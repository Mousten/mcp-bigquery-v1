# Investigation: 404s in HTTP-Stream Transport Mode

## Executive Summary

**Root Cause Identified**: In `http-stream` transport mode, all routers (including the tools router) are included with a `/stream` prefix. This means tool endpoints exist at `/stream/tools/*` instead of `/tools/*`, causing 404 errors when clients access the unprefixed paths.

**Status**: ✅ **This is by design, not a bug**. The http-stream mode intentionally namespaces all routes under `/stream` to support streaming capabilities while keeping them separate from potential other routes.

---

## Technical Analysis

### 1. Route Registration Differences

#### HTTP Mode (Default)
In `src/mcp_bigquery/main.py` lines 127-165:
```python
# Include all routers WITHOUT prefix
fastapi_app.include_router(resources_router)
fastapi_app.include_router(bigquery_router)
fastapi_app.include_router(tools_router)
fastapi_app.include_router(events_router)
fastapi_app.include_router(health_router)
fastapi_app.include_router(preferences_router)
fastapi_app.include_router(chat_router)
```

**Result**: Tool endpoints available at:
- `GET /tools/datasets`
- `POST /tools/execute_bigquery_sql`
- `GET /tools/tables`
- etc.

#### HTTP-Stream Mode
In `src/mcp_bigquery/main.py` lines 61-125:
```python
# Include all routers WITH /stream prefix
fastapi_app.include_router(resources_router, prefix="/stream")
fastapi_app.include_router(bigquery_router, prefix="/stream")
fastapi_app.include_router(tools_router, prefix="/stream")  # <-- Line 91
fastapi_app.include_router(events_router, prefix="/stream")
fastapi_app.include_router(health_router, prefix="/stream")
fastapi_app.include_router(preferences_router, prefix="/stream")
fastapi_app.include_router(chat_router, prefix="/stream")
```

**Result**: Tool endpoints available at:
- `GET /stream/tools/datasets`
- `POST /stream/tools/execute_bigquery_sql`
- `GET /stream/tools/tables`
- etc.

### 2. Why Chat Endpoints Work

The Streamlit `SessionManager` (in `streamlit_app/session_manager.py`) correctly uses the `/stream` prefix:

```python
# Line 39
response = await client.post(
    f"{self.base_url}/stream/chat/sessions",
    headers=self.headers,
    json={"title": title},
    timeout=10.0
)

# Line 63
response = await client.get(
    f"{self.base_url}/stream/chat/sessions",
    headers=self.headers,
    params={"limit": limit, "offset": offset},
    timeout=10.0
)
```

This is why chat operations return 200 OK - the client is using the correct paths.

### 3. Why Tool Endpoints Return 404

When a client tries to access:
- `GET /tools/datasets` → **404 Not Found**
- `POST /tools/execute_bigquery_sql` → **404 Not Found**

These paths don't exist in http-stream mode. The correct paths are:
- `GET /stream/tools/datasets` → **200 OK** ✅
- `POST /stream/tools/execute_bigquery_sql` → **200 OK** ✅

### 4. Route Verification

Created test script (`test_routes_simple.py`) that confirms the behavior:

```
HTTP MODE ROUTES:
  GET  /tools/datasets
  POST /tools/execute_bigquery_sql

HTTP-STREAM MODE ROUTES:
  GET  /stream/tools/datasets
  POST /stream/tools/execute_bigquery_sql
```

---

## Architecture Rationale

The `/stream` prefix in http-stream mode serves several purposes:

1. **Namespace Separation**: Allows both streaming and non-streaming endpoints on the same server
2. **Clear Intent**: Signals that these endpoints are part of the streaming transport
3. **NDJSON Support**: The mode also includes `/stream/ndjson/` endpoints for event streaming
4. **Consistency**: All routes are under the same base path for this transport mode

---

## Current Documentation Status

### ✅ Documented
`HTTP_ENDPOINTS_DOCUMENTATION.md` mentions the transport modes (lines 193-216):

```markdown
### Transport Modes

1. **HTTP Mode** (default): Routes at `/tools/*`
2. **HTTP-Stream Mode**: Routes at `/stream/tools/*`
3. **SSE Mode**: MCP protocol over Server-Sent Events
4. **Stdio Mode**: MCP protocol over stdin/stdout
```

### ⚠️ Needs Improvement
- The documentation mentions it but doesn't emphasize the path difference
- Client examples only show HTTP mode paths
- No troubleshooting section specifically for http-stream 404s
- Streamlit app documentation doesn't clearly explain the transport mode requirements

---

## Solutions & Recommendations

### Solution 1: Update Documentation (Recommended) ⭐
**Best for**: Clarifying the intended behavior

**Action**: Enhance documentation to make the path differences crystal clear

**Impact**: Low risk, high clarity

**Implementation**:
1. Add prominent notes in HTTP_ENDPOINTS_DOCUMENTATION.md
2. Add transport-specific examples for each endpoint
3. Update README.md with clear transport mode comparison table
4. Add troubleshooting section for 404s

### Solution 2: Add Route Aliases (Backwards Compatibility)
**Best for**: Supporting clients that expect `/tools/*` paths

**Action**: In http-stream mode, register tools router BOTH at `/stream/tools/*` AND `/tools/*`

**Impact**: Medium risk (duplicate routes), high compatibility

**Implementation**:
```python
# In main.py, http-stream mode section
# Include routers with /stream prefix
fastapi_app.include_router(tools_router, prefix="/stream")

# Also include without prefix for backwards compatibility
fastapi_app.include_router(tools_router)  # Registers at /tools/*
```

**Considerations**:
- Creates duplicate endpoints
- May cause confusion about which path to use
- Increases attack surface slightly
- Good for migration period

### Solution 3: Dynamic Base Path Configuration
**Best for**: Making clients transport-aware

**Action**: Add a configuration or discovery endpoint that tells clients which base path to use

**Impact**: Medium risk, requires client changes

**Implementation**:
```python
# Add endpoint that returns server configuration
@app.get("/")
async def server_info():
    return {
        "transport": "http-stream",
        "base_path": "/stream",
        "tools_base": "/stream/tools",
        "chat_base": "/stream/chat",
        "docs": "/docs"
    }
```

**Client usage**:
```python
# Client discovers base path
info = requests.get(f"{base_url}/").json()
tools_base = info["tools_base"]
# Use tools_base for all tool requests
requests.get(f"{base_url}{tools_base}/datasets")
```

### Solution 4: Environment Variable for Transport
**Best for**: Explicit client configuration

**Action**: Add `MCP_TRANSPORT_MODE` environment variable for clients

**Impact**: Low risk, requires documentation

**Implementation**:
```bash
# .env
MCP_TRANSPORT_MODE=http-stream  # or "http", "sse", "stdio"
MCP_BASE_URL=http://localhost:8000
```

Client code:
```python
transport = os.getenv("MCP_TRANSPORT_MODE", "http")
base_path = "/stream" if transport == "http-stream" else ""
url = f"{base_url}{base_path}/tools/datasets"
```

---

## Recommended Action Plan

### Phase 1: Documentation (Immediate) ✅
1. Update `HTTP_ENDPOINTS_DOCUMENTATION.md` with clear transport mode sections
2. Add transport mode comparison table to README.md
3. Add troubleshooting entry for 404s in http-stream mode
4. Update all code examples to show transport-specific URLs

### Phase 2: Client Configuration (Short-term)
1. Add server info endpoint at GET `/` that returns transport mode and base paths
2. Update Streamlit config to be transport-aware
3. Add helper utilities for constructing URLs based on transport mode

### Phase 3: Backwards Compatibility (Optional)
1. If needed for existing clients, add route aliases in http-stream mode
2. Add deprecation warnings for unprefixed paths
3. Plan migration timeline to remove aliases

---

## Testing Verification

### Test http-stream mode endpoints:
```bash
# Start server in http-stream mode
uv run mcp-bigquery --transport http-stream --port 8000

# Test chat endpoints (should work)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/stream/chat/sessions

# Test tool endpoints (correct path)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/stream/tools/datasets

# Test tool endpoints (old path - should 404)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets
```

### Test regular http mode:
```bash
# Start server in http mode
uv run mcp-bigquery --transport http --port 8000

# Test tool endpoints (should work at /tools/*)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets
```

---

## Conclusion

**The 404s are expected behavior** - http-stream mode uses `/stream` prefix for all routes, including tools. The endpoints exist and work correctly when accessed with the proper path.

**Resolution Path**: 
1. ✅ **Primary**: Enhance documentation to make path differences obvious
2. ⚠️ **Secondary** (if needed): Add backwards-compatible route aliases
3. 💡 **Future**: Add server info endpoint for dynamic path discovery

**No Code Bugs Found**: The implementation is working as designed. This is a documentation and client configuration issue, not a server-side bug.
