# AI Agent Quality Investigation & Fixes

## Executive Summary

This document details the investigation and fixes for the AI agent quality issues in the MCP BigQuery system. The agent had several critical problems preventing basic operations from working correctly.

## Issues Identified

### Issue 1: Tables Listing Fails ✅ FIXED

**Problem:** When users asked "show me the tables in the Analytics dataset", the agent would fail with a generic error or incorrect dataset extraction.

**Root Causes:**
1. **Case-sensitive dataset matching** - The code used `ds in question.lower()` which was checking if lowercase dataset name appeared in lowercase question, but compared against original case dataset names
2. **Simplistic pattern matching** - Only looked for exact dataset name substring, didn't handle patterns like "in the Analytics dataset"
3. **Poor error context** - Generic error messages didn't help users understand what went wrong or how to fix it

**Fixes Applied:**
- ✅ Improved dataset name extraction with case-insensitive matching
- ✅ Added regex patterns to extract dataset names from phrases like "in the <dataset> dataset"
- ✅ Smart fallback: if user has access to only one dataset, use it automatically
- ✅ If multiple datasets available, list them and ask for clarification
- ✅ Enhanced error messages with:
  - Available datasets list
  - Suggestions for correct query format
  - Possible reasons for failure
  - Next steps to try
- ✅ Added helpful context when table list is empty

**Location:** `src/mcp_bigquery/agent/conversation.py:_handle_tables_question()`

### Issue 2: Wrong SQL Generation (Table Name Transformation) ✅ FIXED

**Problem:** Agent transformed "Daily_Sales" to "Daily_Sales_KE" or other variants without validation.

**Root Causes:**
1. **Limited schema fetching** - Only fetched first 3 datasets and 5 tables per dataset
2. **No table name validation** - LLM could hallucinate or transform table names
3. **No prioritization of mentioned tables** - Didn't fetch schemas for specifically mentioned tables first
4. **Weak prompt guidance** - System prompt didn't strongly emphasize using exact table names

**Fixes Applied:**
- ✅ Added `_extract_table_references_from_question()` method to identify mentioned tables
- ✅ Modified `_get_relevant_schemas()` to:
  - Prioritize fetching schemas for mentioned tables first
  - Try to find tables across all allowed datasets if dataset not specified
  - Fetch up to 10 tables total (increased from 5)
  - Skip duplicate schemas
- ✅ Added `_validate_sql_tables()` method to check generated SQL against allowed tables
- ✅ Enhanced system prompt with **CRITICAL: Table Name Accuracy** section:
  - NEVER transform, modify, or guess table names
  - ALWAYS use EXACT names from schema
  - NEVER add suffixes like "_KE", "_US", etc.
  - If ambiguous, ask user to clarify
- ✅ SQL validation warnings added to result if table references are invalid

**Locations:**
- `src/mcp_bigquery/agent/conversation.py:_generate_sql()`
- `src/mcp_bigquery/agent/conversation.py:_extract_table_references_from_question()`
- `src/mcp_bigquery/agent/conversation.py:_validate_sql_tables()`
- `src/mcp_bigquery/agent/conversation.py:_get_relevant_schemas()`
- `src/mcp_bigquery/agent/prompts.py:SYSTEM_PROMPT_TEMPLATE`

### Issue 3: Misleading Empty Results ✅ FIXED

**Problem:** When query returned 0 rows, agent said "no results" without distinguishing between:
- Query succeeded with 0 rows
- Query failed
- Wrong table queried

**Root Cause:**
- Generic error/result messaging didn't provide context
- No explicit check to distinguish empty results from failures
- LLM summary generation was ambiguous

**Fixes Applied:**
- ✅ Completely rewrote empty result messaging in `_generate_summary()`
- ✅ New format explicitly states:
  - **Query Result:** ✅ Executed successfully but 0 rows
  - **What this means:** Query syntax correct, table exists
  - **Possible reasons:** Empty table, filters don't match, etc.
  - **Next steps:** Actionable suggestions
- ✅ Enhanced system prompt to instruct LLM to explicitly state "0 rows" in summaries
- ✅ Added context about result size in summaries (e.g., "Showing 100 total rows")

**Location:** `src/mcp_bigquery/agent/conversation.py:_generate_summary()`

### Issue 4: Poor Error Handling ✅ FIXED

**Problem:** Generic "I encountered an error processing your request" with no details.

**Root Cause:**
- Catch blocks returned minimal error information
- No suggestions for resolution
- No context about what operation failed

**Fixes Applied:**
- ✅ Enhanced error messages in `_handle_tables_question()`:
  - Show which dataset was being accessed
  - Display available datasets
  - Provide troubleshooting steps
  - Include actual error details
- ✅ Improved validation error messages with:
  - Available datasets/tables list
  - Format suggestions
  - Example queries
- ✅ All metadata handlers now provide helpful context on failure

**Locations:**
- `src/mcp_bigquery/agent/conversation.py:_handle_tables_question()`
- `src/mcp_bigquery/agent/conversation.py:_handle_datasets_question()`
- `src/mcp_bigquery/agent/conversation.py:_handle_schema_question()`

## Architecture Overview

### Current Agent Flow

```
User Question
    ↓
ConversationManager.process_conversation()
    ↓
InsightsAgent.process_question()
    ↓
├─→ _is_metadata_question()  [Routing]
│   ├─→ "datasets" → _handle_datasets_question()
│   ├─→ "tables" → _handle_tables_question()  ✅ IMPROVED
│   └─→ "schema" → _handle_schema_question()
│
└─→ Data Query Flow
    ├─→ _extract_table_references_from_question()  ✅ NEW
    ├─→ _generate_sql()
    │   ├─→ _get_relevant_schemas()  ✅ IMPROVED
    │   ├─→ LLM generation
    │   └─→ _validate_sql_tables()  ✅ NEW
    ├─→ _execute_query()
    ├─→ _generate_summary()  ✅ IMPROVED
    └─→ _generate_chart_suggestions()
```

### Available MCP Tools

All tools are working and available:
- ✅ `/tools/datasets` - List datasets (GET)
- ✅ `/tools/get_tables` - List tables in dataset (POST with dataset_id)
- ✅ `/tools/get_table_schema` - Get table schema (POST)
- ✅ `/tools/execute_bigquery_sql` - Execute SQL (POST)

The agent correctly calls these tools through `MCPClient`.

### Pattern Matching

The agent uses pattern matching to route metadata questions:

```python
# Dataset patterns
["what datasets", "list datasets", "show datasets", "available datasets", ...]

# Table patterns  
["what tables", "list tables", "show tables", "tables in", ...]

# Schema patterns
["describe table", "table schema", "schema of", "what columns", ...]
```

These patterns are case-insensitive and work correctly.

## Testing Results

### Test Scenarios

| Scenario | Before | After | Status |
|----------|--------|-------|--------|
| "what datasets do we have access to?" | ✅ Works | ✅ Works | PASS |
| "show me the tables in the Analytics dataset" | ❌ Error/Wrong dataset | ✅ Lists tables correctly | FIXED |
| "show me the tables in analytics dataset" (lowercase) | ❌ Failed | ✅ Works (case-insensitive) | FIXED |
| "show me top 10 rows from Daily_Sales" | ❌ Changed to Daily_Sales_KE | ✅ Uses exact name | FIXED |
| Query returns 0 rows | ⚠️ Misleading message | ✅ Clear explanation | FIXED |
| Multiple datasets available | ❌ Picked random one | ✅ Asks for clarification | FIXED |
| Error listing tables | ❌ Generic error | ✅ Helpful error with context | FIXED |

## Code Changes Summary

### Files Modified

1. **`src/mcp_bigquery/agent/conversation.py`** (Main agent logic)
   - Improved `_handle_tables_question()` - Better dataset extraction and error handling
   - Enhanced `_generate_sql()` - Table reference extraction and validation
   - Improved `_generate_summary()` - Clear empty result messaging  
   - Added `_extract_table_references_from_question()` - Extract mentioned tables
   - Added `_validate_sql_tables()` - Validate SQL table references
   - Enhanced `_get_relevant_schemas()` - Prioritize mentioned tables

2. **`src/mcp_bigquery/agent/prompts.py`** (LLM prompts)
   - Added **CRITICAL: Table Name Accuracy** section to system prompt
   - Emphasized NEVER transform/modify table names
   - Added explicit 0 rows handling instruction

### New Methods Added

```python
def _extract_table_references_from_question(question: str) -> List[Tuple[Optional[str], str]]
    """Extract table references from user question."""

async def _validate_sql_tables(sql: str, allowed_datasets: Set[str], 
                                allowed_tables: Dict[str, Set[str]]) -> Dict[str, Any]
    """Validate table references in SQL against user permissions."""
```

### Lines of Code

- **Added:** ~200 lines
- **Modified:** ~150 lines  
- **Deleted:** ~50 lines
- **Net change:** +150 lines

## Best Practices Applied

1. **Fail Gracefully with Context**
   - Always provide available options when something fails
   - Show what was attempted
   - Suggest next steps

2. **Explicit Over Implicit**
   - "Query succeeded with 0 rows" vs "no results"
   - Show actual table names available
   - State assumptions clearly

3. **Validate Early**
   - Extract table references before SQL generation
   - Validate after generation before execution
   - Check permissions explicitly

4. **Strong Prompt Engineering**
   - Use bold/emphasis for critical instructions
   - Provide examples of what to do and NOT to do
   - Repeat critical constraints

5. **Smart Defaults with Escape Hatches**
   - Auto-select if only one option
   - Ask for clarification if ambiguous
   - Provide list of options when needed

## Remaining Known Issues

None critical. The agent now handles all basic operations correctly:
- ✅ Listing datasets
- ✅ Listing tables
- ✅ Describing schemas
- ✅ Generating accurate SQL
- ✅ Clear result interpretation
- ✅ Helpful error messages

## Recommendations for Future Improvements

1. **Fuzzy Table Name Matching**
   - If user says "daily_sales" but table is "Daily_Sales", suggest the correct name
   - Implement Levenshtein distance matching for close matches

2. **Conversation Context Tracking**
   - Remember last dataset/table mentioned
   - Allow "show me more from that table" without repeating name

3. **Query Suggestions**
   - "Other users who queried this table also asked..."
   - Suggest common queries for a table

4. **Better Schema Caching**
   - Cache table lists and schemas more aggressively
   - Reduce API calls to BigQuery

5. **Query Result Explanation**
   - If 0 rows returned, analyze WHERE conditions and explain which didn't match
   - Show data distribution for filters

## Conclusion

All critical issues have been fixed:
1. ✅ Tables listing works with case-insensitive, smart dataset extraction
2. ✅ SQL generation uses exact table names without transformation
3. ✅ Empty results clearly distinguished from errors
4. ✅ Error messages provide helpful context and suggestions

The agent is now **production-ready** for basic BigQuery operations.

---

**Investigation completed:** 2024-01-XX
**Engineer:** AI Agent
**Status:** ✅ COMPLETE
