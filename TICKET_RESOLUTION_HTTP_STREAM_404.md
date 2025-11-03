# Ticket Resolution: HTTP-Stream Transport Mode 404s

## Issue
Tool endpoints were returning 404 when the MCP server ran in `http-stream` transport mode:
```bash
GET /tools/datasets → 404 Not Found
POST /tools/execute_bigquery_sql → 404 Not Found
```

Meanwhile, chat endpoints worked correctly:
```bash
GET /stream/chat/sessions → 200 OK
POST /stream/chat/sessions/{id}/messages → 200 OK
```

## Root Cause Analysis

### What We Found
In `http-stream` transport mode, all routers (including tools) were registered with a `/stream` prefix:

```python
# src/mcp_bigquery/main.py (lines 88-95)
fastapi_app.include_router(resources_router, prefix="/stream")
fastapi_app.include_router(tools_router, prefix="/stream")  # <-- Tools at /stream/tools/*
fastapi_app.include_router(chat_router, prefix="/stream")
```

This meant:
- Tool endpoints existed at `/stream/tools/datasets`, not `/tools/datasets`
- Chat endpoints existed at `/stream/chat/sessions`
- Clients accessing `/tools/*` got 404 because those paths didn't exist

### Why Chat Worked But Tools Didn't
The Streamlit `SessionManager` correctly used `/stream/chat/sessions` paths, so chat worked.
Clients trying to access tools at `/tools/*` got 404s because they didn't know about the `/stream` prefix.

### Was This A Bug?
**No**, this was intentional design. The `/stream` prefix serves to:
1. Namespace all streaming transport routes
2. Support NDJSON streaming at `/stream/ndjson/`
3. Keep streaming routes separate from potential other routes

However, the documentation didn't make this clear enough, leading to confusion.

## Solution Implemented

### 1. ✅ Enhanced Documentation
Updated `HTTP_ENDPOINTS_DOCUMENTATION.md` with:
- Clear transport mode comparison table
- Prominent warnings about path differences
- Transport-specific code examples
- Comprehensive troubleshooting section for 404s
- Quick reference card with all paths

### 2. ✅ Backwards Compatibility
Modified `src/mcp_bigquery/main.py` to register tools router TWICE in http-stream mode:
```python
# Include routers under the /stream base (primary path)
fastapi_app.include_router(tools_router, prefix="/stream")

# Also include tools without prefix for backwards compatibility
fastapi_app.include_router(tools_router)
```

**Result:** In http-stream mode, tools are now accessible at BOTH:
- `/stream/tools/*` (recommended, primary path)
- `/tools/*` (backwards compatible)

This prevents 404s for clients that haven't been updated to use the `/stream` prefix.

### 3. ✅ Investigation Documentation
Created comprehensive investigation documentation:
- `INVESTIGATION_404_HTTP_STREAM.md`: Full technical analysis
- `TICKET_RESOLUTION_HTTP_STREAM_404.md`: This summary
- Test scripts demonstrating the fix

## Changes Made

### Modified Files
1. **`src/mcp_bigquery/main.py`** (line 100)
   - Added backwards-compatible tools router registration without prefix
   - Added TODO comment about future deprecation

2. **`HTTP_ENDPOINTS_DOCUMENTATION.md`**
   - Enhanced transport mode section with comparison table
   - Added prominent warnings about path differences
   - Added HTTP-Stream mode code examples
   - Rewrote 404 troubleshooting section
   - Updated summary with quick reference card

### New Files
1. **`INVESTIGATION_404_HTTP_STREAM.md`** - Full investigation report
2. **`TICKET_RESOLUTION_HTTP_STREAM_404.md`** - This resolution summary
3. **`test_http_stream_routes.py`** - Test demonstrating backwards compatibility

## Testing

### Verification Test
Created `test_http_stream_routes.py` that verifies tools are registered at both paths:

```
HTTP-STREAM MODE ROUTES WITH BACKWARDS COMPATIBILITY
================================================================================
Tools available at /stream/tools/* (PRIMARY):
  POST                 /stream/tools/execute_bigquery_sql
  GET                  /stream/tools/datasets
  ...

Tools ALSO available at /tools/* (BACKWARDS COMPATIBLE):
  POST                 /tools/execute_bigquery_sql
  GET                  /tools/datasets
  ...
```

### Manual Testing
```bash
# Start server in http-stream mode
uv run mcp-bigquery --transport http-stream --port 8000

# Both paths now work:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/stream/tools/datasets  # ✅
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets         # ✅
```

## Impact

### Before Fix
- ❌ Clients using `/tools/*` paths got 404 in http-stream mode
- ⚠️ Required all clients to be updated to use `/stream/tools/*`
- ⚠️ Documentation didn't clearly explain the path differences
- ⚠️ Upgrading from HTTP mode to HTTP-Stream mode broke existing clients

### After Fix
- ✅ Both `/stream/tools/*` and `/tools/*` work in http-stream mode
- ✅ No client updates required - backwards compatible
- ✅ Clear documentation with examples for both transport modes
- ✅ Smooth upgrade path from HTTP mode to HTTP-Stream mode
- ✅ Recommended path (`/stream/tools/*`) clearly documented

## Recommendations

### For Users
1. **Preferred:** Use `/stream/tools/*` paths in http-stream mode for consistency
2. **Compatible:** Use `/tools/*` if you need backwards compatibility
3. Check documentation for your specific transport mode

### For Future Development
1. Consider adding server info endpoint that returns current transport mode and base paths
2. Consider deprecation timeline for unprefixed paths in http-stream mode
3. Add transport mode detection to client libraries
4. Consider environment variable for transport mode configuration

## Deliverables Checklist

- ✅ Root cause identified and documented
- ✅ Clear explanation of path differences between transport modes
- ✅ Backwards compatibility implemented (tools available at both paths)
- ✅ Documentation enhanced with warnings, examples, and troubleshooting
- ✅ Testing verification completed
- ✅ Investigation report created
- ✅ Resolution summary documented

## Acceptance Criteria Met

- ✅ Understand complete routing setup for http-stream transport
- ✅ Know exactly why tool endpoints returned 404
- ✅ Identified where to add/enable tool routes for http-stream
- ✅ Clear fix plan implemented and tested
- ✅ No 404s for either `/tools/*` or `/stream/tools/*` paths
- ✅ Documentation updated to prevent future confusion

## Status

🎉 **RESOLVED** - Tool endpoints now work correctly in http-stream mode at both paths, and documentation clearly explains the transport mode differences.
