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
        # Try to use service role key first, then anon key
        self.supabase_key = (
            supabase_key or 
            os.getenv("SUPABASE_SERVICE_KEY") or 
            os.getenv("SUPABASE_ANON_KEY")
        )
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) must be provided or set in environment variables.")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self._connection_verified = False
        self._use_service_key = bool(os.getenv("SUPABASE_SERVICE_KEY"))
    
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
        """Retrieve cached query result if available and not expired."""
        if not use_cache or not await self.verify_connection():
            return None
            
        query_hash = self._generate_query_hash(sql)
        
        try:
            query = self.supabase.table("query_cache").select("*").eq(
                "query_hash", query_hash
            ).gte(
                "expires_at", datetime.now().isoformat()
            ).order("created_at", desc=True).limit(1)
            
            # Add user filter if using user-based RLS
            if user_id and not self._use_service_key:
                query = query.eq("user_id", user_id)
            
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
        """Cache query result with metadata and table dependencies."""
        if not use_cache or not await self.verify_connection():
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
                "hit_count": 0
            }
            
            # Add user_id if provided
            if user_id:
                cache_data["user_id"] = user_id
            
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
            
            self.supabase.table("query_history").insert(history_data).execute()
            
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