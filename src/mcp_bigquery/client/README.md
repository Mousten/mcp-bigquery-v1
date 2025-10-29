# MCP BigQuery Client

A reusable async client for interacting with the MCP BigQuery server. This client provides a high-level interface to the server's REST API with built-in authentication, retry logic, and error handling.

## Features

- **Async/await support**: Built on `httpx` for efficient async operations
- **Authentication**: Automatic JWT token injection via Bearer authentication
- **Retry logic**: Exponential backoff for transient failures
- **Error handling**: Descriptive exceptions for different error types (401, 403, 400, 500+)
- **Streaming support**: Consume server events via NDJSON stream
- **Configuration**: Flexible configuration from environment or code
- **Type hints**: Full type annotations for better IDE support

## Installation

The client is part of the `mcp-bigquery-server` package:

```bash
pip install mcp-bigquery-server
```

Or with `uv`:

```bash
uv pip install mcp-bigquery-server
```

## Quick Start

### Basic Usage

```python
from mcp_bigquery.client import MCPClient, ClientConfig

# Create configuration
config = ClientConfig(
    base_url="http://localhost:8000",
    auth_token="your-jwt-token"
)

# Use as async context manager
async with MCPClient(config) as client:
    # List datasets
    datasets = await client.list_datasets()
    print(datasets)
    
    # Execute SQL query
    result = await client.execute_sql("SELECT * FROM `my_dataset.my_table` LIMIT 10")
    print(result)
```

### Configuration from Environment

```python
import os
from mcp_bigquery.client import MCPClient, ClientConfig

# Set environment variables
os.environ['MCP_BASE_URL'] = 'https://api.example.com'
os.environ['MCP_AUTH_TOKEN'] = 'your-jwt-token'

# Load config from environment
config = ClientConfig.from_env()

async with MCPClient(config) as client:
    datasets = await client.list_datasets()
```

## Configuration

### Environment Variables

- `MCP_BASE_URL`: Base URL of the MCP server (default: `http://localhost:8000`)
- `MCP_AUTH_TOKEN`: JWT token for authentication
- `MCP_TIMEOUT`: Request timeout in seconds (default: `30.0`)
- `MCP_MAX_RETRIES`: Maximum number of retries (default: `3`)
- `MCP_RETRY_DELAY`: Initial retry delay in seconds (default: `1.0`)
- `MCP_VERIFY_SSL`: Whether to verify SSL certificates (default: `true`)

### ClientConfig Options

```python
from mcp_bigquery.client import ClientConfig

config = ClientConfig(
    base_url="https://api.example.com",  # Server base URL
    auth_token="your-jwt-token",          # JWT authentication token
    timeout=60.0,                         # Request timeout (seconds)
    max_retries=5,                        # Number of retries for failed requests
    retry_delay=2.0,                      # Initial delay between retries (exponential backoff)
    verify_ssl=True                       # Verify SSL certificates
)
```

## API Methods

### Query Execution

#### `execute_sql(sql, maximum_bytes_billed=1000000000, use_cache=True)`

Execute a SQL query on BigQuery.

```python
result = await client.execute_sql(
    sql="SELECT * FROM `dataset.table` WHERE id > 100",
    maximum_bytes_billed=500000000,  # Limit query cost
    use_cache=True                    # Use BigQuery cache
)

# Access results
rows = result["rows"]
total_rows = result["total_rows"]
```

**Parameters:**
- `sql` (str): SQL query to execute
- `maximum_bytes_billed` (int): Maximum bytes to bill for the query (default: 1GB)
- `use_cache` (bool): Whether to use BigQuery cache (default: True)

**Returns:** Dictionary with query results

**Raises:**
- `AuthenticationError`: If authentication fails (401)
- `AuthorizationError`: If user lacks permissions (403)
- `ValidationError`: If query is invalid (400)
- `ServerError`: On server errors (500+)

### Dataset Operations

#### `list_datasets()`

List all datasets the user has access to.

```python
result = await client.list_datasets()
datasets = result["datasets"]
```

**Returns:** Dictionary with list of accessible datasets

### Table Operations

#### `list_tables(dataset_id)`

List tables in a dataset.

```python
result = await client.list_tables("my_dataset")
tables = result["tables"]
```

**Parameters:**
- `dataset_id` (str): Dataset identifier

**Returns:** Dictionary with list of tables

#### `get_table_schema(dataset_id, table_id, include_samples=True)`

Get schema information for a table.

```python
schema = await client.get_table_schema(
    dataset_id="my_dataset",
    table_id="my_table",
    include_samples=True
)

# Access schema details
fields = schema["schema"]
samples = schema.get("samples", [])
```

**Parameters:**
- `dataset_id` (str): Dataset identifier
- `table_id` (str): Table identifier
- `include_samples` (bool): Whether to include sample data (default: True)

**Returns:** Dictionary with schema information and optional samples

#### `explain_table(project_id, dataset_id, table_id, include_usage_stats=True)`

Get detailed explanation of a table with usage statistics.

```python
explanation = await client.explain_table(
    project_id="my-project",
    dataset_id="my_dataset",
    table_id="my_table",
    include_usage_stats=True
)

# Access explanation and stats
description = explanation["description"]
usage = explanation.get("usage_stats", {})
```

**Parameters:**
- `project_id` (str): Google Cloud project ID
- `dataset_id` (str): Dataset identifier
- `table_id` (str): Table identifier
- `include_usage_stats` (bool): Include usage statistics (default: True)

**Returns:** Dictionary with table explanation and usage stats

### Query Optimization

#### `get_query_suggestions(tables_mentioned=None, query_context=None, limit=5)`

Get query suggestions based on context.

```python
suggestions = await client.get_query_suggestions(
    tables_mentioned=["users", "orders"],
    query_context="Find top customers by total order value",
    limit=5
)
```

**Parameters:**
- `tables_mentioned` (List[str], optional): Tables to consider
- `query_context` (str, optional): Context description
- `limit` (int): Maximum suggestions to return (default: 5)

**Returns:** Dictionary with query suggestions

#### `analyze_query_performance(sql, tables_accessed=None, time_range_hours=168, user_id=None)`

Analyze query performance and get recommendations.

```python
analysis = await client.analyze_query_performance(
    sql="SELECT * FROM large_table",
    tables_accessed=["large_table"],
    time_range_hours=24
)

# Access analysis results
recommendations = analysis.get("recommendations", [])
estimated_cost = analysis.get("estimated_cost")
```

**Parameters:**
- `sql` (str): SQL query to analyze
- `tables_accessed` (List[str], optional): Tables accessed by query
- `time_range_hours` (int): Historical time range (default: 168 hours/1 week)
- `user_id` (str, optional): Filter by user ID

**Returns:** Dictionary with performance analysis

### Schema Management

#### `get_schema_changes(project_id, dataset_id, table_id, limit=10)`

Get schema change history for a table.

```python
changes = await client.get_schema_changes(
    project_id="my-project",
    dataset_id="my_dataset",
    table_id="my_table",
    limit=10
)
```

**Parameters:**
- `project_id` (str): Google Cloud project ID
- `dataset_id` (str): Dataset identifier
- `table_id` (str): Table identifier
- `limit` (int): Maximum changes to return (default: 10)

**Returns:** Dictionary with schema change history

### Cache Management

#### `manage_cache(action, target=None, project_id=None, dataset_id=None, table_id=None)`

Manage query cache.

```python
# Clear all cache
result = await client.manage_cache(action="clear", target="all")

# Get cache statistics
stats = await client.manage_cache(action="get_stats")

# Clear cache for specific table
result = await client.manage_cache(
    action="clear",
    target="table",
    project_id="my-project",
    dataset_id="my_dataset",
    table_id="my_table"
)
```

**Parameters:**
- `action` (str): Cache action (e.g., "clear", "get_stats")
- `target` (str, optional): Target scope (e.g., "all", "queries", "metadata")
- `project_id` (str, optional): Project ID for scoped operations
- `dataset_id` (str, optional): Dataset ID for scoped operations
- `table_id` (str, optional): Table ID for scoped operations

**Returns:** Dictionary with operation result

### Event Streaming

#### `stream_events(channel="system")`

Stream events from the server via NDJSON.

```python
async for event in client.stream_events(channel="queries"):
    event_type = event.get("type")
    
    if event_type == "query_started":
        print(f"Query started: {event['query_id']}")
    elif event_type == "query_completed":
        print(f"Query completed: {event['query_id']}")
```

**Parameters:**
- `channel` (str): Event channel to subscribe to (default: "system")

**Yields:** Event dictionaries as they arrive

**Raises:**
- `AuthenticationError`: If authentication fails
- `NetworkError`: On connection failures

## Error Handling

The client raises specific exceptions for different error types:

```python
from mcp_bigquery.client import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ServerError,
    NetworkError,
)

async with MCPClient(config) as client:
    try:
        result = await client.execute_sql("SELECT * FROM my_table")
    except AuthenticationError as e:
        print(f"Auth failed: {e}")
        # Handle token refresh
    except AuthorizationError as e:
        print(f"Access denied: {e}")
        # Handle permission error
    except ValidationError as e:
        print(f"Invalid query: {e}")
        # Handle validation error
    except ServerError as e:
        print(f"Server error: {e}")
        # Handle server error
    except NetworkError as e:
        print(f"Network error: {e}")
        # Handle network error
```

### Exception Hierarchy

- `MCPClientError` (base exception)
  - `AuthenticationError` (401 responses)
  - `AuthorizationError` (403 responses)
  - `ValidationError` (400 responses)
  - `ServerError` (500+ responses)
  - `NetworkError` (network/timeout failures)

## Retry Behavior

The client automatically retries failed requests with exponential backoff:

- **Retry conditions**: Server errors (500+), timeouts, network errors
- **No retry**: Authentication (401), authorization (403), validation (400) errors
- **Backoff formula**: `delay * (2 ** retry_count)`

Example with 3 max retries and 1.0s initial delay:
- Attempt 1: Immediate
- Attempt 2: After 1.0s
- Attempt 3: After 2.0s
- Attempt 4: After 4.0s

Configure retry behavior:

```python
config = ClientConfig(
    max_retries=5,      # More retries
    retry_delay=0.5     # Shorter initial delay
)
```

## Integration Examples

### With Streamlit

```python
import streamlit as st
from mcp_bigquery.client import MCPClient, ClientConfig

@st.cache_resource
def get_client():
    config = ClientConfig.from_env()
    return MCPClient(config)

async def run_query(sql: str):
    client = get_client()
    await client._ensure_client()
    result = await client.execute_sql(sql)
    return result

# In Streamlit app
if st.button("Run Query"):
    import asyncio
    result = asyncio.run(run_query(st.session_state.query))
    st.json(result)
```

### With LangChain

```python
from langchain.tools import Tool
from mcp_bigquery.client import MCPClient, ClientConfig

config = ClientConfig.from_env()
client = MCPClient(config)

async def execute_bigquery(sql: str) -> str:
    """Execute BigQuery SQL and return results."""
    await client._ensure_client()
    result = await client.execute_sql(sql)
    return str(result)

bigquery_tool = Tool(
    name="BigQuery",
    func=execute_bigquery,
    description="Execute SQL queries on BigQuery"
)
```

### Manual Client Management

If you need more control over the client lifecycle:

```python
client = MCPClient(config)

try:
    await client._ensure_client()
    result = await client.execute_sql("SELECT 1")
    print(result)
finally:
    await client.close()
```

## Testing

The client includes comprehensive tests. Run them with:

```bash
# Run all client tests
uv run pytest tests/client/ -v

# Run with coverage
uv run pytest tests/client/ --cov=src/mcp_bigquery/client --cov-report=term-missing

# Run specific test
uv run pytest tests/client/test_mcp_client.py::TestMCPClientMethods::test_execute_sql -v
```

## Development

### Project Structure

```
src/mcp_bigquery/client/
├── __init__.py          # Package exports
├── config.py            # Configuration classes
├── exceptions.py        # Custom exceptions
├── mcp_client.py        # Main client implementation
└── README.md            # This file

tests/client/
├── __init__.py
├── test_config.py       # Configuration tests
└── test_mcp_client.py   # Client tests
```

### Adding New Methods

To add a new API method to the client:

1. Add the method to `MCPClient` in `mcp_client.py`
2. Follow the existing pattern for request handling
3. Add comprehensive tests in `test_mcp_client.py`
4. Update this README with usage examples

Example:

```python
async def new_method(self, param: str) -> Dict[str, Any]:
    """Description of the method.
    
    Args:
        param: Parameter description
        
    Returns:
        Result description
        
    Raises:
        AuthenticationError: When auth fails
        ServerError: On server errors
    """
    return await self._make_request(
        method="POST",
        path="/tools/new_endpoint",
        json_data={"param": param}
    )
```

## Troubleshooting

### Common Issues

**Authentication Failures**

```python
# Ensure token is valid and not expired
config = ClientConfig(auth_token="your-current-token")

# Token format should be: "Bearer <token>" or just "<token>"
```

**SSL Certificate Verification**

```python
# Disable for local development (not recommended for production)
config = ClientConfig(verify_ssl=False)
```

**Timeout Errors**

```python
# Increase timeout for long-running queries
config = ClientConfig(timeout=120.0)  # 2 minutes
```

**Network Errors**

```python
# Increase retry attempts
config = ClientConfig(max_retries=5)
```

## License

This client is part of the mcp-bigquery-server project. See the main project LICENSE file for details.

## Support

For issues, questions, or contributions, please refer to the main project repository.
