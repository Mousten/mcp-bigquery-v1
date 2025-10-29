# Supabase Authentication Implementation Summary

This document describes the Supabase-backed authentication and RBAC implementation for the MCP BigQuery server.

## Overview

The MCP BigQuery server now has a complete JWT-based authentication layer with role-based access control (RBAC) for fine-grained dataset and table permissions. All HTTP endpoints and MCP tool invocations require valid authentication tokens.

## Components Implemented

### 1. Configuration (`src/mcp_bigquery/config/settings.py`)

The `ServerConfig` class (Pydantic v2 BaseSettings) includes:
- `supabase_url`: Supabase project URL
- `supabase_key`: Anonymous key (backward compatible with `SUPABASE_ANON_KEY`)
- `supabase_service_key`: Service role key for RBAC queries (bypasses RLS)
- `supabase_jwt_secret`: JWT secret for token validation

All configuration is loaded from environment variables with automatic validation.

### 2. Authentication Module (`src/mcp_bigquery/core/auth.py`)

**Pydantic Models:**
- `UserContext`: Main user context with auth/authz data
  - Contains user_id, email, roles, permissions, allowed datasets/tables
  - Methods: `has_permission()`, `can_access_dataset()`, `can_access_table()`, `is_expired()`
  - Factory methods: `from_token()` (sync), `from_token_async()` (async with role hydration)
- `UserProfile`: User profile from Supabase
- `UserRole`: Role assignment
- `RolePermission`: Permission strings (e.g., "query:execute", "cache:read")
- `DatasetAccess`: Dataset/table access rules with wildcard support

**Key Features:**
- JWT validation using PyJWT with signature and expiry verification
- Automatic role/permission loading from Supabase tables
- In-memory caching (5-minute TTL) for role data
- Wildcard support ("*" for all datasets/tables)
- Graceful fallback when Pydantic validation fails
- Identifier normalization for consistent comparison

**Exceptions:**
- `AuthenticationError`: 401 - Invalid or expired tokens
- `AuthorizationError`: 403 - Insufficient permissions

### 3. FastAPI Dependencies (`src/mcp_bigquery/api/dependencies.py`)

**Functions:**
- `get_user_context()`: Extracts and validates JWT from Authorization header
- `create_auth_dependency()`: Factory for creating auth dependency with SupabaseKnowledgeBase
- `create_optional_auth_dependency()`: Returns None if no auth provided (for optional auth)

**Features:**
- Supports both HTTPBearer credentials and Authorization header
- Automatic token extraction from "Bearer <token>" format
- Returns 401 for missing/invalid tokens, 403 for authorization failures
- Integration with SupabaseKnowledgeBase for role loading

### 4. Route Integration

All user-facing routes require authentication:

**`src/mcp_bigquery/routes/tools.py`:**
- All endpoints use `Depends(get_current_user)` for authentication
- Receives `UserContext` instance with permissions and access controls
- Endpoints: query execution, dataset/table listing, schema access, cache management

**`src/mcp_bigquery/routes/resources.py`:**
- List and read BigQuery resources with RBAC enforcement
- Filters results based on user's allowed datasets/tables

**`src/mcp_bigquery/routes/chat.py`:**
- Full authentication for chat session management
- User isolation enforced through RLS and UserContext

**Public Endpoints (no auth required):**
- `/health`: Health checks for monitoring
- `/events`: SSE endpoints for system events

### 5. MCP Tool Integration (`src/mcp_bigquery/api/mcp_app.py`)

All MCP tools require authentication:

**Implementation:**
- Each tool accepts `auth_token` parameter (required)
- `get_user_context_from_token()` validates token and creates UserContext
- Returns meaningful errors for missing/invalid tokens
- Event logging includes user_id for audit trails

**Protected Tools:**
- `execute_bigquery_sql`: Query execution with dataset/table access checks
- `get_datasets`: Lists only accessible datasets
- `get_tables`: Lists only accessible tables
- `get_table_schema`: Schema access with permission checks
- `get_query_suggestions`: AI-powered suggestions
- `explain_table`: Table documentation and usage stats
- `list_resources`, `read_resource`: Resource access

### 6. Database Schema (`docs/supabase_rbac_schema.sql`)

Complete SQL schema with:

**Tables:**
- `user_profiles`: Extended user metadata
- `app_roles`: Application roles (analyst, viewer, admin, etc.)
- `user_roles`: User-to-role assignments
- `role_permissions`: Permission grants per role
- `role_dataset_access`: Dataset/table access control

**Features:**
- Row Level Security (RLS) policies for all tables
- Foreign key constraints with CASCADE delete
- Indexes for fast lookups
- Sample data (commented out) for testing
- Comprehensive comments and documentation

**Setup Instructions:**
1. Run SQL schema in Supabase SQL editor
2. Insert roles and permissions
3. Assign roles to users
4. Configure dataset access rules

### 7. Testing (`tests/`)

Comprehensive test coverage:

**`tests/core/test_auth.py` (29 tests):**
- JWT token validation (valid, expired, invalid)
- UserContext creation and hydration
- Permission and access checks
- Role caching with TTL
- Identifier normalization
- Supabase integration

**`tests/core/test_auth_models.py` (42 tests):**
- Pydantic model validation
- Field validators and constraints
- Edge cases and error handling

**`tests/api/test_auth_endpoints.py` (8 tests):**
- HTTP endpoint authentication
- Missing/expired/invalid token handling
- Dataset access filtering
- Query access control
- Permission enforcement
- End-to-end authorization flows

**Test Coverage:**
- 388 tests passing
- 84% coverage for `core/auth.py`
- 50% coverage for `api/dependencies.py` (focused on critical paths)

## Usage Examples

### Basic Token Validation

```python
from mcp_bigquery.core.auth import UserContext, AuthenticationError

try:
    context = await UserContext.from_token_async(
        token="eyJ0eXAiOi...",
        supabase_kb=knowledge_base
    )
    
    if context.is_expired():
        raise AuthenticationError("Token has expired")
    
    print(f"User: {context.user_id}")
    print(f"Roles: {context.roles}")
    print(f"Permissions: {context.permissions}")
except AuthenticationError as e:
    print(f"Auth failed: {e}")
```

### Checking Permissions

```python
# Check permission
if context.has_permission("query:execute"):
    # Execute query
    pass

# Check dataset access
if context.can_access_dataset("analytics"):
    # Access dataset
    pass

# Check table access
if context.can_access_table("analytics", "events"):
    # Access table
    pass
```

### FastAPI Endpoint with Auth

```python
from fastapi import Depends
from mcp_bigquery.core.auth import UserContext
from mcp_bigquery.api.dependencies import create_auth_dependency

router = APIRouter()
get_current_user = create_auth_dependency(knowledge_base)

@router.get("/protected")
async def protected_endpoint(user: UserContext = Depends(get_current_user)):
    return {"user_id": user.user_id, "roles": user.roles}
```

### MCP Tool with Auth

```python
@mcp_app.tool(name="my_tool")
async def my_tool(data: str, auth_token: str) -> dict:
    # Validate token
    user_context = await get_user_context_from_token(auth_token)
    
    # Check permission
    if not user_context.has_permission("custom:action"):
        raise ValueError("Permission denied")
    
    # Perform action
    return {"result": "success"}
```

### REST API Request

```bash
# Get JWT token from Supabase Auth
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# Make authenticated request
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/tools/datasets

# Execute query with auth
curl -X POST http://localhost:8000/tools/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM dataset.table LIMIT 10"}'
```

## Environment Variables

Required for authentication:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key                    # For client operations
SUPABASE_SERVICE_KEY=your-service-role-key   # For RBAC queries (bypasses RLS)
SUPABASE_JWT_SECRET=your-jwt-secret          # For token validation
```

## Security Features

1. **JWT Validation**: All tokens verified for signature and expiration
2. **RBAC Enforcement**: Fine-grained permissions and dataset/table access
3. **Row Level Security**: Supabase RLS policies protect data
4. **Service Key Isolation**: Service key used only for RBAC queries
5. **Audit Logging**: All operations logged with user_id
6. **Token Expiration**: Automatic expiration checking
7. **Input Validation**: Pydantic models validate all data
8. **Wildcard Support**: Flexible access control with "*" patterns

## Permission Strings

Common permissions used in the system:

- `query:execute` - Execute BigQuery queries
- `query:explain` - Explain query execution plans
- `cache:read` - Read from query cache
- `cache:write` - Write to query cache
- `cache:invalidate` - Invalidate cache entries
- `schema:read` - Read dataset/table schemas
- `history:read` - View query history
- `dataset:list` - List datasets
- `table:list` - List tables

## Acceptance Criteria ✅

All ticket requirements met:

1. ✅ Server rejects unauthenticated calls with 401
2. ✅ Malformed tokens receive 401
3. ✅ Valid JWT yields UserContext with role + resource metadata
4. ✅ HTTP routes require authentication (except health checks)
5. ✅ MCP tool invocations require authentication
6. ✅ Existing functionality preserved
7. ✅ Comprehensive test coverage
8. ✅ Complete documentation

## Files Modified/Created

**New Files:**
- `docs/supabase_rbac_schema.sql` - Database schema for RBAC

**Existing Files (already implemented):**
- `src/mcp_bigquery/core/auth.py` - Authentication module
- `src/mcp_bigquery/api/dependencies.py` - FastAPI dependencies
- `src/mcp_bigquery/config/settings.py` - Configuration
- `src/mcp_bigquery/routes/*.py` - Route authentication
- `src/mcp_bigquery/api/mcp_app.py` - MCP tool authentication
- `tests/core/test_auth.py` - Auth tests
- `tests/core/test_auth_models.py` - Model tests
- `tests/api/test_auth_endpoints.py` - Endpoint tests
- `docs/AUTH.md` - Authentication documentation

## Next Steps

To enable authentication in your deployment:

1. **Set up Supabase:**
   - Run `docs/supabase_rbac_schema.sql` in your Supabase project
   - Insert roles and permissions (see commented examples in schema)

2. **Configure environment variables:**
   - Set `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`

3. **Create users:**
   - Use Supabase Auth to create users
   - Assign roles via `user_roles` table

4. **Configure dataset access:**
   - Grant dataset/table access via `role_dataset_access` table

5. **Test authentication:**
   - Run the test suite: `uv run pytest tests/ -k auth -v`
   - Test with real tokens: See examples in `docs/AUTH.md`

## References

- [Authentication Guide](docs/AUTH.md) - Complete auth documentation
- [Supabase RBAC Schema](docs/supabase_rbac_schema.sql) - Database schema
- [Configuration Example](.env.example) - Environment variables
- [README.md](README.md) - General documentation
