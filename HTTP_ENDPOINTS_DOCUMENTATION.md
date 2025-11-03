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

The server supports multiple transport modes:

1. **HTTP Mode** (default): Routes at `/tools/*`
   ```bash
   mcp-bigquery --transport http --port 8000
   ```

2. **HTTP-Stream Mode**: Routes at `/stream/tools/*`
   ```bash
   mcp-bigquery --transport http-stream --port 8000
   ```

3. **SSE Mode**: MCP protocol over Server-Sent Events
   ```bash
   mcp-bigquery --transport sse --port 8000
   ```

4. **Stdio Mode**: MCP protocol over stdin/stdout
   ```bash
   mcp-bigquery --transport stdio
   ```

---

## Client Usage Examples

### Python (httpx)

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get datasets
    response = await client.get(
        "http://localhost:8000/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
    datasets = response.json()
    
    # Execute SQL
    response = await client.post(
        "http://localhost:8000/tools/execute_bigquery_sql",
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

**⚠️ MOST COMMON ISSUE: Transport Mode Mismatch**

The server supports two HTTP modes with different route prefixes:

| Mode | Routes At | Start Command |
|------|-----------|---------------|
| **HTTP** | `/tools/*` | `--transport http` |
| **HTTP-Stream** | `/stream/tools/*` | `--transport http-stream` |

**If you get 404 errors, the server is likely in HTTP-Stream mode while your client expects HTTP mode (or vice versa).**

**Quick Diagnosis:**
```bash
# Run the diagnostic script
python diagnose_server.py --token YOUR_JWT_TOKEN
```

**Solutions:**

1. **Use HTTP mode (recommended):**
   ```bash
   uv run mcp-bigquery --transport http --port 8000
   ```
   Client uses: `http://localhost:8000/tools/datasets`

2. **Use HTTP-Stream mode:**
   ```bash
   uv run mcp-bigquery --transport http-stream --port 8000
   ```
   Client uses: `http://localhost:8000/stream/tools/datasets`

**Other possible causes:**
- Server not running
- Wrong host/port in client configuration
- Firewall blocking connections

See [ENDPOINT_404_FIX.md](./ENDPOINT_404_FIX.md) for detailed troubleshooting.

### Issue: Routes return 401

**Possible causes:**
1. Missing or invalid JWT token
2. Token expired
3. JWT secret mismatch

**Solution:** Ensure valid JWT token is provided in Authorization header.

### Issue: Routes return 403

**Possible causes:**
1. User lacks required permissions
2. User doesn't have access to requested dataset/table
3. RBAC rules not configured

**Solution:** Check user roles and permissions in Supabase.

---

## Summary

✅ **All BigQuery MCP tools are exposed as HTTP REST endpoints**
✅ **Routes are registered and accessible at `/tools/*` (HTTP mode)**
✅ **Authentication and authorization are enforced**
✅ **Integration tested and working**

The HTTP endpoints are fully functional and ready for use by any HTTP client, including the Streamlit conversation manager.
