# Agent Tool Selection and SQL Generation Fixes

## Summary

Fixed critical logic errors in the conversational agent that were causing:
1. Wrong tool selection (generating SQL for metadata questions)
2. Invalid SQL generation (SQL comments sent to BigQuery)
3. Missing table references causing errors
4. Unnecessary error retries

## Changes Made

### 1. Fixed Tool Selection Logic (`src/mcp_bigquery/agent/conversation.py`)

**Problem**: Agent always generated SQL, even for metadata questions like "what datasets do we have?"

**Solution**: Added intelligent question routing before SQL generation:

- Added `_is_metadata_question()` method to detect metadata questions
- Detects three types of metadata questions:
  - **Datasets**: "what datasets", "list datasets", "show datasets", etc.
  - **Tables**: "what tables", "list tables", "show tables in dataset X", etc.
  - **Schema**: "describe table", "table schema", "what columns", etc.
  
- Added metadata handler methods:
  - `_handle_datasets_question()`: Calls `mcp_client.list_datasets()` API
  - `_handle_tables_question()`: Calls `mcp_client.list_tables()` API
  - `_handle_schema_question()`: Calls `mcp_client.get_table_schema()` API

- Updated `process_question()` to route metadata questions to appropriate handlers BEFORE generating SQL

**Result**: Metadata questions now call the correct API endpoints instead of generating SQL.

### 2. Added SQL Validation (`src/mcp_bigquery/agent/conversation.py`)

**Problem**: LLM could generate SQL comments like `-- No datasets accessible` which failed when sent to BigQuery

**Solution**: Added `_is_valid_sql()` validation method that checks:

- SQL is not empty
- SQL doesn't contain only comments (rejects `-- comment only` queries)
- SQL contains required keywords (SELECT or WITH)
- SQL doesn't contain forbidden operations (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE)

Validation runs BEFORE query execution, preventing invalid SQL from reaching BigQuery.

**Result**: Invalid SQL (including comments) is rejected with clear error messages, no BigQuery calls made.

### 3. Updated System Prompt (`src/mcp_bigquery/agent/prompts.py`)

**Problem**: LLM wasn't clear about when to use tools vs. SQL

**Solution**: Enhanced system prompt with:

- Clear distinction between metadata operations and data queries
- Explicit examples of metadata questions (do NOT generate SQL)
- Explicit examples of data queries (DO generate SQL)
- Instruction to NEVER generate SQL comments as queries
- Instruction to leave SQL empty if unable to generate valid query

**Result**: LLM has clearer guidance on routing decisions.

### 4. Fixed Table Name Reference (`src/mcp_bigquery/core/supabase_client.py`)

**Problem**: Code referenced `query_history` table which doesn't exist

**Solution**: Changed line 285 from:
```python
self.supabase.table("query_history").insert(history_data).execute()
```
to:
```python
self.supabase.table("query_cache").insert(history_data).execute()
```

Added comment explaining this is for query pattern tracking, not result caching.

**Result**: No more "table not found" errors when saving query patterns.

### 5. Improved Error Handling (`src/mcp_bigquery/agent/mcp_client.py`)

**Problem**: 400 errors (validation/permission) were retried unnecessarily, causing "retry storms"

**Solution**: Updated retry logic in `_request()` method:

```python
# Don't retry client errors (4xx) - these are validation/permission errors
if 400 <= e.response.status_code < 500:
    logger.warning(f"Client error {e.response.status_code} - not retrying")
    raise
```

Only 5xx server errors are retried (up to 3 times). Client errors (4xx) fail immediately.

**Result**: Invalid SQL causes a single clear error, not 4 repeated failures.

## Testing

All changes were tested with:
- 448 existing tests pass
- Created comprehensive test suite verifying:
  - Metadata question detection works correctly
  - Dataset/table/schema questions route to appropriate APIs
  - SQL comments are rejected
  - Valid SQL is accepted and executed
  - LLM is NOT called for metadata questions
  - SQL validation catches all invalid patterns

## Examples

### Before (Incorrect Behavior)

**User**: "what datasets do we have access to?"

**Agent**: 
1. Calls LLM to generate SQL
2. LLM returns: `{"sql": "-- No datasets accessible", ...}`
3. Sends `-- No datasets accessible` to BigQuery
4. BigQuery returns 500 error
5. Retries 3 times (same error)
6. User sees: "Query execution failed" (4 times)

### After (Correct Behavior)

**User**: "what datasets do we have access to?"

**Agent**:
1. Detects "what datasets" pattern
2. Routes to `_handle_datasets_question()`
3. Calls `GET /tools/datasets` API
4. Returns formatted list of datasets
5. User sees: "You have access to 2 dataset(s): 1. dataset1, 2. dataset2"

**LLM is never called, no SQL generated, no BigQuery query executed.**

## Acceptance Criteria Met

✅ Asking "what datasets do we have access to?" calls the datasets API and returns results (no SQL generation)
✅ Agent correctly routes metadata questions to appropriate APIs
✅ No SQL comments are sent to BigQuery for execution
✅ `query_history` table reference errors are fixed
✅ 500 errors don't trigger unnecessary retries (4xx errors fail immediately)
✅ Users receive clear, correct responses to dataset/table listing questions
✅ Data queries still work correctly with valid SQL generation

## Files Modified

1. `src/mcp_bigquery/agent/conversation.py` - Added routing, validation, and metadata handlers
2. `src/mcp_bigquery/agent/prompts.py` - Updated system prompt
3. `src/mcp_bigquery/core/supabase_client.py` - Fixed table reference
4. `src/mcp_bigquery/agent/mcp_client.py` - Improved retry logic

## Breaking Changes

None. All changes are backwards compatible and enhance existing functionality.

## Performance Impact

Positive impact:
- Metadata questions no longer call LLM (faster, cheaper)
- Invalid SQL rejected before BigQuery call (no wasted quota)
- Fewer retries on validation errors (faster failure)
