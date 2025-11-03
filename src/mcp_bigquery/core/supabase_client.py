"""Enhanced Supabase client for caching and knowledge base functionality with RLS support."""
import os
import hashlib
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from supabase import create_client, Client
    # Import APIError at the top
from postgrest.exceptions import APIError
from ..core.json_encoder import CustomJSONEncoder


class SupabaseKnowledgeBase:
    """Enhanced Supabase-backed knowledge base and caching layer with RLS support."""

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        """Initialize the Supabase client."""
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        
        # Determine which key to use and track it
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
        
        # Try to use service role key first, then anon key
        if supabase_key:
            self.supabase_key = supabase_key
            # Check if the provided key is the service key
            self._use_service_key = (service_key and supabase_key == service_key)
        elif service_key:
            self.supabase_key = service_key
            self._use_service_key = True
        elif anon_key:
            self.supabase_key = anon_key
            self._use_service_key = False
        else:
            self.supabase_key = None
            self._use_service_key = False
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) must be provided or set in environment variables.")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self._connection_verified = False
        
        # Log warning if service key is not available for RLS-sensitive operations
        if not self._use_service_key:
            print("WARNING: SupabaseKnowledgeBase initialized without service key. RLS-protected operations may fail.")
    
    async def verify_connection(self) -> bool:
        """Verify the Supabase connection and schema."""
        if self._connection_verified:
            return True
            
        try:
            # Test connection by checking if query_cache table exists
            result = self.supabase.table("query_cache").select("count", count="exact").limit(1).execute()
            self._connection_verified = True
            print(f"Supabase connection verified. Using {'service key' if self._use_service_key else 'anon key'}")
            return True
        except Exception as e:
            print(f"Supabase connection verification failed: {e}")
            return False
    
    def _generate_query_hash(self, sql: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a unique hash for a query."""
        # Normalize SQL: remove extra whitespace, convert to lowercase
        normalized_sql = " ".join(sql.strip().lower().split())
        query_string = normalized_sql
        
        if params:
            query_string += json.dumps(params, sort_keys=True, cls=CustomJSONEncoder)
        
        return hashlib.sha256(query_string.encode()).hexdigest()
    
    async def get_cached_query(
        self, 
        sql: str, 
        max_age_hours: int = 24,
        use_cache: bool = True,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached query result if available and not expired.
        
        Cache isolation: Always filters by user_id to ensure cached content
        is never shared across users with different permissions.
        """
        if not use_cache or not await self.verify_connection():
            return None
        
        # Require user_id for cache isolation
        if not user_id:
            print("Warning: cache access requires user_id for isolation")
            return None
            
        query_hash = self._generate_query_hash(sql)
        
        try:
            query = self.supabase.table("query_cache").select("*").eq(
                "query_hash", query_hash
            ).eq(
                "user_id", user_id
            ).gte(
                "expires_at", datetime.now().isoformat()
            ).order("created_at", desc=True).limit(1)
            
            result = query.execute()
            
            if result.data:
                cache_entry = result.data[0]
                
                # Update hit count asynchronously
                asyncio.create_task(self._update_cache_hit_count(cache_entry["id"]))
                
                return {
                    "cached": True,
                    "result": cache_entry["result_data"],
                    "metadata": cache_entry["metadata"],
                    "cached_at": cache_entry["created_at"],
                    "cache_id": cache_entry["id"]
                }
        except Exception as e:
            print(f"Error retrieving cached query: {e}")
        
        return None
    
    async def _update_cache_hit_count(self, cache_id: str) -> None:
        """Update the hit count for a cache entry."""
        try:
            # Get current hit count first
            current_result = self.supabase.table("query_cache").select("hit_count").eq("id", cache_id).execute()
            if current_result.data:
                current_count = current_result.data[0]["hit_count"] or 0
                self.supabase.table("query_cache").update({
                    "hit_count": current_count + 1
                }).eq("id", cache_id).execute()
        except Exception as e:
            print(f"Error updating cache hit count: {e}")
    
    async def cache_query_result(
        self, 
        sql: str, 
        result_data: List[Dict[str, Any]], 
        metadata: Dict[str, Any],
        tables_accessed: List[str],
        ttl_hours: int = 24,
        use_cache: bool = True,
        user_id: Optional[str] = None
    ) -> bool:
        """Cache query result with metadata and table dependencies.
        
        Cache isolation: Always requires user_id to ensure cached content
        is segregated per user/role.
        """
        if not use_cache or not await self.verify_connection():
            return False
        
        # Require user_id for cache isolation
        if not user_id:
            print("Warning: cache write requires user_id for isolation")
            return False
            
        # Don't cache empty results or very large results
        if not result_data or len(result_data) > 10000:
            return False
            
        query_hash = self._generate_query_hash(sql)
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        try:
            def serialize_for_json(obj):
                if isinstance(obj, (datetime, )):
                    return obj.isoformat()
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return obj

            # Deep copy to avoid mutating original data
            result_data_serialized = json.loads(json.dumps(result_data, default=serialize_for_json))
            metadata_serialized = json.loads(json.dumps(metadata, default=serialize_for_json))

            cache_data = {
                "query_hash": query_hash,
                "sql_query": sql,
                "result_data": result_data_serialized,
                "metadata": metadata_serialized,
                "expires_at": expires_at.isoformat(),
                "hit_count": 0,
                "user_id": user_id
            }
            
            # Insert cache entry
            cache_result = self.supabase.table("query_cache").insert(cache_data).execute()
            
            if cache_result.data:
                cache_id = cache_result.data[0]["id"]
                
                # Insert table dependencies
                await self._insert_table_dependencies(cache_id, tables_accessed, metadata)
                
                print(f"Cached query result with {len(result_data)} rows, expires at {expires_at}")
                return True
                
        except APIError as e:
            print(f"Error caching query result: {e}")
            # Log API error details for debugging
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
        except Exception as e:
            print(f"Error caching query result: {e}")
        
        return False
    
    async def _insert_table_dependencies(
        self, 
        cache_id: str, 
        tables_accessed: List[str], 
        metadata: Dict[str, Any]
    ) -> None:
        """Insert table dependencies for cache invalidation."""
        if not tables_accessed:
            return
            
        dependencies = []
        
        for table_path in tables_accessed:
            # Handle different table path formats
            if "." in table_path:
                parts = table_path.split(".")
                if len(parts) == 2:
                    # dataset.table format
                    dependencies.append({
                        "query_cache_id": cache_id,
                        "project_id": metadata.get("project_id", "unknown"),
                        "dataset_id": parts[0],
                        "table_id": parts[1]
                    })
                elif len(parts) == 3:
                    # project.dataset.table format
                    dependencies.append({
                        "query_cache_id": cache_id,
                        "project_id": parts[0],
                        "dataset_id": parts[1],
                        "table_id": parts[2]
                    })
        
        if dependencies:
            try:
                self.supabase.table("table_dependencies").insert(dependencies).execute()
            except Exception as e:
                print(f"Error inserting table dependencies: {e}")
    
    async def save_query_pattern(
        self, 
        sql: str, 
        execution_stats: Dict[str, Any], 
        tables_accessed: List[str],
        success: bool,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Save query execution pattern for analysis."""
        if not await self.verify_connection():
            return False
            
        try:
            # Prepare query history data
            history_data = {
                "sql_query": sql,
                "execution_time_ms": execution_stats.get("duration_ms"),
                "bytes_processed": execution_stats.get("total_bytes_processed"),
                "success": success,
                "error_message": error_message,
                "tables_accessed": tables_accessed
            }
            
            # Add user_id if provided
            if user_id:
                history_data["user_id"] = user_id
            
            # Note: Saving to query_cache instead of query_history (table doesn't exist)
            # This is for query pattern tracking, not caching results
            self.supabase.table("query_cache").insert(history_data).execute()
            
            return True
            
        except APIError as e:
            print(f"Error saving query pattern: {e}")
            # Log API error details for debugging
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
            return False
        except Exception as e:
            print(f"Error saving query pattern: {e}")
            # Do not access e.details here, as Exception does not have it
            return False
    
    async def get_query_suggestions(
        self, 
        tables_mentioned: List[str], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get query template suggestions based on tables mentioned."""
        if not await self.verify_connection():
            return []
            
        try:
            result = self.supabase.table("query_templates").select("*").order(
                "usage_count", desc=True
            ).limit(limit).execute()
            
            suggestions = []
            for template in result.data:
                suggestions.append({
                    "id": template["id"],
                    "name": template["name"],
                    "description": template["description"],
                    "template_sql": template["template_sql"],
                    "parameters": template["parameters"],
                    "usage_count": template["usage_count"],
                    "tags": template["tags"]
                })
            
            return suggestions
            
        except Exception as e:
            print(f"Error getting query suggestions: {e}")
            return []
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        if not await self.verify_connection():
            return {}
            
        try:
            # Get cache hit/miss statistics
            total_result = self.supabase.table("query_cache").select("count", count="exact").execute()
            hit_result = self.supabase.table("query_cache").select("hit_count").execute()
            
            total_queries = total_result.count if total_result.count else 0
            total_hits = sum(row["hit_count"] for row in hit_result.data) if hit_result.data else 0
            
            # Get expired cache entries
            expired_result = self.supabase.table("query_cache").select("count", count="exact").lt(
                "expires_at", datetime.now().isoformat()
            ).execute()
            
            expired_count = expired_result.count if expired_result.count else 0
            
            return {
                "total_cached_queries": total_queries,
                "total_cache_hits": total_hits,
                "expired_entries": expired_count,
                "hit_rate": (total_hits / max(total_queries, 1)) * 100
            }
            
        except Exception as e:
            print(f"Error getting cache stats: {e}")
            return {}
    
    async def cleanup_expired_cache(self) -> int:
        """Manually clean up expired cache entries."""
        if not await self.verify_connection():
            return 0
            
        try:
            # Get expired entries
            expired_result = self.supabase.table("query_cache").select("id").lt(
                "expires_at", datetime.now().isoformat()
            ).execute()
            
            if expired_result.data:
                expired_ids = [row["id"] for row in expired_result.data]
                
                # Delete expired entries (dependencies will be cascade deleted)
                self.supabase.table("query_cache").delete().in_("id", expired_ids).execute()
                
                return len(expired_ids)
                
        except Exception as e:
            print(f"Error cleaning up expired cache: {e}")
        
        return 0

    async def get_column_documentation(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str
    ) -> Optional[dict]:
        """
        Retrieve column documentation for a given table from Supabase.
        """
        if not await self.verify_connection():
            return None
        try:
            result = self.supabase.table("column_documentation") \
                .select("*") \
                .eq("project_id", project_id) \
                .eq("dataset_id", dataset_id) \
                .eq("table_id", table_id) \
                .limit(1) \
                .execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error fetching column documentation: {e}")
            return None

    async def save_query_template(
        self,
        name: str,
        description: str,
        template_sql: str,
        parameters: list,
        tags: list,
        user_id: Optional[str] = None
    ) -> bool:
        """Save a query template to Supabase."""
        if not await self.verify_connection():
            return False
        try:
            template_data = {
                "name": name,
                "description": description,
                "template_sql": template_sql,
                "parameters": parameters,
                "tags": tags,
                "usage_count": 1,
            }
            if user_id:
                template_data["user_id"] = user_id
            self.supabase.table("query_templates").insert(template_data).execute()
            return True
        except Exception as e:
            print(f"Error saving query template: {e}")
            return False

    async def get_user_preferences(self, user_id: str) -> Optional[dict]:
        """Retrieve user preferences from Supabase."""
        if not await self.verify_connection():
            return None
        try:
            result = self.supabase.table("user_preferences").select("*").eq("user_id", user_id).limit(1).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error fetching user preferences: {e}")
            return None

    async def set_user_preferences(self, user_id: str, preferences: dict) -> bool:
        """Set or update user preferences in Supabase."""
        if not await self.verify_connection():
            return False
        try:
            # Upsert (insert or update)
            self.supabase.table("user_preferences").upsert({
                "user_id": user_id,
                "preferences": preferences
            }).execute()
            return True
        except Exception as e:
            print(f"Error setting user preferences: {e}")
            return False

    async def increment_common_request(self, sql: str) -> None:
        """Increment a counter for common requests."""
        if not await self.verify_connection():
            return
        try:
            # Use a hash of the SQL as the key
            sql_hash = self._generate_query_hash(sql)
            result = self.supabase.table("common_requests").select("*").eq("sql_hash", sql_hash).limit(1).execute()
            if result.data:
                # Update count
                self.supabase.table("common_requests").update({
                    "count": result.data[0]["count"] + 1
                }).eq("sql_hash", sql_hash).execute()
            else:
                # Insert new
                self.supabase.table("common_requests").insert({
                    "sql_hash": sql_hash,
                    "sql_query": sql,
                    "count": 1
                }).execute()
        except Exception as e:
            print(f"Error incrementing common request: {e}")

    async def invalidate_cache_for_table(
        self, project_id: str, dataset_id: str, table_id: str
    ) -> bool:
        """
        Invalidate (delete) all cached queries related to a specific table.
        """
        try:
            response = self.supabase.table("query_cache") \
                .delete() \
                .eq("project_id", project_id) \
                .eq("dataset_id", dataset_id) \
                .eq("table_id", table_id) \
                .execute()
            return True
        except Exception as e:
            print(f"Error invalidating cache for table: {e}")
            return False
    
    # RBAC Methods
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile from Supabase.
        
        Args:
            user_id: User ID from Supabase auth
            
        Returns:
            User profile dict or None if not found
        """
        if not await self.verify_connection():
            return None
        
        # Check cache first
        from .auth import _get_cached_role_data, _set_cached_role_data
        cache_key = f"user_profile:{user_id}"
        cached = _get_cached_role_data(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = self.supabase.table("user_profiles") \
                .select("*") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()
            
            profile = result.data[0] if result.data else None
            if profile:
                _set_cached_role_data(cache_key, profile)
            return profile
        except Exception as e:
            print(f"Error fetching user profile: {e}")
            return None
    
    async def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve roles assigned to a user.
        
        Args:
            user_id: User ID from Supabase auth
            
        Returns:
            List of role dicts with role_id, role_name, etc.
        """
        if not await self.verify_connection():
            return []
        
        # Check cache first
        from .auth import _get_cached_role_data, _set_cached_role_data
        cache_key = f"user_roles:{user_id}"
        cached = _get_cached_role_data(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = self.supabase.table("user_roles") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            roles = result.data or []
            _set_cached_role_data(cache_key, roles)
            return roles
        except Exception as e:
            print(f"Error fetching user roles: {e}")
            return []
    
    async def get_role_permissions(self, role_id: str) -> List[Dict[str, Any]]:
        """Retrieve permissions for a specific role.
        
        Args:
            role_id: Role identifier
            
        Returns:
            List of permission dicts with permission strings
        """
        if not await self.verify_connection():
            return []
        
        # Check cache first
        from .auth import _get_cached_role_data, _set_cached_role_data
        cache_key = f"role_permissions:{role_id}"
        cached = _get_cached_role_data(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = self.supabase.table("role_permissions") \
                .select("*") \
                .eq("role_id", role_id) \
                .execute()
            
            permissions = result.data or []
            _set_cached_role_data(cache_key, permissions)
            return permissions
        except Exception as e:
            print(f"Error fetching role permissions: {e}")
            return []
    
    async def get_role_dataset_access(self, role_id: str) -> List[Dict[str, Any]]:
        """Retrieve dataset/table access rules for a specific role.
        
        Args:
            role_id: Role identifier
            
        Returns:
            List of access rule dicts with dataset_id, table_id (optional), etc.
        """
        if not await self.verify_connection():
            return []
        
        # Check cache first
        from .auth import _get_cached_role_data, _set_cached_role_data
        cache_key = f"role_dataset_access:{role_id}"
        cached = _get_cached_role_data(cache_key)
        if cached is not None:
            return cached
        
        try:
            result = self.supabase.table("role_dataset_access") \
                .select("*") \
                .eq("role_id", role_id) \
                .execute()
            
            access_rules = result.data or []
            _set_cached_role_data(cache_key, access_rules)
            return access_rules
        except Exception as e:
            print(f"Error fetching role dataset access: {e}")
            return []
    
    # Chat Session Management Methods
    
    async def create_chat_session(
        self,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new chat session for a user.
        
        Expected table schema for chat_sessions:
        - id: uuid (primary key)
        - user_id: text (foreign key to user_profiles)
        - title: text (nullable)
        - created_at: timestamptz (auto)
        - updated_at: timestamptz (auto)
        - metadata: jsonb (nullable)
        
        Args:
            user_id: User ID from Supabase auth
            title: Optional session title
            metadata: Optional metadata dict
            
        Returns:
            Created session dict with id, user_id, title, created_at, updated_at, metadata
            or None if connection fails
            
        Raises:
            Exception: If table doesn't exist or insert fails
        """
        if not await self.verify_connection():
            return None
        
        try:
            session_data = {
                "user_id": user_id,
                "title": title or "New Chat",
                "metadata": metadata or {}
            }
            
            result = self.supabase.table("chat_sessions").insert(session_data).execute()
            
            if result.data:
                print(f"Created chat session {result.data[0]['id']} for user {user_id}")
                return result.data[0]
            return None
            
        except APIError as e:
            print(f"Error creating chat session: {e}")
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
            raise
        except Exception as e:
            print(f"Error creating chat session: {e}")
            raise
    
    async def get_chat_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a chat session by ID.
        
        Args:
            session_id: Chat session ID
            user_id: Optional user ID for access control (required if not using service key)
            
        Returns:
            Session dict or None if not found
        """
        if not await self.verify_connection():
            return None
        
        try:
            query = self.supabase.table("chat_sessions").select("*").eq("id", session_id)
            
            # Add user filter if using user-based RLS
            if user_id and not self._use_service_key:
                query = query.eq("user_id", user_id)
            
            result = query.limit(1).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            print(f"Error retrieving chat session: {e}")
            return None
    
    async def get_user_chat_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve chat sessions for a user, ordered by most recent.
        
        Args:
            user_id: User ID from Supabase auth
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip (for pagination)
            
        Returns:
            List of session dicts ordered by updated_at desc
        """
        if not await self.verify_connection():
            return []
        
        try:
            result = self.supabase.table("chat_sessions") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("updated_at", desc=True) \
                .limit(limit) \
                .offset(offset) \
                .execute()
            
            return result.data or []
            
        except Exception as e:
            print(f"Error retrieving user chat sessions: {e}")
            return []
    
    async def update_chat_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Update a chat session's title or metadata.
        
        Args:
            session_id: Chat session ID
            title: Optional new title
            metadata: Optional new metadata
            user_id: Optional user ID for access control
            
        Returns:
            True if update succeeded, False otherwise
        """
        if not await self.verify_connection():
            return False
        
        try:
            update_data = {}
            if title is not None:
                update_data["title"] = title
            if metadata is not None:
                update_data["metadata"] = metadata
            
            if not update_data:
                return True
            
            query = self.supabase.table("chat_sessions").update(update_data).eq("id", session_id)
            
            # Add user filter if using user-based RLS
            if user_id and not self._use_service_key:
                query = query.eq("user_id", user_id)
            
            query.execute()
            return True
            
        except Exception as e:
            print(f"Error updating chat session: {e}")
            return False
    
    async def append_chat_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Append a message to a chat session.
        
        Expected table schema for chat_messages:
        - id: uuid (primary key)
        - chat_session_id: uuid (foreign key to chat_sessions)
        - user_id: text (foreign key to user_profiles)
        - role: text (e.g., 'user', 'assistant', 'system')
        - content: text
        - created_at: timestamptz (auto)
        - metadata: jsonb (nullable)
        
        Args:
            session_id: Chat session ID
            user_id: User ID from Supabase auth
            role: Message role ('user', 'assistant', 'system', etc.)
            content: Message content
            metadata: Optional metadata (tokens, model, etc.)
            
        Returns:
            Created message dict or None if insert fails
            
        Raises:
            Exception: If table doesn't exist or insert fails
        """
        if not await self.verify_connection():
            return None
        
        try:
            message_data = {
                "chat_session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "metadata": metadata or {}
            }
            
            result = self.supabase.table("chat_messages").insert(message_data).execute()
            
            if result.data:
                # Update session's updated_at timestamp
                asyncio.create_task(
                    self._touch_chat_session(session_id)
                )
                return result.data[0]
            return None
            
        except APIError as e:
            print(f"Error appending chat message: {e}")
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
            raise
        except Exception as e:
            print(f"Error appending chat message: {e}")
            raise
    
    async def _touch_chat_session(self, session_id: str) -> None:
        """Update a chat session's updated_at timestamp."""
        try:
            from datetime import timezone
            self.supabase.table("chat_sessions") \
                .update({"updated_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", session_id) \
                .execute()
        except Exception as e:
            print(f"Error updating chat session timestamp: {e}")
    
    async def get_chat_messages(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve messages from a chat session.
        
        Args:
            session_id: Chat session ID
            user_id: Optional user ID for access control
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            List of message dicts ordered by created_at asc
        """
        if not await self.verify_connection():
            return []
        
        try:
            query = self.supabase.table("chat_messages") \
                .select("*") \
                .eq("chat_session_id", session_id) \
                .order("created_at", desc=False) \
                .limit(limit) \
                .offset(offset)
            
            # Add user filter if using user-based RLS
            if user_id and not self._use_service_key:
                query = query.eq("user_id", user_id)
            
            result = query.execute()
            return result.data or []
            
        except Exception as e:
            print(f"Error retrieving chat messages: {e}")
            return []
    
    async def get_chat_history(
        self,
        user_id: str,
        limit_sessions: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve recent chat sessions with their latest messages.
        
        Args:
            user_id: User ID from Supabase auth
            limit_sessions: Maximum number of sessions to return
            
        Returns:
            List of session dicts with 'messages' key containing recent messages
        """
        sessions = await self.get_user_chat_sessions(user_id, limit=limit_sessions)
        
        for session in sessions:
            session['messages'] = await self.get_chat_messages(
                session['id'],
                user_id=user_id,
                limit=10
            )
        
        return sessions
    
    # LLM Response Caching Methods
    
    def _generate_prompt_hash(
        self,
        prompt: str,
        provider: str,
        model: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a unique hash for an LLM prompt with provider metadata.
        
        Args:
            prompt: Normalized prompt text
            provider: LLM provider (e.g., 'openai', 'anthropic')
            model: Model name (e.g., 'gpt-4', 'claude-3-opus')
            parameters: Optional parameters dict (temperature, max_tokens, etc.)
            
        Returns:
            SHA256 hash string
        """
        # Normalize prompt: remove extra whitespace
        normalized_prompt = " ".join(prompt.strip().split())
        
        # Build hash string with provider metadata
        hash_components = [normalized_prompt, provider, model]
        
        if parameters:
            # Sort keys for consistent hashing
            hash_components.append(json.dumps(parameters, sort_keys=True, cls=CustomJSONEncoder))
        
        hash_string = "||".join(hash_components)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    async def get_cached_llm_response(
        self,
        prompt: str,
        provider: str,
        model: str,
        parameters: Optional[Dict[str, Any]] = None,
        max_age_hours: int = 168  # 7 days default
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached LLM response if available and not expired.
        
        Expected table schema for llm_response_cache:
        - id: uuid (primary key)
        - prompt_hash: text (unique index)
        - prompt: text
        - provider: text
        - model: text
        - response: text
        - metadata: jsonb (nullable - tokens, finish_reason, etc.)
        - embedding: vector (nullable - for similarity search)
        - created_at: timestamptz (auto)
        - expires_at: timestamptz
        - hit_count: integer (default 0)
        
        Args:
            prompt: Prompt text
            provider: LLM provider
            model: Model name
            parameters: Optional parameters dict
            max_age_hours: Maximum age in hours for cache validity
            
        Returns:
            Dict with cached response data including 'response', 'metadata', 'cached_at', 'hit_count'
            or None if cache miss
        """
        if not await self.verify_connection():
            return None
        
        prompt_hash = self._generate_prompt_hash(prompt, provider, model, parameters)
        
        try:
            result = self.supabase.table("llm_response_cache") \
                .select("*") \
                .eq("prompt_hash", prompt_hash) \
                .gte("expires_at", datetime.now().isoformat()) \
                .limit(1) \
                .execute()
            
            if result.data:
                cache_entry = result.data[0]
                
                # Update hit count asynchronously
                asyncio.create_task(
                    self._update_llm_cache_hit_count(cache_entry["id"])
                )
                
                return {
                    "cached": True,
                    "response": cache_entry["response"],
                    "metadata": cache_entry.get("metadata", {}),
                    "cached_at": cache_entry["created_at"],
                    "cache_id": cache_entry["id"],
                    "hit_count": cache_entry.get("hit_count", 0),
                    "provider": cache_entry["provider"],
                    "model": cache_entry["model"]
                }
            
            return None
            
        except Exception as e:
            print(f"Error retrieving cached LLM response: {e}")
            return None
    
    async def _update_llm_cache_hit_count(self, cache_id: str) -> None:
        """Update the hit count for an LLM cache entry."""
        try:
            current_result = self.supabase.table("llm_response_cache") \
                .select("hit_count") \
                .eq("id", cache_id) \
                .execute()
            
            if current_result.data:
                current_count = current_result.data[0]["hit_count"] or 0
                self.supabase.table("llm_response_cache") \
                    .update({"hit_count": current_count + 1}) \
                    .eq("id", cache_id) \
                    .execute()
        except Exception as e:
            print(f"Error updating LLM cache hit count: {e}")
    
    async def cache_llm_response(
        self,
        prompt: str,
        provider: str,
        model: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        ttl_hours: int = 168  # 7 days default
    ) -> bool:
        """Cache an LLM response with metadata.
        
        Args:
            prompt: Prompt text
            provider: LLM provider
            model: Model name
            response: LLM response text
            metadata: Optional metadata (tokens, finish_reason, etc.)
            parameters: Optional parameters used for generation
            embedding: Optional embedding vector for similarity search
            ttl_hours: Time-to-live in hours
            
        Returns:
            True if caching succeeded, False otherwise
        """
        if not await self.verify_connection():
            return False
        
        # Don't cache empty responses
        if not response or not response.strip():
            return False
        
        prompt_hash = self._generate_prompt_hash(prompt, provider, model, parameters)
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        try:
            cache_data = {
                "prompt_hash": prompt_hash,
                "prompt": prompt,
                "provider": provider,
                "model": model,
                "response": response,
                "metadata": metadata or {},
                "expires_at": expires_at.isoformat(),
                "hit_count": 0
            }
            
            # Add embedding if provided
            if embedding:
                cache_data["embedding"] = embedding
            
            # Upsert to handle duplicate prompt hashes
            result = self.supabase.table("llm_response_cache") \
                .upsert(cache_data, on_conflict="prompt_hash") \
                .execute()
            
            if result.data:
                print(f"Cached LLM response (provider={provider}, model={model}), expires at {expires_at}")
                return True
            
            return False
            
        except APIError as e:
            print(f"Error caching LLM response: {e}")
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
            return False
        except Exception as e:
            print(f"Error caching LLM response: {e}")
            return False
    
    async def get_similar_cached_prompts(
        self,
        embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Find similar cached prompts using vector similarity search.
        
        This requires pgvector extension and a vector column in llm_response_cache.
        
        Args:
            embedding: Query embedding vector
            limit: Maximum number of similar prompts to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of similar cache entries with similarity scores
        """
        if not await self.verify_connection():
            return []
        
        try:
            # This is a placeholder - actual implementation depends on pgvector setup
            # Would use something like: .rpc('match_prompts', {'query_embedding': embedding, ...})
            print("Vector similarity search not yet implemented - requires pgvector setup")
            return []
        except Exception as e:
            print(f"Error finding similar cached prompts: {e}")
            return []
    
    async def cleanup_expired_llm_cache(self) -> int:
        """Clean up expired LLM cache entries.
        
        Returns:
            Number of entries deleted
        """
        if not await self.verify_connection():
            return 0
        
        try:
            expired_result = self.supabase.table("llm_response_cache") \
                .select("id") \
                .lt("expires_at", datetime.now().isoformat()) \
                .execute()
            
            if expired_result.data:
                expired_ids = [row["id"] for row in expired_result.data]
                
                self.supabase.table("llm_response_cache") \
                    .delete() \
                    .in_("id", expired_ids) \
                    .execute()
                
                print(f"Cleaned up {len(expired_ids)} expired LLM cache entries")
                return len(expired_ids)
            
            return 0
            
        except Exception as e:
            print(f"Error cleaning up expired LLM cache: {e}")
            return 0
    
    # Token Usage Tracking Methods
    
    async def record_token_usage(
        self,
        user_id: str,
        tokens_consumed: int,
        provider: str,
        model: str,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record token usage for a user.
        
        Expected table schema for user_usage_stats:
        - id: uuid (primary key)
        - user_id: text (foreign key to user_profiles)
        - period_start: date (start of the tracking period)
        - period_end: date (end of the tracking period)
        - tokens_consumed: bigint
        - requests_count: integer
        - quota_limit: bigint (nullable - daily/monthly limit)
        - created_at: timestamptz (auto)
        - updated_at: timestamptz (auto)
        - metadata: jsonb (nullable - provider/model breakdown)
        
        Args:
            user_id: User ID from Supabase auth
            tokens_consumed: Number of tokens consumed
            provider: LLM provider
            model: Model name
            request_metadata: Optional request metadata
            
        Returns:
            True if recording succeeded, False otherwise
        """
        if not await self.verify_connection():
            return False
        
        if tokens_consumed <= 0:
            return True
        
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(days=1)
            
            # Check if we have a stats record for today
            result = self.supabase.table("user_usage_stats") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("period_start", period_start.date().isoformat()) \
                .limit(1) \
                .execute()
            
            if result.data:
                # Update existing record
                current_stats = result.data[0]
                current_tokens = current_stats.get("tokens_consumed", 0)
                current_requests = current_stats.get("requests_count", 0)
                current_metadata = current_stats.get("metadata", {})
                
                # Update provider/model breakdown
                if "providers" not in current_metadata:
                    current_metadata["providers"] = {}
                if provider not in current_metadata["providers"]:
                    current_metadata["providers"][provider] = {}
                if model not in current_metadata["providers"][provider]:
                    current_metadata["providers"][provider][model] = {
                        "tokens": 0,
                        "requests": 0
                    }
                
                current_metadata["providers"][provider][model]["tokens"] += tokens_consumed
                current_metadata["providers"][provider][model]["requests"] += 1
                
                self.supabase.table("user_usage_stats") \
                    .update({
                        "tokens_consumed": current_tokens + tokens_consumed,
                        "requests_count": current_requests + 1,
                        "metadata": current_metadata,
                        "updated_at": now.isoformat()
                    }) \
                    .eq("id", current_stats["id"]) \
                    .execute()
            else:
                # Create new record
                metadata = {
                    "providers": {
                        provider: {
                            model: {
                                "tokens": tokens_consumed,
                                "requests": 1
                            }
                        }
                    }
                }
                
                if request_metadata:
                    metadata["request_metadata"] = request_metadata
                
                self.supabase.table("user_usage_stats") \
                    .insert({
                        "user_id": user_id,
                        "period_start": period_start.date().isoformat(),
                        "period_end": period_end.date().isoformat(),
                        "tokens_consumed": tokens_consumed,
                        "requests_count": 1,
                        "metadata": metadata
                    }) \
                    .execute()
            
            return True
            
        except APIError as e:
            print(f"Error recording token usage: {e}")
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
            return False
        except Exception as e:
            print(f"Error recording token usage: {e}")
            return False
    
    async def get_user_token_usage(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get token usage statistics for a user over a period.
        
        Args:
            user_id: User ID from Supabase auth
            days: Number of days to look back
            
        Returns:
            Dict with total_tokens, total_requests, daily_breakdown, provider_breakdown
        """
        if not await self.verify_connection():
            return {
                "total_tokens": 0,
                "total_requests": 0,
                "daily_breakdown": [],
                "provider_breakdown": {}
            }
        
        try:
            from datetime import timezone
            start_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
            
            result = self.supabase.table("user_usage_stats") \
                .select("*") \
                .eq("user_id", user_id) \
                .gte("period_start", start_date.isoformat()) \
                .order("period_start", desc=True) \
                .execute()
            
            daily_stats = result.data or []
            
            total_tokens = sum(stat.get("tokens_consumed", 0) for stat in daily_stats)
            total_requests = sum(stat.get("requests_count", 0) for stat in daily_stats)
            
            # Aggregate provider breakdown
            provider_breakdown = {}
            for stat in daily_stats:
                metadata = stat.get("metadata", {})
                providers = metadata.get("providers", {})
                
                for provider, models in providers.items():
                    if provider not in provider_breakdown:
                        provider_breakdown[provider] = {}
                    
                    for model, usage in models.items():
                        if model not in provider_breakdown[provider]:
                            provider_breakdown[provider][model] = {
                                "tokens": 0,
                                "requests": 0
                            }
                        
                        provider_breakdown[provider][model]["tokens"] += usage.get("tokens", 0)
                        provider_breakdown[provider][model]["requests"] += usage.get("requests", 0)
            
            return {
                "total_tokens": total_tokens,
                "total_requests": total_requests,
                "daily_breakdown": daily_stats,
                "provider_breakdown": provider_breakdown
            }
            
        except Exception as e:
            print(f"Error getting user token usage: {e}")
            return {
                "total_tokens": 0,
                "total_requests": 0,
                "daily_breakdown": [],
                "provider_breakdown": {}
            }
    
    async def check_user_quota(
        self,
        user_id: str,
        quota_period: str = "daily"
    ) -> Dict[str, Any]:
        """Check if a user has exceeded their token quota.
        
        Args:
            user_id: User ID from Supabase auth
            quota_period: 'daily' or 'monthly'
            
        Returns:
            Dict with quota_limit, tokens_used, remaining, is_over_quota
        """
        if not await self.verify_connection():
            return {
                "quota_limit": None,
                "tokens_used": 0,
                "remaining": None,
                "is_over_quota": False
            }
        
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            if quota_period == "daily":
                period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                days_to_check = 1
            else:  # monthly
                period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                days_to_check = 31
            
            # Get usage for the period
            usage_stats = await self.get_user_token_usage(user_id, days=days_to_check)
            tokens_used = usage_stats["total_tokens"]
            
            # Get user's quota limit (could be from user preferences or a separate quota table)
            user_prefs = await self.get_user_preferences(user_id)
            quota_limit = None
            
            if user_prefs and "preferences" in user_prefs:
                prefs = user_prefs["preferences"]
                if quota_period == "daily":
                    quota_limit = prefs.get("daily_token_quota")
                else:
                    quota_limit = prefs.get("monthly_token_quota")
            
            # Calculate remaining and check if over quota
            is_over_quota = False
            remaining = None
            
            if quota_limit is not None:
                remaining = max(0, quota_limit - tokens_used)
                is_over_quota = tokens_used >= quota_limit
            
            return {
                "quota_limit": quota_limit,
                "tokens_used": tokens_used,
                "remaining": remaining,
                "is_over_quota": is_over_quota,
                "quota_period": quota_period
            }
            
        except Exception as e:
            print(f"Error checking user quota: {e}")
            return {
                "quota_limit": None,
                "tokens_used": 0,
                "remaining": None,
                "is_over_quota": False
            }
    
    # Chat Persistence Methods
    
    async def create_chat_session(
        self, 
        user_id: str, 
        title: str = "New Conversation"
    ) -> Optional[Dict[str, Any]]:
        """Create a new chat session for a user.
        
        Args:
            user_id: User ID from Supabase auth
            title: Optional session title
            
        Returns:
            Created session dict with id, user_id, title, created_at, updated_at
        """
        if not await self.verify_connection():
            return None
        
        # Warn if not using service key
        if not self._use_service_key:
            print("WARNING: Creating chat session without service key - this may fail due to RLS policies")
        
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            session_data = {
                "user_id": user_id,
                "title": title,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            
            print(f"Creating chat session for user {user_id} using {'service key' if self._use_service_key else 'anon key'}")
            result = self.supabase.table("chat_sessions").insert(session_data).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except APIError as e:
            error_msg = f"Error creating chat session: {e}"
            print(error_msg)
            if hasattr(e, 'message'):
                print(f"API Error message: {e.message}")
            if hasattr(e, 'details') and e.details:
                print(f"API Error details: {e.details}")
            if hasattr(e, 'hint') and e.hint:
                print(f"API Error hint: {e.hint}")
            if hasattr(e, 'code'):
                print(f"API Error code: {e.code}")
            
            # If RLS error and not using service key, provide helpful message
            if hasattr(e, 'code') and e.code == '42501' and not self._use_service_key:
                print("HINT: This is an RLS policy violation. Ensure SUPABASE_SERVICE_KEY is set in environment variables.")
            
            return None
        except Exception as e:
            print(f"Error creating chat session: {e}")
            return None
    
    async def list_chat_sessions(
        self, 
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List chat sessions for a user, ordered by most recent first.
        
        Args:
            user_id: User ID from Supabase auth
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            
        Returns:
            List of session dicts ordered by updated_at descending
        """
        if not await self.verify_connection():
            return []
        
        try:
            result = self.supabase.table("chat_sessions") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("updated_at", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"Error listing chat sessions: {e}")
            return []
    
    async def append_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Append a message to a chat session.
        
        Args:
            session_id: Session UUID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (model, tokens, etc.)
            user_id: Optional user ID for ownership validation
            
        Returns:
            Created message dict or None on failure
        """
        if not await self.verify_connection():
            return None
        
        # Validate role
        if role not in ["user", "assistant", "system"]:
            print(f"Invalid message role: {role}")
            return None
        
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Validate session ownership if user_id provided
            if user_id:
                session_result = self.supabase.table("chat_sessions") \
                    .select("user_id") \
                    .eq("id", session_id) \
                    .limit(1) \
                    .execute()
                
                if not session_result.data:
                    print(f"Session not found: {session_id}")
                    return None
                
                if session_result.data[0]["user_id"] != user_id:
                    print(f"Session ownership validation failed")
                    return None
            
            # Get current message count to determine ordering
            count_result = self.supabase.table("chat_messages") \
                .select("ordering", count="exact") \
                .eq("session_id", session_id) \
                .order("ordering", desc=True) \
                .limit(1) \
                .execute()
            
            ordering = 0
            if count_result.data:
                ordering = count_result.data[0]["ordering"] + 1
            
            message_data = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "created_at": now.isoformat(),
                "ordering": ordering
            }
            
            result = self.supabase.table("chat_messages").insert(message_data).execute()
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            print(f"Error appending chat message: {e}")
            return None
    
    async def fetch_chat_history(
        self,
        session_id: str,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch chat history for a session in chronological order.
        
        Args:
            session_id: Session UUID
            user_id: User ID for ownership validation
            limit: Optional maximum number of messages to return
            
        Returns:
            List of message dicts ordered by ordering field
        """
        if not await self.verify_connection():
            return []
        
        try:
            # Validate session ownership
            session_result = self.supabase.table("chat_sessions") \
                .select("user_id") \
                .eq("id", session_id) \
                .limit(1) \
                .execute()
            
            if not session_result.data:
                print(f"Session not found: {session_id}")
                return []
            
            if session_result.data[0]["user_id"] != user_id:
                print(f"Session ownership validation failed")
                return []
            
            # Fetch messages
            query = self.supabase.table("chat_messages") \
                .select("*") \
                .eq("session_id", session_id) \
                .order("ordering", desc=False)
            
            if limit:
                query = query.limit(limit)
            
            result = query.execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"Error fetching chat history: {e}")
            return []
    
    async def rename_session(
        self,
        session_id: str,
        title: str,
        user_id: str
    ) -> bool:
        """Rename a chat session.
        
        Args:
            session_id: Session UUID
            title: New session title
            user_id: User ID for ownership validation
            
        Returns:
            True if successful, False otherwise
        """
        if not await self.verify_connection():
            return False
        
        try:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Validate session ownership
            session_result = self.supabase.table("chat_sessions") \
                .select("user_id") \
                .eq("id", session_id) \
                .limit(1) \
                .execute()
            
            if not session_result.data:
                print(f"Session not found: {session_id}")
                return False
            
            if session_result.data[0]["user_id"] != user_id:
                print(f"Session ownership validation failed")
                return False
            
            # Update title
            update_result = self.supabase.table("chat_sessions") \
                .update({
                    "title": title,
                    "updated_at": now.isoformat()
                }) \
                .eq("id", session_id) \
                .execute()
            
            return bool(update_result.data)
            
        except Exception as e:
            print(f"Error renaming session: {e}")
            return False
    
    async def delete_chat_session(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """Delete a chat session and all its messages.
        
        Args:
            session_id: Session UUID
            user_id: User ID for ownership validation
            
        Returns:
            True if successful, False otherwise
        """
        if not await self.verify_connection():
            return False
        
        try:
            # Validate session ownership
            session_result = self.supabase.table("chat_sessions") \
                .select("user_id") \
                .eq("id", session_id) \
                .limit(1) \
                .execute()
            
            if not session_result.data:
                print(f"Session not found: {session_id}")
                return False
            
            if session_result.data[0]["user_id"] != user_id:
                print(f"Session ownership validation failed")
                return False
            
            # Delete session (messages will cascade delete)
            delete_result = self.supabase.table("chat_sessions") \
                .delete() \
                .eq("id", session_id) \
                .execute()
            
            return True
            
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False