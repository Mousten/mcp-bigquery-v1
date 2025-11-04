# Database Schema Fixes - Changelog

## Summary

Fixed multiple database schema mismatches and RLS policy issues that were causing errors in chat persistence and token usage tracking.

## Changes Made

### 1. Fixed Column Name Mismatch in chat_messages Table

**Files Modified:**
- `src/mcp_bigquery/core/supabase_client.py`
  - Line 915: Changed `.eq("chat_session_id", session_id)` to `.eq("session_id", session_id)` in `get_chat_messages()`
  - Lines 827-832: Updated docstring to reflect correct schema
  - Lines 851-869: Updated `append_chat_message()` to use `session_id` and include `ordering` field
- `tests/core/test_supabase_chat_llm_usage.py`
  - Line 232: Changed `"chat_session_id"` to `"session_id"` in test data
  - Line 249: Updated assertion to check `"session_id"` instead of `"chat_session_id"`
  - Line 250: Updated mock assertion to verify `"session_id"` parameter
  - Line 267: Changed `"chat_session_id"` to `"session_id"` in test data
- `docs/chat_llm_usage_examples.md`
  - Lines 310-322: Updated schema documentation to show `session_id` instead of `chat_session_id`

### 2. Added Missing RLS Policies for user_usage_stats

**Files Modified:**
- `docs/supabase_complete_schema.sql`
  - Lines 331-335: Added INSERT and UPDATE RLS policies for `user_usage_stats` table
  - Line 361: Changed `GRANT SELECT` to `GRANT ALL` on `user_usage_stats` for authenticated users

**Files Created:**
- `docs/fix_rls_policies.sql` - Standalone migration script to add missing RLS policies

### 3. Added SUPABASE_SERVICE_KEY Support to Streamlit Config

**Files Modified:**
- `streamlit_app/config.py`
  - Line 15: Added documentation for `SUPABASE_SERVICE_KEY` environment variable
  - Line 44: Added `supabase_service_key` optional field to `StreamlitConfig` class

### 4. Documentation Updates

**Files Created:**
- `docs/FIX_DATABASE_ISSUES.md` - Comprehensive guide describing all issues and fixes
- `docs/fix_rls_policies.sql` - SQL migration script for RLS policy fixes
- `CHANGELOG_DB_FIXES.md` - This file

## Testing

All tests pass successfully:
```bash
uv run pytest tests/core/test_supabase_chat_llm_usage.py -v
# Result: 31 passed, 2 warnings in 1.65s
```

## Migration Steps for Users

### For Code Changes
The code changes are backward-compatible and require no action from users running the updated code.

### For Database Changes
Users must run the following SQL in their Supabase SQL Editor to add missing RLS policies:

```sql
-- Add INSERT policy for user_usage_stats
CREATE POLICY user_usage_stats_insert_policy ON user_usage_stats
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- Add UPDATE policy for user_usage_stats
CREATE POLICY user_usage_stats_update_policy ON user_usage_stats
    FOR UPDATE USING (auth.uid()::text = user_id);

-- Grant INSERT/UPDATE permissions
GRANT INSERT, UPDATE ON user_usage_stats TO authenticated;
```

Or simply run the migration file:
```bash
# In Supabase SQL Editor, run: docs/fix_rls_policies.sql
```

### For Environment Variables
Add to `.env` file if not already present:
```bash
SUPABASE_SERVICE_KEY=your-service-role-key
```

## Errors Fixed

### Before Fixes
```
❌ Error retrieving chat messages: {'message': 'column chat_messages.chat_session_id does not exist', 'code': '42703'}
❌ Error recording token usage: {'message': 'new row violates row-level security policy for table "user_usage_stats"', 'code': '42501'}
❌ WARNING: SupabaseKnowledgeBase initialized without service key. RLS-protected operations may fail.
```

### After Fixes
```
✅ Chat messages load successfully
✅ Token usage records successfully
✅ Service key loads from environment
✅ All operations work with proper RLS enforcement
```

## Impact Assessment

**Breaking Changes:** None - All changes are backward-compatible

**Required User Action:** 
1. Run SQL migration (one-time): `docs/fix_rls_policies.sql`
2. Add `SUPABASE_SERVICE_KEY` to `.env` file (recommended)

**Benefits:**
- Chat history now loads correctly
- Token usage tracking works properly
- Better RLS policy enforcement
- Improved error handling and logging

## Verification

To verify the fixes work in your environment:

1. **Test chat persistence:**
   ```python
   from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase
   kb = SupabaseKnowledgeBase()
   messages = await kb.get_chat_messages(session_id="your-session-id")
   # Should return messages without errors
   ```

2. **Test token usage:**
   ```python
   success = await kb.record_token_usage(
       user_id="user-123",
       tokens_consumed=100,
       provider="openai",
       model="gpt-4"
   )
   # Should return True
   ```

3. **Check logs:**
   Look for:
   - ✅ "Supabase connection verified. Using service key"
   - ✅ No "column does not exist" errors
   - ✅ No "row violates RLS policy" errors

## Related Documentation

- [FIX_DATABASE_ISSUES.md](docs/FIX_DATABASE_ISSUES.md) - Detailed issue description and solutions
- [fix_rls_policies.sql](docs/fix_rls_policies.sql) - SQL migration script
- [chat_llm_usage_examples.md](docs/chat_llm_usage_examples.md) - Updated usage examples
- [supabase_complete_schema.sql](docs/supabase_complete_schema.sql) - Complete schema with fixes

## Commit Message

```
fix: correct chat_messages column name and add missing RLS policies

- Fixed column name mismatch: chat_session_id -> session_id
- Added INSERT and UPDATE RLS policies for user_usage_stats
- Added SUPABASE_SERVICE_KEY support to Streamlit config
- Updated documentation and tests
- All tests passing (31/31)

Fixes:
- Chat message retrieval errors (42703)
- Token usage RLS violations (42501)
- Service key loading warnings

Migration required: Run docs/fix_rls_policies.sql in Supabase
```
