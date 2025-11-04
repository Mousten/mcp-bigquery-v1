"""Tests for MCP BigQuery client."""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from mcp_bigquery.client import (
    MCPClient,
    ClientConfig,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    ServerError,
    NetworkError,
)


@pytest.fixture
def client_config():
    """Create a test client configuration."""
    return ClientConfig(
        base_url="http://localhost:8000",
        auth_token="test-token",
        timeout=10.0,
        max_retries=2,
        retry_delay=0.1
    )


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    mock = AsyncMock(spec=httpx.AsyncClient)
    mock.is_closed = False
    return mock


class TestMCPClientInitialization:
    """Tests for MCPClient initialization and lifecycle."""
    
    def test_init(self, client_config):
        """Test client initialization."""
        client = MCPClient(client_config)
        assert client.config == client_config
    
    @pytest.mark.asyncio
    async def test_context_manager(self, client_config):
        """Test async context manager."""
        async with MCPClient(client_config) as client:
            assert isinstance(client, MCPClient)
    
    @pytest.mark.asyncio
    async def test_close(self, client_config):
        """Test explicit close (no-op for backwards compatibility)."""
        client = MCPClient(client_config)
        await client.close()
    
    def test_get_headers_with_token(self, client_config):
        """Test headers include auth token."""
        client = MCPClient(client_config)
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"
    
    def test_get_headers_without_token(self):
        """Test headers without auth token."""
        config = ClientConfig(base_url="http://localhost:8000")
        client = MCPClient(config)
        headers = client._get_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"


class TestMCPClientRequests:
    """Tests for HTTP request handling."""
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, client_config, mock_http_client):
        """Test successful request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client._make_request("GET", "/test")
            
            assert result == {"result": "success"}
            mock_http_client.request.assert_called_once()
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_with_json_data(self, client_config, mock_http_client):
        """Test request with JSON data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            await client._make_request(
                "POST",
                "/test",
                json_data={"key": "value"}
            )
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["json"] == {"key": "value"}
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_with_params(self, client_config, mock_http_client):
        """Test request with query parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            await client._make_request(
                "GET",
                "/test",
                params={"param1": "value1"}
            )
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["params"] == {"param1": "value1"}
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authentication_error(self, client_config, mock_http_client):
        """Test 401 raises AuthenticationError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid token"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(AuthenticationError) as exc_info:
                await client._make_request("GET", "/test")
            
            assert "Invalid token" in str(exc_info.value)
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authorization_error(self, client_config, mock_http_client):
        """Test 403 raises AuthorizationError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Access denied"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(AuthorizationError) as exc_info:
                await client._make_request("GET", "/test")
            
            assert "Access denied" in str(exc_info.value)
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validation_error(self, client_config, mock_http_client):
        """Test 400 raises ValidationError."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Invalid input"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(ValidationError) as exc_info:
                await client._make_request("GET", "/test")
            
            assert "Invalid input" in str(exc_info.value)
            mock_http_client.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_server_error_retry(self, client_config, mock_http_client):
        """Test server error triggers retry."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal error"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(ServerError):
                await client._make_request("GET", "/test")
            
            # Should retry max_retries + 1 times (initial + retries)
            assert mock_http_client.request.call_count == 3
            # aclose called 3 times (once per attempt)
            assert mock_http_client.aclose.call_count == 3
    
    @pytest.mark.asyncio
    async def test_server_error_eventual_success(self, client_config, mock_http_client):
        """Test server error succeeds on retry."""
        responses = [
            Mock(status_code=500, json=lambda: {"error": "Error"}),
            Mock(status_code=200, json=lambda: {"result": "success"}),
        ]
        mock_http_client.request = AsyncMock(side_effect=responses)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client._make_request("GET", "/test")
            assert result == {"result": "success"}
            assert mock_http_client.request.call_count == 2
            # aclose called 2 times (once per attempt)
            assert mock_http_client.aclose.call_count == 2
    
    @pytest.mark.asyncio
    async def test_timeout_retry(self, client_config, mock_http_client):
        """Test timeout triggers retry."""
        mock_http_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(NetworkError) as exc_info:
                await client._make_request("GET", "/test")
            
            assert "timeout" in str(exc_info.value).lower()
            assert mock_http_client.request.call_count == 3
            assert mock_http_client.aclose.call_count == 3
    
    @pytest.mark.asyncio
    async def test_network_error_retry(self, client_config, mock_http_client):
        """Test network error triggers retry."""
        mock_http_client.request = AsyncMock(
            side_effect=httpx.NetworkError("Connection failed")
        )
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(NetworkError) as exc_info:
                await client._make_request("GET", "/test")
            
            assert "Connection failed" in str(exc_info.value)
            assert mock_http_client.request.call_count == 3
            assert mock_http_client.aclose.call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self, client_config, mock_http_client):
        """Test auth errors don't trigger retry."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(AuthenticationError):
                await client._make_request("GET", "/test")
            
            # Should not retry
            assert mock_http_client.request.call_count == 1
            mock_http_client.aclose.assert_called_once()


class TestMCPClientMethods:
    """Tests for client API methods."""
    
    @pytest.mark.asyncio
    async def test_execute_sql(self, client_config, mock_http_client):
        """Test execute_sql method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rows": [{"col1": "value1"}],
            "total_rows": 1
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.execute_sql("SELECT 1")
            
            assert result["rows"] == [{"col1": "value1"}]
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "POST"
            assert "/tools/execute_bigquery_sql" in call_args[1]["url"]
            assert call_args[1]["json"]["sql"] == "SELECT 1"
    
    @pytest.mark.asyncio
    async def test_execute_sql_with_options(self, client_config, mock_http_client):
        """Test execute_sql with custom options."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rows": []}
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            await client.execute_sql(
                "SELECT 1",
                maximum_bytes_billed=500000000,
                use_cache=False
            )
            
            call_args = mock_http_client.request.call_args
            json_data = call_args[1]["json"]
            assert json_data["maximum_bytes_billed"] == 500000000
            assert json_data["use_cache"] is False
    
    @pytest.mark.asyncio
    async def test_list_datasets(self, client_config, mock_http_client):
        """Test list_datasets method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "datasets": ["dataset1", "dataset2"]
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.list_datasets()
            
            assert result["datasets"] == ["dataset1", "dataset2"]
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "GET"
            assert "/tools/datasets" in call_args[1]["url"]
    
    @pytest.mark.asyncio
    async def test_list_tables(self, client_config, mock_http_client):
        """Test list_tables method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tables": ["table1", "table2"]
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.list_tables("my_dataset")
            
            assert result["tables"] == ["table1", "table2"]
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "POST"
            assert "/tools/get_tables" in call_args[1]["url"]
            assert call_args[1]["json"]["dataset_id"] == "my_dataset"
    
    @pytest.mark.asyncio
    async def test_get_table_schema(self, client_config, mock_http_client):
        """Test get_table_schema method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "schema": [{"name": "col1", "type": "STRING"}]
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.get_table_schema("my_dataset", "my_table")
            
            assert result["schema"] == [{"name": "col1", "type": "STRING"}]
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "POST"
            assert "/tools/get_table_schema" in call_args[1]["url"]
            json_data = call_args[1]["json"]
            assert json_data["dataset_id"] == "my_dataset"
            assert json_data["table_id"] == "my_table"
    
    @pytest.mark.asyncio
    async def test_explain_table(self, client_config, mock_http_client):
        """Test explain_table method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "explanation": "Table details",
            "usage_stats": {}
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.explain_table(
                "my_project",
                "my_dataset",
                "my_table"
            )
            
            assert "explanation" in result
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "POST"
            assert "/tools/explain_table" in call_args[1]["url"]
            json_data = call_args[1]["json"]
            assert json_data["project_id"] == "my_project"
            assert json_data["dataset_id"] == "my_dataset"
            assert json_data["table_id"] == "my_table"
    
    @pytest.mark.asyncio
    async def test_get_query_suggestions(self, client_config, mock_http_client):
        """Test get_query_suggestions method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "suggestions": ["SELECT * FROM table1"]
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.get_query_suggestions(
                tables_mentioned=["table1"],
                query_context="Get all rows"
            )
            
            assert "suggestions" in result
            
            call_args = mock_http_client.request.call_args
            json_data = call_args[1]["json"]
            assert json_data["tables_mentioned"] == ["table1"]
            assert json_data["query_context"] == "Get all rows"
    
    @pytest.mark.asyncio
    async def test_analyze_query_performance(self, client_config, mock_http_client):
        """Test analyze_query_performance method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "analysis": "Performance details"
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.analyze_query_performance("SELECT 1")
            
            assert "analysis" in result
            
            call_args = mock_http_client.request.call_args
            assert "/tools/analyze_query_performance" in call_args[1]["url"]
    
    @pytest.mark.asyncio
    async def test_get_schema_changes(self, client_config, mock_http_client):
        """Test get_schema_changes method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "changes": []
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.get_schema_changes(
                "my_project",
                "my_dataset",
                "my_table"
            )
            
            assert "changes" in result
            
            call_args = mock_http_client.request.call_args
            assert call_args[1]["method"] == "GET"
            params = call_args[1]["params"]
            assert params["project_id"] == "my_project"
            assert params["dataset_id"] == "my_dataset"
            assert params["table_id"] == "my_table"
    
    @pytest.mark.asyncio
    async def test_manage_cache(self, client_config, mock_http_client):
        """Test manage_cache method."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "Cache cleared"
        }
        mock_http_client.request = AsyncMock(return_value=mock_response)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            result = await client.manage_cache("clear", target="all")
            
            assert result["result"] == "Cache cleared"
            
            call_args = mock_http_client.request.call_args
            json_data = call_args[1]["json"]
            assert json_data["action"] == "clear"
            assert json_data["target"] == "all"


class TestMCPClientStreaming:
    """Tests for streaming functionality."""
    
    @pytest.mark.asyncio
    async def test_stream_events(self, client_config, mock_http_client):
        """Test streaming events via NDJSON."""
        events = [
            {"type": "connection_established", "client_id": "123"},
            {"type": "query_started", "query_id": "q1"},
            {"type": "query_completed", "query_id": "q1"},
        ]
        
        async def mock_aiter_lines():
            for event in events:
                yield json.dumps(event)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines
        
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        
        mock_http_client.stream = Mock(return_value=mock_stream)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            received_events = []
            async for event in client.stream_events("test_channel"):
                received_events.append(event)
            
            assert len(received_events) == 3
            assert received_events[0]["type"] == "connection_established"
            assert received_events[1]["type"] == "query_started"
            assert received_events[2]["type"] == "query_completed"
    
    @pytest.mark.asyncio
    async def test_stream_events_skip_empty_lines(self, client_config, mock_http_client):
        """Test streaming skips empty lines (heartbeats)."""
        async def mock_aiter_lines():
            yield json.dumps({"type": "event1"})
            yield ""
            yield "\n"
            yield json.dumps({"type": "event2"})
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines
        
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        
        mock_http_client.stream = Mock(return_value=mock_stream)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            received_events = []
            async for event in client.stream_events():
                received_events.append(event)
            
            assert len(received_events) == 2
            assert received_events[0]["type"] == "event1"
            assert received_events[1]["type"] == "event2"
    
    @pytest.mark.asyncio
    async def test_stream_events_authentication_error(self, client_config, mock_http_client):
        """Test streaming raises AuthenticationError on 401."""
        mock_response = Mock()
        mock_response.status_code = 401
        
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        
        mock_http_client.stream = Mock(return_value=mock_stream)
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(AuthenticationError):
                async for event in client.stream_events():
                    pass
    
    @pytest.mark.asyncio
    async def test_stream_events_network_error(self, client_config, mock_http_client):
        """Test streaming raises NetworkError on connection failure."""
        mock_http_client.stream = Mock(
            side_effect=httpx.NetworkError("Connection failed")
        )
        
        client = MCPClient(client_config)
        
        with patch('mcp_bigquery.client.mcp_client.httpx.AsyncClient', return_value=mock_http_client):
            with pytest.raises(NetworkError):
                async for event in client.stream_events():
                    pass


class TestErrorExtraction:
    """Tests for error message extraction."""
    
    def test_extract_error_with_error_field(self, client_config):
        """Test extracting error from 'error' field."""
        client = MCPClient(client_config)
        
        response = Mock()
        response.json.return_value = {"error": "Something went wrong"}
        
        error_msg = client._extract_error(response)
        assert error_msg == "Something went wrong"
    
    def test_extract_error_with_detail_field(self, client_config):
        """Test extracting error from 'detail' field."""
        client = MCPClient(client_config)
        
        response = Mock()
        response.json.return_value = {"detail": "Validation failed"}
        
        error_msg = client._extract_error(response)
        assert error_msg == "Validation failed"
    
    def test_extract_error_fallback_to_text(self, client_config):
        """Test fallback to response text."""
        client = MCPClient(client_config)
        
        response = Mock()
        response.json.side_effect = Exception("Not JSON")
        response.text = "Error text"
        response.status_code = 500
        
        error_msg = client._extract_error(response)
        assert error_msg == "Error text"
    
    def test_extract_error_empty_text(self, client_config):
        """Test fallback when text is empty."""
        client = MCPClient(client_config)
        
        response = Mock()
        response.json.side_effect = Exception("Not JSON")
        response.text = ""
        response.status_code = 500
        
        error_msg = client._extract_error(response)
        assert "HTTP 500" in error_msg
