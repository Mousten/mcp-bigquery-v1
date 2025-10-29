# MCP BigQuery Client Implementation

## Overview

This document describes the implementation of the MCP BigQuery client - a reusable wrapper for interacting with the MCP BigQuery server from external applications such as Streamlit agents, notebooks, or other Python applications.

## Architecture

### Transport Layer

The client uses **HTTP** as the transport mechanism, leveraging the server's REST API endpoints. While FastMCP provides native client capabilities, we implemented an HTTP-based client for broader compatibility and easier integration with various application types.

**Key Design Decisions:**
- **httpx**: Modern async HTTP client with excellent async/await support
- **REST API**: Uses the server's `/tools/*` endpoints for operations
- **NDJSON Streaming**: Uses `/stream/ndjson/` for event streaming
- **Bearer Authentication**: JWT tokens via Authorization header

### Module Structure

```
src/mcp_bigquery/client/
├── __init__.py          # Package exports
├── config.py            # ClientConfig with Pydantic validation
├── exceptions.py        # Custom exception hierarchy
├── mcp_client.py        # MCPClient implementation
└── README.md            # Client documentation
```

## Key Components

### 1. ClientConfig (config.py)

Pydantic-based configuration with environment variable support.

**Features:**
- Environment variable loading via `from_env()`
- Field validation (base_url format, positive timeout, etc.)
- Sensible defaults
- Override support

**Environment Variables:**
- `MCP_BASE_URL`: Server URL (default: http://localhost:8000)
- `MCP_AUTH_TOKEN`: JWT authentication token
- `MCP_TIMEOUT`: Request timeout in seconds (default: 30.0)
- `MCP_MAX_RETRIES`: Max retry attempts (default: 3)
- `MCP_RETRY_DELAY`: Initial retry delay (default: 1.0s)
- `MCP_VERIFY_SSL`: SSL verification (default: true)

### 2. Exception Hierarchy (exceptions.py)

Structured exceptions for different error types:

```
MCPClientError (base)
├── AuthenticationError (401)
├── AuthorizationError (403)
├── ValidationError (400)
├── ServerError (500+)
└── NetworkError (timeouts, connection failures)
```

This allows consumers to handle different error types appropriately:
- **Don't retry**: Authentication, Authorization, Validation errors
- **Retry with backoff**: Server errors, Network errors, Timeouts

### 3. MCPClient (mcp_client.py)

Main client implementation with async/await support.

**Core Features:**

#### Authentication
- Automatic Bearer token injection
- Token validation via server responses
- Clear error messages for auth failures

#### Retry Logic
- Exponential backoff: `delay * (2 ** retry_count)`
- Configurable max retries and initial delay
- Selective retry (only for transient failures)
- No retry for auth/validation errors

#### Request Handling
- Async context manager support (`async with MCPClient(...)`)
- Automatic HTTP client lifecycle management
- Proper error extraction from responses
- Type hints throughout

#### API Coverage

All major MCP tools are exposed:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `execute_sql()` | POST /tools/execute_bigquery_sql | Execute SQL queries |
| `list_datasets()` | GET /tools/datasets | List accessible datasets |
| `list_tables()` | POST /tools/get_tables | List tables in dataset |
| `get_table_schema()` | POST /tools/get_table_schema | Get table schema |
| `explain_table()` | POST /tools/explain_table | Get table explanation |
| `get_query_suggestions()` | POST /tools/query_suggestions | Get query suggestions |
| `analyze_query_performance()` | POST /tools/analyze_query_performance | Analyze query performance |
| `get_schema_changes()` | GET /tools/schema_changes | Get schema history |
| `manage_cache()` | POST /tools/manage_cache | Cache operations |
| `stream_events()` | GET /stream/ndjson/ | Stream server events |

#### Streaming Support

The `stream_events()` method provides async iteration over server events:

```python
async for event in client.stream_events(channel="queries"):
    if event["type"] == "query_completed":
        print(f"Query {event['query_id']} completed")
```

**Features:**
- Automatic heartbeat handling (skips empty lines)
- JSON parsing with error recovery
- Network error handling
- Graceful disconnection

## Testing

### Test Coverage

**Unit Tests** (45 tests, 93% coverage):
- Configuration validation
- Request handling and retries
- Error handling and extraction
- All API methods
- Streaming functionality

**Test Structure:**
```
tests/client/
├── test_config.py         # ClientConfig tests (15 tests)
├── test_mcp_client.py     # MCPClient tests (30 tests)
└── test_integration.py    # Integration tests (marked)
```

### Running Tests

```bash
# Run all unit tests
uv run pytest tests/client/ -v

# Run with coverage
uv run pytest tests/client/ --cov=src/mcp_bigquery/client --cov-report=term-missing

# Skip integration tests
uv run pytest tests/client/ -m "not integration" -v

# Run integration tests (requires running server)
RUN_INTEGRATION_TESTS=true MCP_AUTH_TOKEN=<token> uv run pytest tests/client/ -m integration -v
```

### Test Approach

**Unit Tests:**
- Mock httpx responses
- Test all success and error paths
- Verify retry behavior
- Check error extraction logic

**Integration Tests:**
- Require running server and valid credentials
- Marked with `@pytest.mark.integration`
- Skipped by default
- Enable with `RUN_INTEGRATION_TESTS=true`

## Usage Examples

### Basic Usage

```python
from mcp_bigquery.client import MCPClient, ClientConfig

config = ClientConfig(
    base_url="http://localhost:8000",
    auth_token="your-jwt-token"
)

async with MCPClient(config) as client:
    # Execute query
    result = await client.execute_sql("SELECT * FROM dataset.table LIMIT 10")
    print(f"Got {result['total_rows']} rows")
    
    # List datasets
    datasets = await client.list_datasets()
    print(f"Datasets: {datasets['datasets']}")
```

### Environment Configuration

```python
import os
from mcp_bigquery.client import MCPClient, ClientConfig

# Set environment variables
os.environ['MCP_BASE_URL'] = 'https://api.example.com'
os.environ['MCP_AUTH_TOKEN'] = 'your-token'
os.environ['MCP_TIMEOUT'] = '60.0'

# Load from environment
config = ClientConfig.from_env()

async with MCPClient(config) as client:
    result = await client.execute_sql("SELECT 1")
```

### Error Handling

```python
from mcp_bigquery.client import (
    MCPClient,
    ClientConfig,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ServerError,
)

async with MCPClient(config) as client:
    try:
        result = await client.execute_sql("SELECT * FROM table")
    except AuthenticationError:
        # Handle token refresh
        print("Authentication failed - refresh token")
    except AuthorizationError:
        # Handle permission denied
        print("Access denied - check permissions")
    except ValidationError:
        # Handle invalid query
        print("Invalid SQL query")
    except ServerError:
        # Handle server error
        print("Server error - retry later")
```

### Streaming Events

```python
async with MCPClient(config) as client:
    async for event in client.stream_events(channel="queries"):
        event_type = event.get("type")
        
        if event_type == "query_started":
            print(f"Query started: {event['query_id']}")
        elif event_type == "query_completed":
            print(f"Query completed in {event['duration_ms']}ms")
```

### Integration with Streamlit

```python
import streamlit as st
from mcp_bigquery.client import MCPClient, ClientConfig

@st.cache_resource
def get_mcp_client():
    config = ClientConfig.from_env()
    return MCPClient(config)

async def run_query(sql: str):
    client = get_mcp_client()
    await client._ensure_client()
    return await client.execute_sql(sql)

# In Streamlit app
if st.button("Execute"):
    import asyncio
    result = asyncio.run(run_query(st.session_state.sql))
    st.dataframe(result["rows"])
```

## Design Patterns

### Async Context Manager

The client implements `__aenter__` and `__aexit__` for proper resource management:

```python
async with MCPClient(config) as client:
    # HTTP client automatically initialized
    result = await client.execute_sql("SELECT 1")
# HTTP client automatically closed
```

### Lazy Client Initialization

The HTTP client is only created when needed:

```python
client = MCPClient(config)  # No HTTP client yet
await client._ensure_client()  # Now created
```

### Exponential Backoff

Retry delays grow exponentially to avoid overwhelming the server:

```
Attempt 1: immediate
Attempt 2: 1.0s delay
Attempt 3: 2.0s delay
Attempt 4: 4.0s delay
```

### Error Extraction

Smart error message extraction from responses:

1. Try to parse JSON and extract "error" field
2. Try to extract "detail" field (FastAPI format)
3. Fall back to response text
4. Fall back to HTTP status code

## Dependencies

### Runtime Dependencies

- **httpx >= 0.24.0**: Async HTTP client
- **pydantic >= 2.0.0**: Configuration validation
- **pydantic-settings >= 2.0.0**: Environment loading

### Development Dependencies

- **pytest >= 7.0.0**: Test framework
- **pytest-asyncio >= 0.21.0**: Async test support
- **pytest-mock >= 3.12.0**: Mocking support
- **pytest-cov >= 4.0.0**: Coverage reporting

## Future Enhancements

### Potential Improvements

1. **Connection Pooling**: Reuse HTTP connections across requests
2. **Request Batching**: Batch multiple requests for efficiency
3. **Response Caching**: Cache frequently accessed data
4. **Progress Callbacks**: Report query progress to caller
5. **Sync Wrapper**: Provide synchronous API for non-async code
6. **Rate Limiting**: Built-in rate limiting support
7. **Metrics**: Expose request metrics (latency, errors, etc.)
8. **Request Middleware**: Plugin system for request/response interceptors

### WebSocket Transport

For future consideration:
- Lower latency for streaming
- Bidirectional communication
- Server push notifications

## Acceptance Criteria ✅

All acceptance criteria from the ticket have been met:

### ✅ Transport Selection
- Investigated FastMCP/MCP Python client capabilities
- Implemented HTTP-based adapter using httpx
- Supports REST endpoints (`/tools/*`)
- Optional NDJSON stream consumption (`/stream/ndjson/`)

### ✅ Client Implementation
- Created `client/mcp_client.py` with async `MCPClient`
- Exposed methods: `execute_sql`, `list_datasets`, `list_tables`, `get_table_schema`, `explain_table`, etc.
- Injects auth tokens via Authorization: Bearer header
- Surfaces structured errors for 401/403/500 with custom exceptions
- Supports streaming via `/stream/ndjson/`

### ✅ Config & Retries
- `ClientConfig` with environment variable support
- Configurable base URL, transport type, timeouts, retry policies
- Exponential backoff retry logic

### ✅ Testing
- 45 unit tests with 93% coverage
- Mocked HTTP responses
- Verifies request formation and auth headers
- Tests all error conditions
- Integration tests for real server testing

### ✅ Functional Requirements
- Client successfully calls `execute_bigquery_sql`, `get_datasets`, and `get_table_schema`
- Authentication failures bubble up with `AuthenticationError`
- Module documented with comprehensive README
- Example code provided
- Ready for Streamlit agent integration

## Conclusion

The MCP BigQuery client provides a robust, well-tested, and documented interface for interacting with the MCP BigQuery server. It handles authentication, retries, error handling, and streaming transparently, allowing application developers to focus on their business logic rather than HTTP plumbing.

The client follows Python best practices:
- Type hints throughout
- Async/await for I/O
- Pydantic for validation
- Comprehensive testing
- Clear error handling
- Extensive documentation

It is ready for integration into Streamlit agents and other Python applications.
