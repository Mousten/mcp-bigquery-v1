"""Tests for MCP BigQuery HTTP client."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from mcp_bigquery.agent.mcp_client import (
    MCPBigQueryClient,
    QueryResult,
    DatasetInfo,
    TableInfo,
    TableSchema,
    HealthStatus,
)
from mcp_bigquery.core.auth import AuthenticationError, AuthorizationError


@pytest.fixture
def base_url():
    """Base URL for testing."""
    return "http://localhost:8000"


@pytest.fixture
def auth_token():
    """Test auth token."""
    return "test-jwt-token"


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.mark.asyncio
class TestMCPBigQueryClient:
    """Tests for MCPBigQueryClient."""
    
    async def test_client_initialization(self, base_url, auth_token):
        """Test client initialization."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        assert client.base_url == base_url
        assert client.auth_token == auth_token
        assert client.max_retries == 3
        assert client.timeout == 30.0
        
    async def test_context_manager(self, base_url, auth_token):
        """Test async context manager."""
        async with MCPBigQueryClient(base_url, auth_token=auth_token) as client:
            assert client._client is not None
            
    async def test_get_headers_with_auth(self, base_url, auth_token):
        """Test headers include auth token."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token, session_id="session-123")
        headers = client._get_headers()
        
        assert headers["Authorization"] == f"Bearer {auth_token}"
        assert headers["X-Session-ID"] == "session-123"
        assert headers["Content-Type"] == "application/json"
        
    async def test_get_headers_without_auth(self, base_url):
        """Test headers without auth token."""
        client = MCPBigQueryClient(base_url)
        headers = client._get_headers()
        
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"
        
    async def test_execute_sql_mcp_response(self, base_url, auth_token):
        """Test execute_sql with MCP-style response."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "query_id": "query-123",
                    "result": [{"id": 1, "name": "Alice"}],
                    "statistics": {"totalBytesProcessed": 1024},
                    "cached": False,
                })
            }],
            "isError": False,
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.execute_sql("SELECT * FROM table")
            
        assert isinstance(result, QueryResult)
        assert result.query_id == "query-123"
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "Alice"
        assert result.statistics["totalBytesProcessed"] == 1024
        assert not result.cached
        
        await client.close()
        
    async def test_execute_sql_direct_response(self, base_url, auth_token):
        """Test execute_sql with direct response."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [{"id": 2, "name": "Bob"}],
            "statistics": {"totalRows": 1},
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.execute_sql("SELECT * FROM table")
            
        assert isinstance(result, QueryResult)
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "Bob"
        
        await client.close()
        
    async def test_execute_sql_error_response(self, base_url, auth_token):
        """Test execute_sql with error response."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": "Query failed",
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.execute_sql("SELECT * FROM table")
            
        assert isinstance(result, QueryResult)
        assert result.error == "Query failed"
        assert len(result.rows) == 0
        
        await client.close()
        
    async def test_get_datasets(self, base_url, auth_token):
        """Test get_datasets."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "datasets": [
                        {
                            "datasetId": "dataset1",
                            "projectId": "project1",
                            "location": "US",
                            "description": "Test dataset",
                        }
                    ]
                })
            }]
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            datasets = await client.get_datasets()
            
        assert len(datasets) == 1
        assert isinstance(datasets[0], DatasetInfo)
        assert datasets[0].dataset_id == "dataset1"
        assert datasets[0].project_id == "project1"
        assert datasets[0].location == "US"
        
        await client.close()
        
    async def test_get_tables(self, base_url, auth_token):
        """Test get_tables."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tables": [
                {
                    "tableId": "table1",
                    "projectId": "project1",
                    "type": "TABLE",
                    "numRows": 1000,
                }
            ]
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            tables = await client.get_tables("dataset1")
            
        assert len(tables) == 1
        assert isinstance(tables[0], TableInfo)
        assert tables[0].table_id == "table1"
        assert tables[0].dataset_id == "dataset1"
        assert tables[0].num_rows == 1000
        
        await client.close()
        
    async def test_get_table_schema(self, base_url, auth_token):
        """Test get_table_schema."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "projectId": "project1",
                    "schema": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "name", "type": "STRING"},
                    ],
                    "numRows": 1000,
                    "sampleRows": [{"id": 1, "name": "Alice"}],
                })
            }]
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            schema = await client.get_table_schema("dataset1", "table1")
            
        assert isinstance(schema, TableSchema)
        assert schema.dataset_id == "dataset1"
        assert schema.table_id == "table1"
        assert len(schema.schema_fields) == 2
        assert schema.schema_fields[0]["name"] == "id"
        assert len(schema.sample_rows) == 1
        
        await client.close()
        
    async def test_health_check(self, base_url, auth_token):
        """Test health_check."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "timestamp": 1234567890.0,
            "connections": {"total": 5},
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            health = await client.health_check()
            
        assert isinstance(health, HealthStatus)
        assert health.status == "healthy"
        assert health.timestamp == 1234567890.0
        
        await client.close()
        
    async def test_authentication_error(self, base_url, auth_token):
        """Test handling of authentication errors."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b'{"error": "Invalid token"}'
        mock_response.json.return_value = {"error": "Invalid token"}
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            
            with pytest.raises(AuthenticationError) as exc_info:
                await client.execute_sql("SELECT 1")
                
            assert "Invalid token" in str(exc_info.value)
            
        await client.close()
        
    async def test_authorization_error(self, base_url, auth_token):
        """Test handling of authorization errors."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.content = b'{"error": "Access denied"}'
        mock_response.json.return_value = {"error": "Access denied"}
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            
            with pytest.raises(AuthorizationError) as exc_info:
                await client.execute_sql("SELECT * FROM restricted")
                
            assert "Access denied" in str(exc_info.value)
            
        await client.close()
        
    async def test_retry_on_timeout(self, base_url, auth_token):
        """Test retry logic on timeout."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token, max_retries=2)
        
        # First call raises timeout, second succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TimeoutException("Timeout")
            return mock_response
        
        with patch.object(httpx.AsyncClient, 'request', side_effect=side_effect):
            await client.connect()
            result = await client.execute_sql("SELECT 1")
            
        assert isinstance(result, QueryResult)
        assert call_count == 2  # Initial + 1 retry
        
        await client.close()
        
    async def test_retry_on_network_error(self, base_url, auth_token):
        """Test retry logic on network error."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token, max_retries=2)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.NetworkError("Network error")
            return mock_response
        
        with patch.object(httpx.AsyncClient, 'request', side_effect=side_effect):
            await client.connect()
            result = await client.execute_sql("SELECT 1")
            
        assert isinstance(result, QueryResult)
        assert call_count == 2
        
        await client.close()
        
    async def test_retry_on_server_error(self, base_url, auth_token):
        """Test retry logic on 5xx server error."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token, max_retries=2)
        
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response_error
        )
        
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"result": []}
        mock_response_ok.raise_for_status.return_value = None
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_response_error
            return mock_response_ok
        
        with patch.object(httpx.AsyncClient, 'request', side_effect=side_effect):
            await client.connect()
            result = await client.execute_sql("SELECT 1")
            
        assert isinstance(result, QueryResult)
        assert call_count == 2
        
        await client.close()
        
    async def test_no_retry_on_auth_error(self, base_url, auth_token):
        """Test that auth errors are not retried."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token, max_retries=3)
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b'{"error": "Invalid token"}'
        mock_response.json.return_value = {"error": "Invalid token"}
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response
        
        with patch.object(httpx.AsyncClient, 'request', side_effect=side_effect):
            await client.connect()
            
            with pytest.raises(AuthenticationError):
                await client.execute_sql("SELECT 1")
                
        # Should not retry auth errors
        assert call_count == 1
        
        await client.close()
        
    async def test_parse_datetime_from_string(self):
        """Test datetime parsing from ISO string."""
        client = MCPBigQueryClient("http://localhost:8000")
        
        dt_str = "2023-01-15T10:30:00Z"
        result = client._parse_datetime(dt_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 15
        
    async def test_parse_datetime_from_timestamp(self):
        """Test datetime parsing from timestamp."""
        client = MCPBigQueryClient("http://localhost:8000")
        
        timestamp = 1673781000.0  # 2023-01-15 10:30:00 UTC
        result = client._parse_datetime(timestamp)
        
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        
    async def test_parse_datetime_none(self):
        """Test datetime parsing with None."""
        client = MCPBigQueryClient("http://localhost:8000")
        result = client._parse_datetime(None)
        assert result is None
        
    async def test_explain_table(self, base_url, auth_token):
        """Test explain_table method."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "table_id": "table1",
                    "description": "Test table",
                    "usage_stats": {"queries": 100},
                })
            }]
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.explain_table("project1", "dataset1", "table1")
            
        assert result["table_id"] == "table1"
        assert result["description"] == "Test table"
        
        await client.close()
        
    async def test_analyze_query_performance(self, base_url, auth_token):
        """Test analyze_query_performance method."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "analysis": {
                "recommendation": "Use LIMIT clause",
                "estimated_cost": 0.05,
            }
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.analyze_query_performance("SELECT * FROM table")
            
        assert "analysis" in result
        assert result["analysis"]["recommendation"] == "Use LIMIT clause"
        
        await client.close()
        
    async def test_manage_cache(self, base_url, auth_token):
        """Test manage_cache method."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "cleared": 10,
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.manage_cache("clear", "all")
            
        assert result["status"] == "success"
        assert result["cleared"] == 10
        
        await client.close()
        
    async def test_get_query_suggestions(self, base_url, auth_token):
        """Test get_query_suggestions method."""
        client = MCPBigQueryClient(base_url, auth_token=auth_token)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "suggestions": [
                {"sql": "SELECT * FROM table1", "score": 0.9}
            ]
        }
        
        with patch.object(httpx.AsyncClient, 'request', return_value=mock_response):
            await client.connect()
            result = await client.get_query_suggestions(tables_mentioned=["table1"])
            
        assert "suggestions" in result
        assert len(result["suggestions"]) == 1
        
        await client.close()
