# MCP BigQuery Client & Summarizer

This document describes the client and summarizer utilities for invoking the MCP BigQuery server from agent code and summarizing large query results for LLM consumption.

## Overview

The agent package provides two main components:

1. **MCPBigQueryClient**: An async HTTP client that wraps the MCP BigQuery REST API with authentication, retry logic, and typed responses
2. **ResultSummarizer**: Utilities to summarize large BigQuery result sets into compact representations suitable for LLM processing

## MCPBigQueryClient

### Features

- Async/await support using httpx
- Automatic JWT authentication with Supabase tokens
- Exponential backoff retry logic for transient failures
- Typed response models using Pydantic
- Comprehensive error handling with custom exceptions

### Basic Usage

```python
import asyncio
from mcp_bigquery.agent import MCPBigQueryClient

async def example():
    # Initialize client
    async with MCPBigQueryClient(
        base_url="http://localhost:8000",
        auth_token="your-jwt-token",
        session_id="optional-session-id",
    ) as client:
        # Execute a query
        result = await client.execute_sql("SELECT * FROM dataset.table LIMIT 10")
        
        if result.error:
            print(f"Query failed: {result.error}")
        else:
            print(f"Rows: {len(result.rows)}")
            for row in result.rows:
                print(row)

asyncio.run(example())
```

### Available Methods

#### Query Execution

```python
result = await client.execute_sql(
    sql="SELECT * FROM table",
    maximum_bytes_billed=1000000000,  # 1GB default
    use_cache=True,
)
```

Returns `QueryResult` with:
- `rows`: List of result rows as dicts
- `statistics`: Query execution statistics
- `cached`: Whether result was from cache
- `error`: Error message if query failed

#### Dataset Discovery

```python
datasets = await client.get_datasets()

for dataset in datasets:
    print(f"{dataset.dataset_id} - {dataset.description}")
```

Returns list of `DatasetInfo` objects.

#### Table Discovery

```python
tables = await client.get_tables("dataset_id")

for table in tables:
    print(f"{table.table_id}: {table.num_rows} rows")
```

Returns list of `TableInfo` objects.

#### Schema Introspection

```python
schema = await client.get_table_schema(
    dataset_id="my_dataset",
    table_id="my_table",
    include_samples=True,
)

print(f"Fields: {len(schema.schema_fields)}")
for field in schema.schema_fields:
    print(f"- {field['name']}: {field['type']}")

if schema.sample_rows:
    print(f"Sample data: {schema.sample_rows[:5]}")
```

Returns `TableSchema` object.

#### Health Check

```python
health = await client.health_check()
print(f"Status: {health.status}")
print(f"Timestamp: {health.timestamp}")
```

#### Additional Methods

- `explain_table()`: Get detailed table explanation and metadata
- `analyze_query_performance()`: Analyze query performance and get optimization suggestions
- `manage_cache()`: Manage query result cache
- `get_query_suggestions()`: Get query suggestions based on context

### Error Handling

The client raises specific exceptions for different error types:

```python
from mcp_bigquery.core.auth import AuthenticationError, AuthorizationError

try:
    result = await client.execute_sql("SELECT * FROM restricted_table")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except AuthorizationError as e:
    print(f"Access denied: {e}")
except Exception as e:
    print(f"Other error: {e}")
```

### Retry Logic

The client automatically retries on:
- Network errors (connection failures, timeouts)
- Server errors (5xx status codes)

The client does NOT retry on:
- Authentication errors (401)
- Authorization errors (403)
- Client errors (4xx except auth)

Default retry configuration:
- Maximum retries: 3
- Exponential backoff: 2^retry_count seconds
- Timeout: 30 seconds

Configure retry behavior:

```python
client = MCPBigQueryClient(
    base_url="http://localhost:8000",
    max_retries=5,
    timeout=60.0,
)
```

## ResultSummarizer

### Features

- Limit rows to meet token budget constraints
- Compute descriptive statistics (mean, median, std, percentiles)
- Generate high-level text summaries
- Produce visualization-ready aggregates
- Handle numeric, categorical, datetime, and boolean columns
- Efficient sampling for large datasets

### Basic Usage

```python
from mcp_bigquery.agent import ResultSummarizer

# Initialize summarizer
summarizer = ResultSummarizer(
    max_rows=100,           # Maximum rows to analyze
    max_categories=10,      # Maximum categories to show
    include_samples=True,   # Include sample values
)

# Query results from BigQuery
rows = [
    {"name": "Alice", "age": 30, "salary": 75000},
    {"name": "Bob", "age": 35, "salary": 85000},
    # ... more rows
]

# Generate summary
summary = summarizer.summarize(rows)

print(f"Total Rows: {summary.total_rows}")
print(f"Key Insights: {summary.key_insights}")
```

### Summary Features

#### Column Statistics

For each column, the summarizer computes:

**Numeric columns:**
- Count, null count, null percentage
- Min, max, mean, median, standard deviation
- 25th and 75th percentiles

**Categorical columns:**
- Count, null count, null percentage
- Unique value count
- Most common values with frequencies
- Sample values

**Boolean columns:**
- Count, null count, null percentage
- Value distribution

#### Key Insights

The summarizer generates automatic insights:
- Dataset size characteristics
- Null value warnings
- Data type distribution
- High cardinality columns
- Numeric variability

#### Visualization Suggestions

Based on data characteristics, suggests appropriate visualizations:
- Time series plots for datetime + numeric
- Bar charts for categorical + numeric
- Scatter plots for numeric pairs
- Histograms for distributions
- Pie charts for categorical data

### Text Formatting

Format summary as human-readable text for LLM:

```python
text = summarizer.format_summary_text(summary)
print(text)
```

Output example:
```
# Query Result Summary

**Total Rows:** 1,000
**Total Columns:** 4

## Key Insights
- Dataset contains 1,000 rows
- Query returns 4 columns
- Column types: 2 numeric, 2 categorical

## Column Statistics

### age (numeric)
- **Non-null values:** 950 (95.0%)
- **Mean:** 32.45
- **Median:** 31.00
- **Range:** [22.00, 65.00]

### department (categorical)
- **Non-null values:** 1,000 (100.0%)
- **Most common values:**
  - Engineering: 450 occurrences
  - Sales: 350 occurrences
  - Marketing: 200 occurrences

## Visualization Suggestions
1. **bar**: Bar chart of salary by department
2. **histogram**: Distribution of age
```

### Aggregation

Create aggregates for visualization:

```python
# Group by category with numeric aggregation
agg = summarizer.create_aggregate_summary(
    rows,
    group_by="department",
    numeric_cols=["salary"],
)

# Returns aggregated data suitable for charts
```

### Limiting Rows

Limit results to control token usage:

```python
# Limit to first 50 rows
limited = summarizer.limit_rows(rows, max_rows=50)
```

## Complete Example

```python
import asyncio
from mcp_bigquery.agent import MCPBigQueryClient, ResultSummarizer

async def analyze_data():
    # Connect to server
    async with MCPBigQueryClient(
        base_url="http://localhost:8000",
        auth_token="jwt-token",
    ) as client:
        
        # Execute query
        result = await client.execute_sql("""
            SELECT 
                employee_name,
                department,
                salary,
                hire_date
            FROM employees
            WHERE active = true
            LIMIT 1000
        """)
        
        if result.error:
            print(f"Error: {result.error}")
            return
        
        # Summarize results
        summarizer = ResultSummarizer(max_rows=100)
        summary = summarizer.summarize(result.rows)
        
        # Format for LLM
        text = summarizer.format_summary_text(summary)
        
        # Send to LLM with context
        prompt = f"""
        I've queried employee data from BigQuery. Here's a summary:
        
        {text}
        
        Based on this data, what insights can you provide about:
        1. Salary distribution across departments
        2. Hiring trends over time
        3. Potential outliers or anomalies
        """
        
        print(prompt)

asyncio.run(analyze_data())
```

## Best Practices

### Token Budget Management

1. **Use sampling**: For large result sets, let the summarizer sample rows
2. **Limit categories**: Reduce `max_categories` for high-cardinality data
3. **Disable samples**: Set `include_samples=False` to save tokens
4. **Pre-filter queries**: Use WHERE and LIMIT clauses in SQL

### Error Handling

```python
from mcp_bigquery.core.auth import AuthenticationError, AuthorizationError

try:
    async with MCPBigQueryClient(base_url, auth_token) as client:
        result = await client.execute_sql(sql)
        
        if result.error:
            # Handle query-level errors
            handle_query_error(result.error)
        else:
            # Process results
            process_results(result.rows)
            
except AuthenticationError:
    # Re-authenticate or refresh token
    refresh_authentication()
    
except AuthorizationError:
    # User lacks required permissions
    request_access()
    
except Exception as e:
    # Other errors
    log_error(e)
```

### Performance Optimization

1. **Reuse client instances**: Create one client per session
2. **Enable caching**: Set `use_cache=True` for repeated queries
3. **Batch operations**: Combine multiple small queries when possible
4. **Set byte limits**: Use `maximum_bytes_billed` to control costs

### Security

1. **Rotate tokens**: Regularly refresh JWT tokens
2. **Use HTTPS**: Always connect via HTTPS in production
3. **Validate input**: Sanitize SQL before execution
4. **Check permissions**: Verify user has required access before queries

## Testing

Unit tests are provided in `tests/agent/`:
- `test_mcp_client.py`: Client functionality with mocked HTTP responses
- `test_summarizer.py`: Summarizer with various data types

Run tests:
```bash
uv run pytest tests/agent/ -v
```

## Dependencies

Required packages (already in pyproject.toml):
- `httpx>=0.24.0`: Async HTTP client
- `pandas>=2.0.0`: Data analysis for summarization
- `pydantic>=2.0.0`: Data validation and models

## API Reference

See module docstrings for detailed API documentation:
- `mcp_bigquery.agent.mcp_client`
- `mcp_bigquery.agent.summarizer`
