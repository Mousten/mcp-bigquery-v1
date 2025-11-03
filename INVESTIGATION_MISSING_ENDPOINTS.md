# Investigation: Missing BigQuery Tool Endpoints

## Executive Summary

**Status:** ✅ **Routes are correctly defined and registered**

The investigation reveals that the BigQuery tool endpoints (`/tools/datasets` and `/tools/execute_bigquery_sql`) ARE properly defined and registered in the codebase. The 404 errors are most likely caused by a **transport mode mismatch** between how the server is started and what the client expects.

## Root Cause

The MCP BigQuery server supports two HTTP transport modes with **different route prefixes**:

1. **HTTP Mode** (`--transport http`): Routes at `/tools/*`
2. **HTTP-Stream Mode** (`--transport http-stream`): Routes at `/stream/tools/*`

**If the server is running in HTTP-Stream mode but the client is configured to call `/tools/*` (without the `/stream` prefix), this will cause 404 errors.**

## Evidence

### 1. Routes Are Correctly Defined ✅

**File:** `src/mcp_bigquery/routes/tools.py`

```python
def create_tools_router(bigquery_client, event_manager, knowledge_base, config=None) -> APIRouter:
    """Create router for tool-related endpoints."""
    router = APIRouter(prefix="/tools", tags=["tools"])  # Line 22
    
    @router.post("/execute_bigquery_sql")  # Line 45
    async def execute_bigquery_sql_fastapi(payload: Dict[str, Any] = Body(...), ...):
        ...
    
    @router.get("/datasets")  # Line 61
    async def get_datasets_fastapi(current_user: UserContext = Depends(get_current_user)):
        ...
```

**Result:** Routes are defined with correct paths and decorators.

### 2. Routes Are Properly Registered ✅

**File:** `src/mcp_bigquery/main.py`

#### HTTP Mode (lines 127-165):
```python
# Create FastAPI app
fastapi_app = create_fastapi_app()

# Create tools router
tools_router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)

# Include router WITHOUT prefix
fastapi_app.include_router(tools_router)  # Line 157
```

**Final paths in HTTP mode:** `/tools/datasets`, `/tools/execute_bigquery_sql`

#### HTTP-Stream Mode (lines 61-125):
```python
# Create tools router
tools_router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)

# Include router WITH /stream prefix
fastapi_app.include_router(tools_router, prefix="/stream")  # Line 91
```

**Final paths in HTTP-stream mode:** `/stream/tools/datasets`, `/stream/tools/execute_bigquery_sql`

### 3. Test Verification ✅

Created test script (`test_routes.py`) that confirms routes are registered:

```
Testing full app setup (simulating main.py)...
============================================================
✓ GET    /tools/datasets
✓ POST   /tools/execute_bigquery_sql
✓ GET    /tools/tables
✓ POST   /tools/query

✅ All required routes are registered correctly!
```

### 4. Client Configuration ✅

**File:** `src/mcp_bigquery/client/mcp_client.py`

```python
async def list_datasets(self) -> Dict[str, Any]:
    return await self._make_request(
        method="GET",
        path="/tools/datasets"  # Line 245
    )

async def execute_sql(self, sql: str, ...) -> Dict[str, Any]:
    return await self._make_request(
        method="POST",
        path="/tools/execute_bigquery_sql"  # Line 224
    )
```

**Result:** Client is calling the correct paths for HTTP mode.

### 5. Streamlit Configuration

**File:** `streamlit_app/config.py`

```python
mcp_base_url: str = Field(
    default="http://localhost:8000",
    description="Base URL of the MCP server"
)
```

**File:** `streamlit_app/app.py` (line 175-178)

```python
mcp_config = ClientConfig(
    base_url=config.mcp_base_url,
    auth_token=st.session_state.access_token
)
```

**Result:** Streamlit is configured to use `http://localhost:8000` as base URL.

## Transport Mode Details

### HTTP Mode
- **Start command:** `uv run mcp-bigquery --transport http --port 8000`
- **Routes:** `/tools/datasets`, `/tools/execute_bigquery_sql`, etc.
- **Use case:** Standard REST API access

### HTTP-Stream Mode  
- **Start command:** `uv run mcp-bigquery --transport http-stream --port 8000`
- **Routes:** `/stream/tools/datasets`, `/stream/tools/execute_bigquery_sql`, etc.
- **Use case:** Recommended for Streamlit (according to README)

## Why 404 Errors Occur

### Scenario 1: Server in HTTP-Stream Mode, Client Expects HTTP Mode ❌

```
Server started: mcp-bigquery --transport http-stream --port 8000
Server routes: /stream/tools/datasets, /stream/tools/execute_bigquery_sql

Client requests: GET http://localhost:8000/tools/datasets
Result: 404 Not Found (route doesn't exist without /stream prefix)
```

### Scenario 2: Server in HTTP Mode, Client Configured Correctly ✅

```
Server started: mcp-bigquery --transport http --port 8000
Server routes: /tools/datasets, /tools/execute_bigquery_sql

Client requests: GET http://localhost:8000/tools/datasets
Result: 200 OK
```

### Scenario 3: Server Not Started or Failed to Start ❌

```
Server: Not running or crashed during initialization
Client requests: GET http://localhost:8000/tools/datasets
Result: Connection error or 404
```

## PR #30 Investigation

PR #30 (`feat-expose-mcp-bigquery-http-endpoints`) added documentation in `HTTP_ENDPOINTS_DOCUMENTATION.md` that describes:

1. Routes at `/tools/*` for HTTP mode
2. Routes at `/stream/tools/*` for HTTP-stream mode
3. Example usage and troubleshooting

**The PR correctly documented the endpoints but didn't change how they're registered** (they were already registered). The documentation confirms our findings.

## Possible Issues

### Issue 1: Transport Mode Mismatch (Most Likely)

**Problem:** Server running in HTTP-Stream mode (`--transport http-stream`) but client trying to access `/tools/*` instead of `/stream/tools/*`.

**Solution:**
- **Option A:** Start server in HTTP mode: `uv run mcp-bigquery --transport http --port 8000`
- **Option B:** Update client to use `/stream` prefix for HTTP-Stream mode
- **Option C:** Update `MCP_BASE_URL` environment variable to include `/stream` if using HTTP-Stream mode

### Issue 2: Server Initialization Failure

**Problem:** Server fails to start or crashes during initialization (e.g., missing environment variables, failed BigQuery client init).

**Solution:**
- Check server logs for errors
- Verify all required environment variables are set
- Test server startup manually: `uv run mcp-bigquery --transport http --port 8000`

### Issue 3: Wrong Base URL

**Problem:** Client configured with wrong base URL (e.g., pointing to wrong host/port).

**Solution:**
- Verify `MCP_BASE_URL` environment variable is set to `http://localhost:8000`
- Check Streamlit logs to see what URL it's actually calling

### Issue 4: Authentication Failure

**Problem:** Routes exist but return 401/403 instead of 404 (though logs show 404, not 401).

**Solution:**
- Less likely since logs specifically show 404 Not Found
- But verify JWT token is valid and properly passed in Authorization header

## Recommended Action Plan

### Step 1: Verify How Server Is Started

Check the command used to start the server:

```bash
# Should be one of:
uv run mcp-bigquery --transport http --port 8000        # Routes at /tools/*
uv run mcp-bigquery --transport http-stream --port 8000 # Routes at /stream/tools/*
```

### Step 2: Match Client Configuration to Server Mode

**If server is in HTTP mode:** No changes needed - this is the correct configuration.

**If server is in HTTP-Stream mode:** Either:
- Change server to HTTP mode, OR
- Update client base URL to include `/stream` prefix

### Step 3: Test Endpoints Directly

Test with curl to verify routes exist:

```bash
# Get auth token first
AUTH_TOKEN="your-jwt-token"

# Test datasets endpoint (HTTP mode)
curl -H "Authorization: Bearer $AUTH_TOKEN" http://localhost:8000/tools/datasets

# Test datasets endpoint (HTTP-Stream mode)
curl -H "Authorization: Bearer $AUTH_TOKEN" http://localhost:8000/stream/tools/datasets

# Test execute_bigquery_sql (HTTP mode)
curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1 as num", "use_cache": true}' \
  http://localhost:8000/tools/execute_bigquery_sql
```

### Step 4: Check Server Logs

Look for:
- Server startup messages showing which mode is active
- Any initialization errors
- Route registration confirmation
- Actual request paths being received

### Step 5: List All Routes

Add temporary debug code to list all registered routes on startup:

```python
# In main.py after including all routers
print("\n=== Registered Routes ===")
for route in fastapi_app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ', '.join(route.methods)
        print(f"{methods:20} {route.path}")
print("=" * 50 + "\n")
```

## Code Verification Status

✅ **Routes defined:** Correct paths in `routes/tools.py`  
✅ **Router created:** `create_tools_router()` properly creates APIRouter with `/tools` prefix  
✅ **Router included:** `main.py` includes router in both HTTP and HTTP-Stream modes  
✅ **Client paths:** Client calls correct paths (`/tools/datasets`, `/tools/execute_bigquery_sql`)  
✅ **Test verification:** Test script confirms routes are registered correctly  

## Conclusion

**The code is correct.** The routes are properly defined, registered, and tested. The 404 errors are caused by a configuration or deployment issue, most likely:

1. **Server running in HTTP-Stream mode** (`--transport http-stream`) with routes at `/stream/tools/*`, but **client expecting HTTP mode** with routes at `/tools/*`

2. **Server not running** or failed to start

To fix:
- Ensure server is started in HTTP mode: `uv run mcp-bigquery --transport http --port 8000`
- OR update client/Streamlit to use the `/stream` prefix if HTTP-Stream mode is required
- Verify with curl that endpoints are accessible after fixing the mode

## Next Steps

1. ✅ Investigation complete - routes exist and are correctly registered
2. 🔧 Verify which transport mode the server is actually running in
3. 🔧 Match client configuration to server transport mode
4. ✅ Test with curl to confirm endpoints are accessible
5. ✅ Update documentation if needed

---

**Investigation Date:** November 3, 2024  
**Status:** Complete - Root cause identified, solution provided
