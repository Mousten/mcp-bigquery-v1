# Database Setup Guide

This guide provides comprehensive instructions for setting up the Supabase database schema for the MCP BigQuery Server.

## Overview

The MCP BigQuery Server uses Supabase (PostgreSQL) for:
- **Authentication & RBAC**: User management and role-based access control
- **Chat Persistence**: Conversation sessions and message history
- **Caching**: Query results and metadata caching
- **Usage Tracking**: Token consumption and request statistics
- **User Preferences**: Quotas and user-specific settings

## Quick Setup

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project
3. Wait for the database to be provisioned
4. Note your credentials from Settings > API:
   - **Project URL** (`SUPABASE_URL`)
   - **Anonymous Key** (`SUPABASE_KEY`)
   - **Service Role Key** (`SUPABASE_SERVICE_KEY`)
   - **JWT Secret** (`SUPABASE_JWT_SECRET` from JWT Settings)

### 2. Run Schema Migration

Execute the complete schema using the Supabase SQL Editor:

1. Open your Supabase project dashboard
2. Go to **SQL Editor** in the left sidebar
3. Click **New Query**
4. Copy and paste the contents of [`docs/supabase_complete_schema.sql`](./supabase_complete_schema.sql)
5. Click **Run** to execute

Alternatively, use `psql`:

```bash
psql -h db.your-project.supabase.co -U postgres -d postgres \
  -f docs/supabase_complete_schema.sql
```

### 3. Verify Installation

Check that all tables were created:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

Expected tables:
- `app_roles`
- `chat_messages`
- `chat_sessions`
- `metadata_cache`
- `query_cache`
- `role_dataset_access`
- `role_permissions`
- `user_preferences`
- `user_profiles`
- `user_roles`
- `user_usage_stats`

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION & RBAC                       │
└─────────────────────────────────────────────────────────────────────┘

    auth.users (Supabase Auth)
          │
          │ user_id
          ▼
    ┌─────────────┐
    │user_profiles│
    └─────────────┘
          │
          │ user_id
          ▼
    ┌─────────────┐       ┌────────────┐       ┌──────────────────┐
    │ user_roles  │──────▶│ app_roles  │──────▶│ role_permissions │
    └─────────────┘       └────────────┘       └──────────────────┘
          │                     │
          │                     │
          │                     ▼
          │               ┌─────────────────────┐
          │               │role_dataset_access  │
          │               └─────────────────────┘
          │
┌─────────────────────────────────────────────────────────────────────┐
│                         CHAT PERSISTENCE                            │
└─────────────────────────────────────────────────────────────────────┘
          │
          │ user_id
          ▼
    ┌─────────────┐
    │chat_sessions│
    └─────────────┘
          │
          │ session_id
          ▼
    ┌─────────────┐
    │chat_messages│
    └─────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         CACHING & USAGE                             │
└─────────────────────────────────────────────────────────────────────┘

    auth.users
          │
          │ user_id
          ├────────────────┬────────────────────┬──────────────────┐
          ▼                ▼                    ▼                  ▼
    ┌───────────┐    ┌─────────────┐    ┌──────────────┐   ┌──────────┐
    │query_cache│    │metadata_cache│   │user_usage_stats│  │user_prefs│
    └───────────┘    └─────────────┘    └──────────────┘   └──────────┘
```

### Table Descriptions

#### RBAC Tables

**`user_profiles`**
- **Purpose**: Extended user metadata beyond Supabase auth.users
- **Key Fields**: 
  - `user_id` (TEXT, PK) - Supabase auth user ID
  - `metadata` (JSONB) - Additional user metadata
- **Relationships**: Links to auth.users

**`app_roles`**
- **Purpose**: Define available application roles
- **Key Fields**:
  - `role_id` (TEXT, PK) - Unique role identifier (e.g., "role-analyst")
  - `role_name` (TEXT, UNIQUE) - Human-readable name (e.g., "analyst")
  - `description` (TEXT) - Role description
- **Example Roles**: analyst, viewer, admin

**`user_roles`**
- **Purpose**: Assign roles to users
- **Key Fields**:
  - `user_id` (TEXT, FK) - References auth.users
  - `role_id` (TEXT, FK) - References app_roles
  - `role_name` (TEXT) - Denormalized for fast lookups
- **Relationships**: Many-to-many bridge between users and roles

**`role_permissions`**
- **Purpose**: Define permissions for each role
- **Key Fields**:
  - `role_id` (TEXT, FK) - References app_roles
  - `permission` (TEXT) - Permission string (e.g., "query:execute", "cache:read")
- **Common Permissions**:
  - `query:execute` - Execute BigQuery queries
  - `cache:read` - Read from cache
  - `cache:write` - Write to cache
  - `cache:invalidate` - Clear cache
  - `schema:read` - Read dataset/table schemas

**`role_dataset_access`**
- **Purpose**: Control dataset/table access per role
- **Key Fields**:
  - `role_id` (TEXT, FK) - References app_roles
  - `dataset_id` (TEXT) - BigQuery dataset ID (use "*" for all)
  - `table_id` (TEXT, nullable) - BigQuery table ID (use "*" for all, NULL for dataset-level)
  - `access_level` (TEXT) - Access level (default: "read")
- **Wildcards**: Use `*` for dataset_id or table_id to grant broad access

#### Chat Persistence Tables

**`chat_sessions`**
- **Purpose**: Store conversation session metadata
- **Key Fields**:
  - `id` (UUID, PK) - Session identifier
  - `user_id` (TEXT, FK) - References auth.users
  - `title` (TEXT) - Session title (default: "New Conversation")
  - `created_at`, `updated_at` (TIMESTAMPTZ) - Timestamps
- **Ordering**: Sorted by `updated_at DESC` for most recent first

**`chat_messages`**
- **Purpose**: Store individual messages within sessions
- **Key Fields**:
  - `id` (UUID, PK) - Message identifier
  - `session_id` (UUID, FK) - References chat_sessions
  - `role` (TEXT) - Message role: "user", "assistant", or "system"
  - `content` (TEXT) - Message content
  - `metadata` (JSONB) - Additional data (model, tokens, etc.)
  - `ordering` (INTEGER) - Message sequence number
- **Ordering**: Sorted by `ordering` within each session
- **Trigger**: Automatically updates parent session's `updated_at` on insert

#### Caching Tables

**`query_cache`**
- **Purpose**: Cache BigQuery query results
- **Key Fields**:
  - `user_id` (TEXT) - Owner of cached entry (for isolation)
  - `query_hash` (TEXT) - SHA-256 hash of normalized SQL
  - `sql_text` (TEXT) - Original SQL query
  - `result_data` (JSONB) - Cached results
  - `expires_at` (TIMESTAMPTZ) - Cache expiration
  - `hit_count` (INTEGER) - Number of cache hits
- **Security**: User-scoped to prevent cross-user data leakage
- **Default TTL**: 24 hours

**`metadata_cache`**
- **Purpose**: Cache BigQuery metadata (schemas, datasets, tables)
- **Key Fields**:
  - `cache_key` (TEXT, UNIQUE) - Unique cache key
  - `cache_type` (TEXT) - Type of metadata (e.g., "dataset", "table_schema")
  - `metadata` (JSONB) - Cached metadata
  - `expires_at` (TIMESTAMPTZ) - Cache expiration
- **Sharing**: Shared across users (read-only metadata)
- **Default TTL**: 1 hour

#### Usage Tracking Tables

**`user_usage_stats`**
- **Purpose**: Track daily token consumption per user
- **Key Fields**:
  - `user_id` (TEXT) - User identifier
  - `period_start`, `period_end` (DATE) - Period dates
  - `tokens_consumed` (INTEGER) - Total tokens used
  - `requests_count` (INTEGER) - Total requests made
  - `metadata` (JSONB) - Provider/model breakdown
- **Metadata Structure**:
  ```json
  {
    "providers": {
      "openai": {
        "gpt-4o": {"tokens": 5000, "requests": 10},
        "gpt-4o-mini": {"tokens": 2000, "requests": 5}
      },
      "anthropic": {
        "claude-3-5-sonnet-20241022": {"tokens": 3000, "requests": 8}
      }
    }
  }
  ```
- **Aggregation**: Daily records with unique constraint on (user_id, period_start)

**`user_preferences`**
- **Purpose**: Store user preferences and token quotas
- **Key Fields**:
  - `user_id` (TEXT, PK) - User identifier
  - `preferences` (JSONB) - User preferences
- **Preferences Structure**:
  ```json
  {
    "daily_token_quota": 10000,
    "monthly_token_quota": 100000,
    "default_llm_provider": "openai",
    "default_llm_model": "gpt-4o"
  }
  ```

### Row Level Security (RLS)

All tables include RLS policies to ensure data isolation:

**User Isolation**:
- Users can only access their own data (profiles, sessions, messages, cache, usage stats)
- Enforced via `auth.uid()::text = user_id` checks

**Role-Based Access**:
- Users can read roles, permissions, and dataset access for their assigned roles
- Enforced via `EXISTS` subqueries checking `user_roles`

**Shared Resources**:
- App roles are readable by all authenticated users (for discovery)
- Metadata cache is readable by all authenticated users (read-only metadata)

**Service Key Bypass**:
- The `SUPABASE_SERVICE_KEY` bypasses RLS for server operations
- Used by the MCP server for administrative tasks and RBAC operations

## Initial Configuration

### 1. Create Sample Roles

Uncomment and run the sample data section in `supabase_complete_schema.sql`:

```sql
-- Create roles
INSERT INTO app_roles (role_id, role_name, description) VALUES
    ('role-analyst', 'analyst', 'Data analyst with query execution permissions'),
    ('role-viewer', 'viewer', 'Read-only viewer with limited access'),
    ('role-admin', 'admin', 'Administrator with full access');

-- Create permissions
INSERT INTO role_permissions (role_id, permission, description) VALUES
    ('role-analyst', 'query:execute', 'Execute BigQuery queries'),
    ('role-analyst', 'cache:read', 'Read from query cache'),
    ('role-analyst', 'cache:write', 'Write to query cache'),
    ('role-analyst', 'schema:read', 'Read dataset/table schemas'),
    ('role-viewer', 'schema:read', 'Read dataset/table schemas'),
    ('role-admin', 'query:execute', 'Execute BigQuery queries'),
    ('role-admin', 'cache:read', 'Read from query cache'),
    ('role-admin', 'cache:write', 'Write to query cache'),
    ('role-admin', 'cache:invalidate', 'Invalidate cache entries'),
    ('role-admin', 'schema:read', 'Read dataset/table schemas');

-- Create dataset access
INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level) VALUES
    ('role-analyst', 'public_data', NULL, 'read'),
    ('role-analyst', 'analytics', 'events', 'read'),
    ('role-viewer', 'public_data', NULL, 'read'),
    ('role-admin', '*', NULL, 'read');  -- Admin has access to all datasets
```

### 2. Assign User Roles

After users sign up via Supabase Auth, assign them roles:

```sql
-- Get user ID from Supabase Auth
SELECT id, email FROM auth.users;

-- Assign analyst role to user
INSERT INTO user_roles (user_id, role_id, role_name) 
VALUES ('[user-id-from-auth]', 'role-analyst', 'analyst');

-- Set user preferences and quotas
INSERT INTO user_preferences (user_id, preferences)
VALUES ('[user-id-from-auth]', '{
  "daily_token_quota": 10000,
  "monthly_token_quota": 100000,
  "default_llm_provider": "openai"
}');
```

### 3. Configure Dataset Access

Grant users access to specific datasets:

```sql
-- Grant access to specific dataset
INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level)
VALUES ('role-analyst', 'sales_data', NULL, 'read');

-- Grant access to specific table
INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level)
VALUES ('role-analyst', 'analytics', 'user_events', 'read');

-- Grant access to all datasets (wildcard)
INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level)
VALUES ('role-admin', '*', NULL, 'read');
```

## Maintenance

### Monitoring

```sql
-- Check active users with roles
SELECT u.email, ur.role_name, r.description
FROM auth.users u
JOIN user_roles ur ON u.id::text = ur.user_id
JOIN app_roles r ON ur.role_id = r.role_id;

-- Check token usage by user
SELECT u.email, 
       SUM(uus.tokens_consumed) as total_tokens,
       SUM(uus.requests_count) as total_requests
FROM auth.users u
JOIN user_usage_stats uus ON u.id::text = uus.user_id
WHERE uus.period_start >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.email
ORDER BY total_tokens DESC;

-- Check cache statistics
SELECT 
    COUNT(*) as total_entries,
    SUM(hit_count) as total_hits,
    AVG(hit_count) as avg_hits_per_entry
FROM query_cache
WHERE expires_at > NOW();
```

### Cleanup

```sql
-- Remove expired cache entries
DELETE FROM query_cache WHERE expires_at < NOW();
DELETE FROM metadata_cache WHERE expires_at < NOW();

-- Remove old usage statistics (keep last 90 days)
DELETE FROM user_usage_stats 
WHERE period_start < CURRENT_DATE - INTERVAL '90 days';

-- Remove inactive sessions (no messages in 30 days)
DELETE FROM chat_sessions 
WHERE updated_at < NOW() - INTERVAL '30 days';
```

## Backup & Recovery

### Backup

```bash
# Backup entire database
pg_dump -h db.your-project.supabase.co -U postgres -d postgres \
  -F c -f backup.dump

# Backup specific tables
pg_dump -h db.your-project.supabase.co -U postgres -d postgres \
  -t user_roles -t role_permissions -t role_dataset_access \
  -F c -f rbac_backup.dump
```

### Restore

```bash
# Restore from backup
pg_restore -h db.your-project.supabase.co -U postgres -d postgres \
  -c backup.dump
```

## Troubleshooting

### Common Issues

**RLS Policy Violations:**
- Ensure you're using `SUPABASE_SERVICE_KEY` for server operations
- Check that RLS policies are correctly configured
- Verify user has been assigned at least one role

**Missing Tables:**
- Re-run the complete schema SQL
- Check for errors in the SQL execution log
- Verify all migrations completed successfully

**Performance Issues:**
- Ensure indexes are created (check with `\d+ table_name`)
- Run `ANALYZE` on tables after bulk inserts
- Consider partitioning `user_usage_stats` by period for large datasets

**Cache Not Working:**
- Verify `query_cache` and `metadata_cache` tables exist
- Check cache expiration times are reasonable
- Ensure user_id is being passed for query cache lookups

## See Also

- [Authentication & RBAC Guide](./AUTH.md)
- [Chat Persistence API](./CHAT_PERSISTENCE.md)
- [Complete Schema SQL](./supabase_complete_schema.sql)
