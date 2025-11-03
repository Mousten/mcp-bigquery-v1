"""FastAPI dependencies for authentication and authorization."""

from typing import Optional
from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.auth import UserContext, AuthenticationError, AuthorizationError
from ..core.supabase_client import SupabaseKnowledgeBase

# Security scheme for OpenAPI documentation
security = HTTPBearer(auto_error=False)


async def get_user_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
    supabase_kb: Optional[SupabaseKnowledgeBase] = None,
    jwt_secret: Optional[str] = None
) -> UserContext:
    """Extract and validate user context from Authorization header.
    
    Args:
        credentials: Bearer token credentials from HTTPBearer
        authorization: Alternative authorization header
        supabase_kb: SupabaseKnowledgeBase instance for loading roles/permissions
        jwt_secret: JWT secret for token validation
        
    Returns:
        UserContext with user information and permissions
        
    Raises:
        HTTPException: 401 if authentication fails, 403 if authorization fails
    """
    # Extract token from credentials or header
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization:
        # Handle "Bearer <token>" format
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
    
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Create UserContext from token
        context = await UserContext.from_token_async(
            token=token,
            jwt_secret=jwt_secret,
            supabase_kb=supabase_kb
        )
        
        # Check if token has expired
        if context.is_expired():
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return context
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal authentication error: {str(e)}"
        )


def create_auth_dependency(
    supabase_kb: Optional[SupabaseKnowledgeBase] = None,
    jwt_secret: Optional[str] = None
):
    """Factory function to create auth dependency with injected SupabaseKnowledgeBase.
    
    Args:
        supabase_kb: SupabaseKnowledgeBase instance for loading roles/permissions
        jwt_secret: JWT secret for token validation
        
    Returns:
        Dependency function that extracts UserContext
    """
    async def auth_dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        authorization: Optional[str] = Header(None)
    ) -> UserContext:
        return await get_user_context(credentials, authorization, supabase_kb, jwt_secret)
    
    return auth_dependency


def create_optional_auth_dependency(
    supabase_kb: Optional[SupabaseKnowledgeBase] = None,
    jwt_secret: Optional[str] = None
):
    """Factory function to create optional auth dependency.
    
    Returns None if no authentication is provided, otherwise returns UserContext.
    Useful for endpoints that can work with or without authentication.
    
    Args:
        supabase_kb: SupabaseKnowledgeBase instance for loading roles/permissions
        jwt_secret: JWT secret for token validation
        
    Returns:
        Dependency function that extracts optional UserContext
    """
    async def optional_auth_dependency(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        authorization: Optional[str] = Header(None)
    ) -> Optional[UserContext]:
        # If no auth provided, return None
        token = None
        if credentials:
            token = credentials.credentials
        elif authorization:
            if authorization.startswith("Bearer "):
                token = authorization[7:]
            else:
                token = authorization
        
        if not token:
            return None
        
        try:
            context = await UserContext.from_token_async(
                token=token,
                jwt_secret=jwt_secret,
                supabase_kb=supabase_kb
            )
            
            if context.is_expired():
                return None
            
            return context
        except (AuthenticationError, Exception):
            return None
    
    return optional_auth_dependency
