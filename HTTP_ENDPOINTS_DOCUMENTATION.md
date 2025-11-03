# BigQuery MCP HTTP Endpoints Documentation

## Overview

The BigQuery MCP tools are exposed as HTTP REST endpoints in addition to the MCP protocol. These endpoints allow direct HTTP access to BigQuery operations from any HTTP client, including the Streamlit conversation manager.

## Authentication

All endpoints require JWT authentication via the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

Returns:
- `401 Unauthorized` if token is missing or invalid
- `403 Forbidden` if user lacks required permissions

## Available Endpoints

### 1. List Datasets

**Endpoint:** `GET /tools/datasets`

**Description:** Retrieve all datasets the authenticated user has access to.

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "datasets": [
    {"dataset_id": "public_data"},
    {"dataset_id": "analytics"}
  ]
}
```

**Permissions Required:**
- `dataset:list` OR `query:execute`

**Authorization:** User must have access to datasets via RBAC rules.

---

### 2. Execute BigQuery SQL

**Endpoint:** `POST /tools/execute_bigquery_sql`

**Description:** Execute a read-only SQL query on BigQuery with caching support.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "sql": "SELECT * FROM `project.dataset.table` LIMIT 10",
  "maximum_bytes_billed": 1000000000,
  "use_cache": true
}
```

**Response (200 OK):**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"query_id\": \"...\", \"result\": [...], \"statistics\": {...}}"
    }
  ],
  "isError": false
}
```

**Permissions Required:**
- `query:execute`

**Authorization:** User must have access to all tables referenced in the SQL query.

---

### 3. List Tables

**Endpoint:** `GET /tools/tables?dataset_id=<dataset>`

**Description:** List all tables in a dataset that the user can access.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `dataset_id` (required): Dataset identifier

**Response (200 OK):**
```json
{
  "tables": [
    {"table_id": "users"},
    {"table_id": "orders"}
  ]
}
```

---

### 4. Get Table Schema

**Endpoint:** `GET /tools/table_schema?dataset_id=<dataset>&table_id=<table>`

**Description:** Get schema information for a specific table.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `dataset_id` (required): Dataset identifier
- `table_id` (required): Table identifier
- `include_samples` (optional, default: true): Include sample rows

**Response (200 OK):**
```json
{
  "schema": [
    {"name": "id", "type": "INTEGER", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING", "mode": "NULLABLE"}
  ]
}
```

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Missing authentication token"
}
```

### 403 Forbidden
```json
{
  "error": "Access denied to dataset example_dataset"
}
```

### 400 Bad Request
```json
{
  "error": "Only READ operations are allowed."
}
```

### 500 Internal Server Error
```json
{
  "error": "BigQuery API error: ..."
}
```

---

## Implementation Details

### Route Registration

The HTTP endpoints are defined in `src/mcp_bigquery/routes/tools.py` and registered in `main.py`:

```python
# In main.py (HTTP mode)
tools_router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)
fastapi_app.include_router(tools_router)
```

This creates routes at:
- `GET /tools/datasets`
- `POST /tools/execute_bigquery_sql`
- etc.

### Transport Modes

The server supports multiple transport modes with **different base paths**:

| Transport Mode | Base Path | Tool Endpoints | Example |
|---|---|---|---|
| **HTTP** (default) | None | `/tools/*` | `GET /tools/datasets` |
| **HTTP-Stream** | `/stream` | `/stream/tools/*` | `GET /stream/tools/datasets` |
| **SSE** | N/A | MCP protocol only | Use MCP client |
| **Stdio** | N/A | MCP protocol only | Use MCP client |

#### ⚠️ Important: Path Differences

**In HTTP-Stream mode:**
- ✅ **Recommended**: `GET /stream/tools/datasets` (primary path)
- ✅ **Also works**: `GET /tools/datasets` (backwards compatible)
- Both paths work! The `/stream/tools/*` paths are recommended for new code.

**In regular HTTP mode, routes have NO prefix:**
- ✅ Correct: `GET /tools/datasets`
- ❌ Wrong: `GET /stream/tools/datasets` → Returns 404

**Note on Backwards Compatibility**: As of the latest version, http-stream mode exposes tools at both `/stream/tools/*` (recommended) and `/tools/*` (for compatibility with existing clients). This prevents 404 errors when upgrading from HTTP mode to HTTP-Stream mode.

#### Starting the Server

**HTTP Mode (default):**
```bash
uv run mcp-bigquery --transport http --port 8000
# Tool endpoints: /tools/*
# Chat endpoints: /chat/*
```

**HTTP-Stream Mode:**
```bash
uv run mcp-bigquery --transport http-stream --port 8000
# Tool endpoints: /stream/tools/*
# Chat endpoints: /stream/chat/*
# NDJSON stream: /stream/ndjson/
```

**SSE Mode** (MCP protocol over Server-Sent Events):
```bash
uv run mcp-bigquery --transport sse --port 8000
# Use MCP client library, not direct HTTP
```

**Stdio Mode** (MCP protocol over stdin/stdout):
```bash
uv run mcp-bigquery --transport stdio
# Use MCP client library, not HTTP
```

---

## Client Usage Examples

### Python (httpx) - HTTP Mode

```python
import httpx

# For HTTP mode (default)
BASE_URL = "http://localhost:8000"

async with httpx.AsyncClient() as client:
    # Get datasets
    response = await client.get(
        f"{BASE_URL}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
    datasets = response.json()
    
    # Execute SQL
    response = await client.post(
        f"{BASE_URL}/tools/execute_bigquery_sql",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sql": "SELECT 1 as num",
            "use_cache": True
        }
    )
    result = response.json()
```

### Python (httpx) - HTTP-Stream Mode

```python
import httpx

# For HTTP-Stream mode - note the /stream prefix!
BASE_URL = "http://localhost:8000/stream"

async with httpx.AsyncClient() as client:
    # Get datasets (note /stream prefix)
    response = await client.get(
        f"{BASE_URL}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
    datasets = response.json()
    
    # Execute SQL (note /stream prefix)
    response = await client.post(
        f"{BASE_URL}/tools/execute_bigquery_sql",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sql": "SELECT 1 as num",
            "use_cache": True
        }
    )
    result = response.json()
```

### JavaScript (fetch)

```javascript
// Get datasets
const response = await fetch('http://localhost:8000/tools/datasets', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const datasets = await response.json();

// Execute SQL
const sqlResponse = await fetch('http://localhost:8000/tools/execute_bigquery_sql', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    sql: 'SELECT 1 as num',
    use_cache: true
  })
});
const result = await sqlResponse.json();
```

### MCP Client (Python)

```python
from mcp_bigquery.client import MCPClient, ClientConfig

config = ClientConfig(
    base_url="http://localhost:8000",
    auth_token=token
)

async with MCPClient(config) as client:
    # Get datasets
    datasets = await client.list_datasets()
    
    # Execute SQL
    result = await client.execute_sql("SELECT 1 as num")
```

---

## Testing

To verify routes are registered correctly:

```python
from src.mcp_bigquery.routes.tools import create_tools_router
from unittest.mock import MagicMock, AsyncMock

# Create mocks
bigquery_client = MagicMock()
event_manager = MagicMock()
event_manager.broadcast = AsyncMock()
knowledge_base = MagicMock()
config = MagicMock()
config.supabase_jwt_secret = "test-secret"

# Create router
router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)

# Print routes
for route in router.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        for method in route.methods:
            print(f"{method:6} {route.path}")
```

Expected output:
```
POST   /tools/query
POST   /tools/execute_bigquery_sql
GET    /tools/datasets
GET    /tools/tables
...
```

---

## Troubleshooting

### Issue: Routes return 404

**Good News:** As of the latest version, http-stream mode supports BOTH `/stream/tools/*` and `/tools/*` paths for backwards compatibility, so 404s should be rare!

**If you still get 404s:**

1. **Check which transport mode the server is running:**
   ```bash
   # Look at server startup logs
   # HTTP mode: "Starting server in HTTP mode..."
   # HTTP-Stream mode: "Starting server in HTTP-STREAM mode..."
   ```

2. **Verify the endpoint path is correct:**
   ```python
   # These all work in http-stream mode:
   url = "http://localhost:8000/stream/tools/datasets"  # Recommended
   url = "http://localhost:8000/tools/datasets"         # Also works
   
   # In http mode, only unprefixed works:
   url = "http://localhost:8000/tools/datasets"         # Works
   url = "http://localhost:8000/stream/tools/datasets"  # 404
   ```

3. **Check server is actually running:**
   ```bash
   # Test basic connectivity
   curl http://localhost:8000/stream/
   # Should return: {"message": "MCP tools root", ...}
   ```

**Quick Test:**
```bash
# Both of these work in http-stream mode:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/stream/tools/datasets
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets

# Only unprefixed works in http mode:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets
```

---

### Issue: Routes return 401

**Possible causes:**
1. Missing or invalid JWT token
2. Token expired
3. JWT secret mismatch

**Solution:** Ensure valid JWT token is provided in Authorization header.

```bash
# Check token is provided
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" http://localhost:8000/tools/datasets

# Verify token hasn't expired
# JWT tokens from Supabase expire after 1 hour by default
```

---

### Issue: Routes return 403

**Possible causes:**
1. User lacks required permissions
2. User doesn't have access to requested dataset/table
3. RBAC rules not configured

**Solution:** Check user roles and permissions in Supabase.

```sql
-- Check user roles
SELECT * FROM user_roles WHERE user_id = 'YOUR_USER_ID';

-- Check role permissions
SELECT rp.* FROM role_permissions rp
JOIN user_roles ur ON ur.role = rp.role
WHERE ur.user_id = 'YOUR_USER_ID';

-- Check dataset access
SELECT rda.* FROM role_dataset_access rda
JOIN user_roles ur ON ur.role = rda.role
WHERE ur.user_id = 'YOUR_USER_ID';
```

---

## Summary

✅ **All BigQuery MCP tools are exposed as HTTP REST endpoints**
✅ **Routes are transport-mode specific:**
   - HTTP mode: `/tools/*`
   - HTTP-Stream mode: `/stream/tools/*`
✅ **Authentication and authorization are enforced**
✅ **Integration tested and working**

The HTTP endpoints are fully functional and ready for use by any HTTP client, including the Streamlit conversation manager. **Remember to use the correct base path for your transport mode to avoid 404 errors!**

### Quick Reference Card

| Need | HTTP Mode | HTTP-Stream Mode (Recommended) | HTTP-Stream Mode (Compatible) |
|---|---|---|---|
| **List datasets** | `GET /tools/datasets` | `GET /stream/tools/datasets` | `GET /tools/datasets` |
| **Execute SQL** | `POST /tools/execute_bigquery_sql` | `POST /stream/tools/execute_bigquery_sql` | `POST /tools/execute_bigquery_sql` |
| **List tables** | `GET /tools/tables?dataset_id=X` | `GET /stream/tools/tables?dataset_id=X` | `GET /tools/tables?dataset_id=X` |
| **Chat sessions** | `GET /chat/sessions` | `GET /stream/chat/sessions` | N/A |
| **Server info** | `GET /` | `GET /stream/` | N/A |

**Note:** In http-stream mode, both `/stream/tools/*` (recommended) and `/tools/*` (backwards compatible) work. Use `/stream/tools/*` for new code.
