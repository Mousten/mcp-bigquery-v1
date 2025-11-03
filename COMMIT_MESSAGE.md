Fix: Add backwards compatibility for tool endpoints in http-stream mode

## Problem
Tool endpoints returned 404 in http-stream transport mode when accessed at
/tools/* paths. Only /stream/tools/* paths worked, causing confusion and
breaking clients that weren't aware of the path difference.

## Root Cause
In http-stream mode, all routers are registered with /stream prefix:
- Tools at /stream/tools/* (not /tools/*)
- Chat at /stream/chat/* (not /chat/*)

This is by design for namespace separation, but wasn't clearly documented
and required all clients to update their URLs when switching from http to
http-stream mode.

## Solution
Added backwards compatibility in http-stream mode:
- Tools now available at BOTH /stream/tools/* (recommended) AND /tools/*
- No breaking changes - existing clients continue to work
- Clear documentation with transport-specific examples

## Changes

### Code (1 file)
- src/mcp_bigquery/main.py:
  - Added tools router registration without prefix for backwards compat
  - Added TODO comment about future deprecation consideration
  - Clean, minimal change (4 lines added)

### Documentation (1 file)
- HTTP_ENDPOINTS_DOCUMENTATION.md:
  - Added transport mode comparison table
  - Added prominent warnings about path differences
  - Split examples into HTTP vs HTTP-Stream sections
  - Rewrote 404 troubleshooting with clear guidance
  - Added quick reference card

### Investigation (4 new files)
- INVESTIGATION_404_HTTP_STREAM.md: Full technical analysis
- TICKET_RESOLUTION_HTTP_STREAM_404.md: Formal resolution summary
- HTTP_STREAM_404_FIX_README.md: User-friendly quick start guide
- CHANGES_SUMMARY.md: Index of all changes

### Testing (1 file)
- test_http_stream_routes.py: Verification script

## Impact
Before: /tools/datasets → 404 in http-stream mode
After:  /tools/datasets → 200 OK (backwards compatible)
        /stream/tools/datasets → 200 OK (recommended)

## Testing
✅ All existing tests pass (488 tests)
✅ Verification script confirms both paths work
✅ Syntax validation passes
✅ No breaking changes

## Migration
None required. Existing code continues to work without changes.
New code should use /stream/tools/* in http-stream mode for consistency.
