# Database Schema Fixes

## Overview

This document describes the fixes applied to resolve database schema mismatches and RLS policy issues.

## Issues Fixed

### 1. Column Name Mismatch in chat_messages Table

**Problem**: Code was referencing `chat_session_id` but the actual column name in the database is `session_id`.

**Error**:
```
Error retrieving chat messages: {'message': 'column chat_messages.chat_session_id does not exist', 'code': '42703'}
```

**Fix**: Updated code to use `session_id` instead of `chat_session_id`:
- `src/mcp_bigquery/core/supabase_client.py` - Line 915
- `tests/core/test_supabase_chat_llm_usage.py` - Lines 232, 249, 250, 267

### 2. Missing RLS Policies for user_usage_stats Table

**Problem**: The `user_usage_stats` table only had a SELECT policy, causing INSERT operations to fail.

**Error**:
```
Error recording token usage: {'message': 'new row violates row-level security policy for table "user_usage_stats"', 'code': '42501'}
```

**Fix**: Added INSERT and UPDATE policies for authenticated users to manage their own usage stats.

**To apply the fix to your Supabase database**:
1. Open your Supabase project SQL Editor
2. Run the SQL file: `docs/fix_rls_policies.sql`
3. Verify policies are created by checking the output

### 3. SUPABASE_SERVICE_KEY Not Loaded in Streamlit App

**Problem**: The Streamlit configuration didn't include the `supabase_service_key` field, preventing RLS-protected operations from using the service key.

**Warning**:
```
WARNING: SupabaseKnowledgeBase initialized without service key. RLS-protected operations may fail.
```

**Fix**: Added `supabase_service_key` optional field to `StreamlitConfig`:
- `streamlit_app/config.py` - Line 44

## Environment Variables

Ensure the following environment variables are set in your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key  # Required for RLS bypass
SUPABASE_JWT_SECRET=your-jwt-secret

# Other required variables
PROJECT_ID=your-gcp-project-id
# ... (other variables)
```

**Note**: The `SUPABASE_SERVICE_KEY` is the service role key from your Supabase project settings. This key bypasses RLS policies and should be kept secure.

## Verification

After applying the fixes:

1. **Chat messages should load without errors**:
   ```
   ✅ No more "column chat_messages.chat_session_id does not exist" errors
   ✅ Chat history displays correctly
   ```

2. **Usage stats should record successfully**:
   ```
   ✅ No more "row violates row-level security policy" errors
   ✅ Token usage is recorded successfully
   ```

3. **Service key should load**:
   ```
   ✅ No more "initialized without service key" warnings
   ✅ Logs show "Using service key for Supabase"
   ```

## Database Schema Reference

The correct `chat_messages` table schema:

```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ordering INTEGER NOT NULL
);

CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_ordering ON chat_messages(session_id, ordering);
```

The correct `user_usage_stats` RLS policies:

```sql
-- SELECT policy
CREATE POLICY user_usage_stats_select_policy ON user_usage_stats
    FOR SELECT USING (auth.uid()::text = user_id);

-- INSERT policy (ADDED)
CREATE POLICY user_usage_stats_insert_policy ON user_usage_stats
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- UPDATE policy (ADDED)
CREATE POLICY user_usage_stats_update_policy ON user_usage_stats
    FOR UPDATE USING (auth.uid()::text = user_id);
```

## Additional Notes

- The `.env` file is automatically loaded by:
  - `src/mcp_bigquery/main.py` (line 5) for the MCP server
  - `streamlit_app/config.py` (via Pydantic BaseSettings) for the Streamlit app
  
- The service key should be used for operations that need to bypass RLS:
  - Creating chat sessions
  - Recording token usage
  - Admin operations

- Regular user operations should still use the anonymous key with JWT tokens for proper RLS enforcement.

## Testing

Run the test suite to verify the fixes:

```bash
uv run pytest tests/core/test_supabase_chat_llm_usage.py -v
```

All chat-related tests should pass.
