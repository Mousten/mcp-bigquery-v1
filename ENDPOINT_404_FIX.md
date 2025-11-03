# Fix for 404 Errors on BigQuery Tool Endpoints

## Problem

The MCP FastAPI server returns 404 errors for BigQuery tool endpoints:
```
GET /tools/datasets → 404 Not Found
POST /tools/execute_bigquery_sql → 404 Not Found
```

## Root Cause

The server supports two HTTP transport modes with **different route prefixes**:

| Transport Mode | Start Command | Route Prefix | Example Endpoint |
|----------------|---------------|--------------|------------------|
| **HTTP** | `--transport http` | `/tools/*` | `/tools/datasets` |
| **HTTP-Stream** | `--transport http-stream` | `/stream/tools/*` | `/stream/tools/datasets` |

**The 404 errors occur when there's a mismatch between the server's transport mode and the client's expected route prefix.**

## Diagnosis

Use the provided diagnostic script to check your server configuration:

```bash
# Check if server is running and which mode it's in
python diagnose_server.py

# With authentication token
python diagnose_server.py --token YOUR_JWT_TOKEN

# Check different URL
python diagnose_server.py --url http://your-server:8000
```

The diagnostic script will:
- ✅ Test connectivity to the server
- ✅ Check HTTP mode endpoints (`/tools/*`)
- ✅ Check HTTP-Stream mode endpoints (`/stream/tools/*`)
- ✅ Identify which mode the server is running in
- ✅ Provide specific fix recommendations

## Solution

### Option 1: Use HTTP Mode (Recommended for Direct API Access)

**Start the server in HTTP mode:**

```bash
uv run mcp-bigquery --transport http --port 8000
```

**Client configuration:**
```python
# Python client
mcp_config = ClientConfig(
    base_url="http://localhost:8000",  # No /stream prefix
    auth_token=your_token
)

# Environment variable
MCP_BASE_URL=http://localhost:8000
```

**Endpoints will be available at:**
- `GET /tools/datasets`
- `POST /tools/execute_bigquery_sql`
- `GET /tools/tables`
- `GET /tools/table_schema`
- `POST /tools/query`

### Option 2: Use HTTP-Stream Mode

**Start the server in HTTP-Stream mode:**

```bash
uv run mcp-bigquery --transport http-stream --port 8000
```

**Client configuration (requires /stream prefix):**
```python
# Python client - update base URL to include /stream
mcp_config = ClientConfig(
    base_url="http://localhost:8000/stream",  # Add /stream prefix
    auth_token=your_token
)

# Or modify the client to prepend /stream to all paths
```

**Endpoints will be available at:**
- `GET /stream/tools/datasets`
- `POST /stream/tools/execute_bigquery_sql`
- `GET /stream/tools/tables`
- `GET /stream/tools/table_schema`
- `POST /stream/tools/query`

## Quick Verification

After starting the server, you should see helpful startup messages:

### HTTP Mode:
```
Starting server in HTTP mode on 0.0.0.0:8000...
📡 BigQuery tool endpoints available at:
   - GET  0.0.0.0:8000/tools/datasets
   - POST 0.0.0.0:8000/tools/execute_bigquery_sql
   - GET  0.0.0.0:8000/tools/tables
   - GET  0.0.0.0:8000/tools/table_schema
📚 API documentation at: http://0.0.0.0:8000/docs
```

### HTTP-Stream Mode:
```
Starting server in HTTP-STREAM mode on 0.0.0.0:8000...
📡 BigQuery tool endpoints available at:
   - GET  0.0.0.0:8000/stream/tools/datasets
   - POST 0.0.0.0:8000/stream/tools/execute_bigquery_sql
   - GET  0.0.0.0:8000/stream/tools/tables
   - GET  0.0.0.0:8000/stream/tools/table_schema
📚 API documentation at: http://0.0.0.0:8000/docs
⚠️  Note: All tool endpoints have /stream prefix in this mode
```

## Test with curl

### HTTP Mode:
```bash
# Get auth token from Supabase or your auth system
AUTH_TOKEN="your-jwt-token"

# Test datasets endpoint
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/tools/datasets

# Test SQL execution
curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1 as num", "use_cache": true}' \
  http://localhost:8000/tools/execute_bigquery_sql
```

### HTTP-Stream Mode:
```bash
# Add /stream prefix to all paths
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/stream/tools/datasets

curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT 1 as num", "use_cache": true}' \
  http://localhost:8000/stream/tools/execute_bigquery_sql
```

## For Streamlit Users

The Streamlit app (`streamlit_app/app.py`) uses the `MCP_BASE_URL` environment variable.

**If server is in HTTP mode (recommended):**
```bash
# .env file
MCP_BASE_URL=http://localhost:8000
```

**If server is in HTTP-Stream mode:**
```bash
# .env file
MCP_BASE_URL=http://localhost:8000/stream
```

Or update the client code to prepend `/stream` to all paths.

## Code Verification

The routes ARE correctly defined and registered in the codebase:

✅ **Route definitions:** `src/mcp_bigquery/routes/tools.py`
```python
router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("/datasets")
@router.post("/execute_bigquery_sql")
# etc.
```

✅ **Router registration in HTTP mode:** `src/mcp_bigquery/main.py` (line 157)
```python
fastapi_app.include_router(tools_router)  # No prefix → /tools/*
```

✅ **Router registration in HTTP-Stream mode:** `src/mcp_bigquery/main.py` (line 91)
```python
fastapi_app.include_router(tools_router, prefix="/stream")  # → /stream/tools/*
```

## Common Mistakes

❌ **Starting server in HTTP-Stream mode but client expects HTTP mode**
```bash
# Server
uv run mcp-bigquery --transport http-stream --port 8000  # Routes at /stream/tools/*

# Client tries
GET http://localhost:8000/tools/datasets  # 404 - wrong path!
```

✅ **Fix:** Either restart server in HTTP mode OR update client base URL to include `/stream`

❌ **Server not running at all**
```bash
# Client tries
GET http://localhost:8000/tools/datasets  # Connection error or 404
```

✅ **Fix:** Start the server first

❌ **Wrong port or host**
```bash
# Server on port 8000
# Client trying port 8080
GET http://localhost:8080/tools/datasets  # Connection error
```

✅ **Fix:** Match port numbers

## Related Documentation

- [HTTP_ENDPOINTS_DOCUMENTATION.md](./HTTP_ENDPOINTS_DOCUMENTATION.md) - Complete API reference
- [INVESTIGATION_MISSING_ENDPOINTS.md](./INVESTIGATION_MISSING_ENDPOINTS.md) - Detailed investigation report
- [README.md](./README.md) - Main project documentation

## Summary

1. ✅ The routes are correctly implemented in the code
2. ✅ Choose the right transport mode for your use case
3. ✅ Match your client configuration to the server's transport mode
4. ✅ Use the diagnostic script to verify your setup
5. ✅ Check startup messages to confirm route availability

---

**Last Updated:** November 3, 2024
