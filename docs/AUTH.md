# Authentication and Authorization

This document describes the Supabase-backed authentication and RBAC (Role-Based Access Control) system.

## Overview

The authentication layer provides JWT-based authentication using Supabase tokens and role-based access control for BigQuery datasets and tables. All configuration and data models use **Pydantic v2** for robust validation and type safety.

## Environment Variables

Configure authentication by setting these environment variables:

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_KEY`: Supabase service role key (for RBAC queries)
- `SUPABASE_JWT_SECRET`: JWT secret for validating Supabase tokens

## Pydantic Models

The auth system uses Pydantic v2 models for validation:

- **`UserContext`**: Main user context with authentication and authorization data
- **`UserProfile`**: User profile data from Supabase
- **`UserRole`**: User role assignment
- **`RolePermission`**: Permission associated with a role
- **`DatasetAccess`**: Dataset/table access rule for a role

All models provide automatic validation, type checking, and serialization.

## Database Schema

The following Supabase tables are required for RBAC. See `docs/supabase_rbac_schema.sql` for the complete SQL schema with indexes, constraints, and RLS policies.

### `user_profiles`
- `user_id` (text, primary key): User ID from Supabase auth
- `metadata` (jsonb): Additional user metadata
- `created_at` (timestamp, optional): Profile creation timestamp
- `updated_at` (timestamp, optional): Last update timestamp

### `app_roles`
- `role_id` (text, primary key): Unique role identifier
- `role_name` (text): Role display name
- `description` (text, optional): Role description

### `user_roles`
- `user_id` (text): User ID
- `role_id` (text): Role identifier (references app_roles)
- `role_name` (text): Role display name
- `assigned_at` (timestamp, optional): Role assignment timestamp

### `role_permissions`
- `role_id` (text): Role identifier (references app_roles)
- `permission` (text): Permission string (e.g., "query:execute", "cache:read")
- `description` (text, optional): Permission description

### `role_dataset_access`
- `role_id` (text): Role identifier (references app_roles)
- `dataset_id` (text): BigQuery dataset identifier (use "*" for wildcard)
- `table_id` (text, optional): BigQuery table identifier (use "*" for wildcard, null for all tables)
- `access_level` (text, optional): Access level (default: "read")

**Setup Instructions:**
1. Run the SQL schema in your Supabase project: `docs/supabase_rbac_schema.sql`
2. Insert sample roles and permissions (see commented examples in schema file)
3. Assign roles to users via the `user_roles` table
4. Configure dataset access via the `role_dataset_access` table

## Usage

### Validating Tokens

```python
from mcp_bigquery.core.auth import UserContext, AuthenticationError

try:
    # Synchronous (without role hydration)
    context = UserContext.from_token(token, jwt_secret="your-secret")
    print(f"User: {context.user_id}, Email: {context.email}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
```

### Loading Roles and Permissions

```python
from mcp_bigquery.core.auth import UserContext
from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase

# Initialize Supabase client
kb = SupabaseKnowledgeBase()

# Create context with full role/permission hydration
context = await UserContext.from_token_async(
    token=token,
    jwt_secret="your-secret",
    supabase_kb=kb
)

# Check permissions
if context.has_permission("query:execute"):
    print("User can execute queries")

# Check dataset access
if context.can_access_dataset("public_data"):
    print("User can access public_data dataset")

# Check table access
if context.can_access_table("analytics", "events"):
    print("User can access analytics.events table")
```

### Checking Access in Handlers

```python
async def execute_query(sql: str, token: str):
    # Validate token and load user context
    context = await UserContext.from_token_async(
        token=token,
        supabase_kb=kb
    )
    
    # Check if token is expired
    if context.is_expired():
        raise AuthenticationError("Token has expired")
    
    # Check permission
    if not context.has_permission("query:execute"):
        raise AuthorizationError("User lacks query:execute permission")
    
    # Extract tables from SQL and verify access
    tables = extract_tables_from_sql(sql)
    for table in tables:
        dataset, table_name = extract_dataset_table_from_path(table)
        if not context.can_access_table(dataset, table_name):
            raise AuthorizationError(f"Access denied to {table}")
    
    # Execute query...
```

## Caching

Role and permission data is cached in-memory for 5 minutes to reduce database round trips. The cache can be cleared manually:

```python
from mcp_bigquery.core.auth import clear_role_cache

clear_role_cache()
```

## Error Handling

The auth module defines two exception types:

- `AuthenticationError`: Raised when token validation fails (invalid, expired, or malformed tokens)
- `AuthorizationError`: Raised when user lacks required permissions

Handlers should catch these and translate them to appropriate HTTP status codes:

- `AuthenticationError` → HTTP 401 Unauthorized
- `AuthorizationError` → HTTP 403 Forbidden

### Pydantic Validation Errors

When creating models with invalid data, Pydantic will raise `ValidationError`:

```python
from pydantic import ValidationError
from mcp_bigquery.core.auth import UserContext

try:
    # This will fail - empty user_id
    context = UserContext(user_id="")
except ValidationError as e:
    print(f"Validation error: {e}")
    # Handle validation errors appropriately
```

Common validation errors:
- Empty or whitespace-only `user_id`
- Invalid email format (missing '@')
- Empty or whitespace-only `dataset_id` in access rules

## Permissions

Common permission strings:

- `query:execute` - Execute BigQuery queries
- `query:explain` - Explain query execution plans
- `cache:read` - Read from query cache
- `cache:write` - Write to query cache
- `cache:invalidate` - Invalidate cache entries
- `schema:read` - Read dataset/table schemas
- `history:read` - View query history

## Identifier Normalization

Dataset and table identifiers are normalized for consistent comparison:

- Backticks are removed: `` `my-dataset` `` → `my-dataset`
- Converted to lowercase: `MyDataset` → `mydataset`
- Whitespace is trimmed

Wildcard access:
- `*` in `allowed_datasets` grants access to all datasets
- `*` in `allowed_tables[dataset]` grants access to all tables in that dataset
