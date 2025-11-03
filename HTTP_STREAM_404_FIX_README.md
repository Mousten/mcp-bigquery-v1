# HTTP-Stream Transport Mode 404 Fix

## Quick Summary

**Problem:** Tool endpoints returned 404 in `http-stream` transport mode when accessed at `/tools/*` paths.

**Root Cause:** In http-stream mode, all routes were prefixed with `/stream`, so tools existed at `/stream/tools/*` not `/tools/*`.

**Solution:** Added backwards compatibility - tools are now available at BOTH paths in http-stream mode.

## What Changed

### Code Changes
**File:** `src/mcp_bigquery/main.py` (line 100)

Added backwards-compatible route registration:
```python
# Include all routers under the /stream base (primary path)
fastapi_app.include_router(tools_router, prefix="/stream")

# Also include tools without prefix for backwards compatibility
fastapi_app.include_router(tools_router)
```

### Documentation Updates
**File:** `HTTP_ENDPOINTS_DOCUMENTATION.md`

1. Added transport mode comparison table
2. Clarified path differences with warnings
3. Added HTTP-Stream specific code examples
4. Updated troubleshooting section
5. Added quick reference card with all paths

## How To Use

### HTTP-Stream Mode (After Fix)
Both of these work:
```bash
# Recommended path
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/stream/tools/datasets

# Backwards compatible path
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/tools/datasets
```

### Regular HTTP Mode
Only unprefixed path works:
```bash
# Works
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/tools/datasets

# Returns 404
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/stream/tools/datasets
```

## Path Reference

| Transport Mode | Primary Path | Alternative Path |
|---|---|---|
| **http** | `/tools/*` | N/A |
| **http-stream** | `/stream/tools/*` | `/tools/*` (backwards compatible) |
| **sse** | MCP protocol | N/A |
| **stdio** | MCP protocol | N/A |

## For Developers

### Running the Server
```bash
# HTTP mode
uv run mcp-bigquery --transport http --port 8000

# HTTP-Stream mode (with backwards compatibility)
uv run mcp-bigquery --transport http-stream --port 8000
```

### Testing the Fix
```bash
# Run the verification script
uv run python test_http_stream_routes.py

# Expected output:
# ✅ Both paths work in http-stream mode:
#   - GET /stream/tools/datasets (recommended)
#   - GET /tools/datasets (backwards compatible)
```

### Code Example (Python)
```python
import httpx

# Works for both http and http-stream modes
base_url = "http://localhost:8000"
token = "your_jwt_token"

async with httpx.AsyncClient() as client:
    # This works in both modes
    response = await client.get(
        f"{base_url}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # This only works in http-stream mode (recommended)
    response = await client.get(
        f"{base_url}/stream/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
```

## Related Documentation

- **`INVESTIGATION_404_HTTP_STREAM.md`** - Full technical investigation
- **`TICKET_RESOLUTION_HTTP_STREAM_404.md`** - Detailed resolution summary
- **`HTTP_ENDPOINTS_DOCUMENTATION.md`** - Complete API documentation with transport modes
- **`test_http_stream_routes.py`** - Verification test script

## Migration Guide

### If You're Using HTTP Mode
No changes needed. Everything works as before.

### If You're Migrating to HTTP-Stream Mode
You have two options:

**Option 1: Keep existing code (easiest)**
```python
# Your existing code keeps working
response = await client.get(f"{base_url}/tools/datasets", ...)
```

**Option 2: Update to recommended paths**
```python
# Update for consistency with other http-stream endpoints
response = await client.get(f"{base_url}/stream/tools/datasets", ...)
```

### If You're Writing New Code
Use the `/stream/tools/*` paths in http-stream mode for consistency:
```python
# Recommended for new code in http-stream mode
base_path = "/stream" if transport == "http-stream" else ""
url = f"{base_url}{base_path}/tools/datasets"
```

## Troubleshooting

### Still Getting 404s?
1. Check server startup logs to confirm transport mode
2. Verify Authorization header is present
3. Test with curl to isolate the issue
4. Check server is actually running on the expected port

### Need Help?
See the comprehensive troubleshooting section in `HTTP_ENDPOINTS_DOCUMENTATION.md`.

## Status

✅ **FIXED** - Tool endpoints now work at both paths in http-stream mode
✅ **TESTED** - Verification script confirms both paths work
✅ **DOCUMENTED** - All documentation updated with clear examples
✅ **BACKWARDS COMPATIBLE** - No breaking changes for existing clients
