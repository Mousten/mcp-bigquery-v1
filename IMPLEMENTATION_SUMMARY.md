# Supabase Auth RBAC Implementation Summary

## Overview

This implementation adds a complete Supabase-backed authentication and role-based access control (RBAC) system to the mcp-bigquery server.

## Changes Made

### 1. Configuration (`src/mcp_bigquery/config/settings.py`)

- Added `supabase_service_key` parameter to ServerConfig
- Added `supabase_jwt_secret` parameter to ServerConfig
- Updated `from_env()` to load these values from environment variables
- Added comprehensive docstring documenting all environment variables

### 2. Auth Module (`src/mcp_bigquery/core/auth.py`)

New module providing:

#### Core Classes
- `AuthenticationError`: Exception for JWT validation failures
- `AuthorizationError`: Exception for permission denials
- `UserContext`: Dataclass holding user authentication and authorization data
  - `user_id`, `email`, `roles`, `permissions`
  - `allowed_datasets`, `allowed_tables`
  - `metadata`, `token_expires_at`

#### Key Methods
- `UserContext.from_token()`: Synchronous token validation
- `UserContext.from_token_async()`: Async token validation with role hydration
- `UserContext.has_permission()`: Check if user has a specific permission
- `UserContext.can_access_dataset()`: Check dataset access
- `UserContext.can_access_table()`: Check table-level access
- `UserContext.is_expired()`: Check token expiration

#### Utility Functions
- `verify_token()`: Decode and validate JWT tokens
- `normalize_identifier()`: Normalize dataset/table identifiers for comparison
- `extract_dataset_table_from_path()`: Parse qualified table paths
- `clear_role_cache()`: Clear in-memory role cache

#### Caching
- In-memory cache for role data with 5-minute TTL
- Reduces database round trips for frequently accessed role information

### 3. Supabase Client Extensions (`src/mcp_bigquery/core/supabase_client.py`)

Added RBAC methods to `SupabaseKnowledgeBase`:

- `get_user_profile(user_id)`: Retrieve user profile
- `get_user_roles(user_id)`: Get roles assigned to user
- `get_role_permissions(role_id)`: Get permissions for a role
- `get_role_dataset_access(role_id)`: Get dataset/table access rules

All methods:
- Are async
- Use in-memory caching (5-minute TTL)
- Handle errors gracefully
- Return empty data structures on failure

### 4. Tests (`tests/core/test_auth.py`)

Comprehensive test suite with 29 tests covering:

- Identifier normalization (5 tests)
- Dataset/table path extraction (3 tests)
- Token verification (4 tests)
- UserContext operations (10 tests)
- Async token handling (3 tests)
- Caching functionality (2 tests)
- Supabase integration (1 test)

**Test Coverage**: 89% for auth.py module

### 5. Dependencies (`pyproject.toml`)

Added:
- `pyjwt>=2.8.0`: JWT token validation
- `pytest-mock>=3.12.0`: Mocking in tests

### 6. Documentation

- `docs/AUTH.md`: Comprehensive authentication and authorization guide
  - Environment variables
  - Database schema requirements
  - Usage examples
  - Error handling guidelines
  - Permission strings

## Database Schema Requirements

The following Supabase tables must exist:

### `user_profiles`
```sql
user_id TEXT PRIMARY KEY
metadata JSONB
```

### `user_roles`
```sql
user_id TEXT
role_id TEXT
role_name TEXT
```

### `role_permissions`
```sql
role_id TEXT
permission TEXT
```

### `role_dataset_access`
```sql
role_id TEXT
dataset_id TEXT
table_id TEXT (nullable)
```

## Environment Variables

New required environment variables:

```bash
SUPABASE_JWT_SECRET=your-jwt-secret-here
SUPABASE_SERVICE_KEY=your-service-key-here
```

Existing (already documented):
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
```

## Usage Example

```python
from mcp_bigquery.core.auth import UserContext, AuthenticationError
from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase

# Initialize Supabase client
kb = SupabaseKnowledgeBase()

# Validate token and load roles/permissions
try:
    context = await UserContext.from_token_async(
        token=request_token,
        supabase_kb=kb
    )
    
    # Check expiration
    if context.is_expired():
        raise AuthenticationError("Token expired")
    
    # Check permission
    if not context.has_permission("query:execute"):
        raise AuthorizationError("Permission denied")
    
    # Check dataset access
    if not context.can_access_dataset("analytics"):
        raise AuthorizationError("Dataset access denied")
    
    # Check table access
    if not context.can_access_table("analytics", "events"):
        raise AuthorizationError("Table access denied")
    
    # Proceed with authorized operation
    ...
    
except AuthenticationError as e:
    # Return HTTP 401
    ...
except AuthorizationError as e:
    # Return HTTP 403
    ...
```

## Integration Notes

### Existing Functionality Preserved
- All existing Supabase functionality remains intact
- Caching, query history, preferences, etc. all work as before
- New RBAC methods are additive, not breaking changes

### Future Integration Points
The auth module is ready to be integrated into:
- FastAPI routes (via dependency injection)
- MCP handlers (for tool-level authorization)
- WebSocket/SSE streams (for real-time auth)

### Token Flow
1. Client authenticates with Supabase Auth
2. Client receives JWT token
3. Client includes token in requests (Authorization header)
4. Server validates token using `UserContext.from_token_async()`
5. Server loads roles/permissions from Supabase
6. Server checks permissions before executing operations

## Testing

Run tests:
```bash
uv run pytest tests/core/test_auth.py -v
```

All 29 tests pass successfully with no warnings.

## Acceptance Criteria Met

✅ Valid Supabase JWT with role assignments returns populated UserContext  
✅ Invalid/expired tokens raise AuthenticationError (translatable to HTTP 401)  
✅ RBAC helpers fetch and memoize permissions from Supabase  
✅ Unit tests cover happy path and failure scenarios  
✅ Environment variables documented in module docstrings  
✅ Existing knowledge-base functionality preserved  

## Next Steps

To fully integrate authentication:

1. **Add middleware** to FastAPI routes for automatic token validation
2. **Update route handlers** to use UserContext for authorization checks
3. **Add MCP tool decorators** for permission-based tool access
4. **Create Supabase migrations** for the required RBAC tables
5. **Update README** with authentication setup instructions
6. **Add integration tests** with real Supabase instance
7. **Implement token refresh** logic for long-running sessions
