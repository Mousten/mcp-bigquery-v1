"""Authentication and authorization module for Supabase JWT validation and RBAC.

This module provides authentication helpers for validating Supabase JWTs,
loading user profiles and roles, and checking dataset/table access permissions.

Environment Variables:
    SUPABASE_JWT_SECRET: Secret key for validating Supabase JWTs
    SUPABASE_URL: Supabase project URL
    SUPABASE_SERVICE_KEY: Service role key for accessing RBAC tables
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from functools import lru_cache


class AuthenticationError(Exception):
    """Raised when JWT validation fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""
    pass


@dataclass
class UserContext:
    """User context with authentication and authorization information.
    
    Attributes:
        user_id: Unique user identifier from Supabase auth
        email: User email address
        roles: List of role names assigned to the user
        permissions: Set of permission strings (e.g., "query:execute", "cache:read")
        allowed_datasets: Set of dataset identifiers the user can access
        allowed_tables: Dict mapping dataset IDs to sets of table IDs
        metadata: Additional user metadata from profile
        token_expires_at: JWT expiration timestamp
    """
    user_id: str
    email: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    allowed_datasets: Set[str] = field(default_factory=set)
    allowed_tables: Dict[str, Set[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_expires_at: Optional[datetime] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def can_access_dataset(self, dataset_id: str) -> bool:
        """Check if user can access a specific dataset.
        
        Args:
            dataset_id: Dataset identifier (normalized)
            
        Returns:
            True if user has access, False otherwise
        """
        # Wildcard access
        if "*" in self.allowed_datasets:
            return True
        
        normalized = normalize_identifier(dataset_id)
        return normalized in self.allowed_datasets
    
    def can_access_table(self, dataset_id: str, table_id: str) -> bool:
        """Check if user can access a specific table.
        
        Args:
            dataset_id: Dataset identifier
            table_id: Table identifier
            
        Returns:
            True if user has access, False otherwise
        """
        # Wildcard dataset access
        if "*" in self.allowed_datasets:
            return True
        
        normalized_dataset = normalize_identifier(dataset_id)
        normalized_table = normalize_identifier(table_id)
        
        # Check dataset-level access first
        if normalized_dataset not in self.allowed_datasets:
            return False
        
        # If dataset is allowed but no specific tables defined, allow all tables
        if normalized_dataset not in self.allowed_tables:
            return True
        
        # Check table-level access
        allowed_tables = self.allowed_tables[normalized_dataset]
        return "*" in allowed_tables or normalized_table in allowed_tables
    
    def is_expired(self) -> bool:
        """Check if the user's token has expired."""
        if self.token_expires_at is None:
            return False
        # Make sure to compare timezone-aware datetimes
        now = datetime.now(timezone.utc)
        # If token_expires_at is naive, assume UTC
        if self.token_expires_at.tzinfo is None:
            token_exp = self.token_expires_at.replace(tzinfo=timezone.utc)
        else:
            token_exp = self.token_expires_at
        return now >= token_exp
    
    @classmethod
    def from_token(
        cls,
        token: str,
        jwt_secret: Optional[str] = None,
        supabase_kb: Optional[Any] = None
    ) -> "UserContext":
        """Create UserContext from a Supabase JWT token.
        
        Args:
            token: JWT token string
            jwt_secret: Secret for validating the JWT (default: from env)
            supabase_kb: SupabaseKnowledgeBase instance for loading roles/permissions
            
        Returns:
            UserContext instance with user information and permissions
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        secret = jwt_secret or os.getenv("SUPABASE_JWT_SECRET")
        if not secret:
            raise AuthenticationError("SUPABASE_JWT_SECRET not configured")
        
        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        
        # Extract user information from token
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing user ID (sub claim)")
        
        email = payload.get("email")
        exp = payload.get("exp")
        token_expires_at = datetime.fromtimestamp(exp, timezone.utc) if exp else None
        
        # Create basic user context
        context = cls(
            user_id=user_id,
            email=email,
            token_expires_at=token_expires_at,
            metadata=payload
        )
        
        # Load roles and permissions from Supabase if available
        if supabase_kb:
            # Note: This is synchronous for now, but can be called from async context
            import asyncio
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, we can't use run_until_complete
                    # The caller should use from_token_async instead
                    pass
                else:
                    asyncio.run(_hydrate_user_context(context, supabase_kb))
            except RuntimeError:
                # No event loop, create one
                asyncio.run(_hydrate_user_context(context, supabase_kb))
        
        return context
    
    @classmethod
    async def from_token_async(
        cls,
        token: str,
        jwt_secret: Optional[str] = None,
        supabase_kb: Optional[Any] = None
    ) -> "UserContext":
        """Async version of from_token that hydrates roles/permissions.
        
        Args:
            token: JWT token string
            jwt_secret: Secret for validating the JWT (default: from env)
            supabase_kb: SupabaseKnowledgeBase instance for loading roles/permissions
            
        Returns:
            UserContext instance with user information and permissions
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        # First decode the token (synchronous)
        secret = jwt_secret or os.getenv("SUPABASE_JWT_SECRET")
        if not secret:
            raise AuthenticationError("SUPABASE_JWT_SECRET not configured")
        
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Token missing user ID (sub claim)")
        
        email = payload.get("email")
        exp = payload.get("exp")
        token_expires_at = datetime.fromtimestamp(exp, timezone.utc) if exp else None
        
        context = cls(
            user_id=user_id,
            email=email,
            token_expires_at=token_expires_at,
            metadata=payload
        )
        
        # Load roles and permissions asynchronously
        if supabase_kb:
            await _hydrate_user_context(context, supabase_kb)
        
        return context


async def _hydrate_user_context(context: UserContext, supabase_kb: Any) -> None:
    """Hydrate user context with roles and permissions from Supabase.
    
    Args:
        context: UserContext to populate
        supabase_kb: SupabaseKnowledgeBase instance
    """
    # Load user profile
    profile = await supabase_kb.get_user_profile(context.user_id)
    if profile:
        context.metadata.update(profile.get("metadata", {}))
    
    # Load user roles
    user_roles = await supabase_kb.get_user_roles(context.user_id)
    context.roles = [role["role_name"] for role in user_roles]
    
    # Load permissions and dataset access for each role
    for role in user_roles:
        role_id = role.get("role_id") or role.get("role_name")
        
        # Load role permissions
        permissions = await supabase_kb.get_role_permissions(role_id)
        for perm in permissions:
            context.permissions.add(perm["permission"])
        
        # Load dataset/table access
        dataset_access = await supabase_kb.get_role_dataset_access(role_id)
        for access in dataset_access:
            dataset_id = normalize_identifier(access["dataset_id"])
            context.allowed_datasets.add(dataset_id)
            
            # Handle table-level access
            if "table_id" in access and access["table_id"]:
                if dataset_id not in context.allowed_tables:
                    context.allowed_tables[dataset_id] = set()
                table_id = normalize_identifier(access["table_id"])
                context.allowed_tables[dataset_id].add(table_id)


def normalize_identifier(identifier: str) -> str:
    """Normalize dataset or table identifier for consistent comparison.
    
    Handles various formats:
    - Simple names: "my_dataset" -> "my_dataset"
    - Backtick-quoted: "`my-dataset`" -> "my-dataset"
    - Project-qualified: "project.dataset" -> "dataset"
    - Full paths: "project.dataset.table" -> "dataset.table" or just "table" depending on context
    
    Args:
        identifier: Dataset or table identifier
        
    Returns:
        Normalized identifier in lowercase without backticks
    """
    if not identifier:
        return ""
    
    # Remove backticks
    cleaned = identifier.strip("`").strip()
    
    # Convert to lowercase for case-insensitive comparison
    cleaned = cleaned.lower()
    
    return cleaned


def extract_dataset_table_from_path(path: str) -> tuple[Optional[str], Optional[str]]:
    """Extract dataset and table from a qualified path.
    
    Args:
        path: Path in format "dataset.table" or "project.dataset.table"
        
    Returns:
        Tuple of (dataset_id, table_id), either may be None
    """
    parts = path.split(".")
    
    if len(parts) == 2:
        return normalize_identifier(parts[0]), normalize_identifier(parts[1])
    elif len(parts) == 3:
        return normalize_identifier(parts[1]), normalize_identifier(parts[2])
    elif len(parts) == 1:
        return None, normalize_identifier(parts[0])
    
    return None, None


def verify_token(token: str, jwt_secret: Optional[str] = None) -> Dict[str, Any]:
    """Verify and decode a Supabase JWT token.
    
    Args:
        token: JWT token string
        jwt_secret: Secret for validating the JWT (default: from env)
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    secret = jwt_secret or os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise AuthenticationError("SUPABASE_JWT_SECRET not configured")
    
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


# In-memory cache for role data with TTL
_role_cache: Dict[str, tuple[Any, datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached_role_data(cache_key: str) -> Optional[Any]:
    """Get cached role data if not expired."""
    if cache_key in _role_cache:
        data, expires_at = _role_cache[cache_key]
        now = datetime.now(timezone.utc)
        # If expires_at is naive, assume UTC
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now < expires_at:
            return data
        else:
            del _role_cache[cache_key]
    return None


def _set_cached_role_data(cache_key: str, data: Any) -> None:
    """Cache role data with TTL."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_CACHE_TTL_SECONDS)
    _role_cache[cache_key] = (data, expires_at)


def clear_role_cache() -> None:
    """Clear all cached role data."""
    global _role_cache
    _role_cache = {}
