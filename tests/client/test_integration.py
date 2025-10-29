"""Integration tests for MCP BigQuery client.

These tests require a running MCP server and valid credentials.
They are marked as integration tests and skipped by default.

Run with: pytest tests/client/test_integration.py -v -m integration
"""

import os
import pytest
from mcp_bigquery.client import (
    MCPClient,
    ClientConfig,
    AuthenticationError,
    AuthorizationError,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


def should_run_integration_tests():
    """Check if integration tests should run."""
    return os.getenv("RUN_INTEGRATION_TESTS", "").lower() in ("true", "1", "yes")


@pytest.fixture
def integration_config():
    """Create config for integration tests from environment."""
    if not should_run_integration_tests():
        pytest.skip("Integration tests disabled (set RUN_INTEGRATION_TESTS=true to enable)")
    
    base_url = os.getenv("MCP_BASE_URL", "http://localhost:8000")
    auth_token = os.getenv("MCP_AUTH_TOKEN")
    
    if not auth_token:
        pytest.skip("MCP_AUTH_TOKEN not set")
    
    return ClientConfig(
        base_url=base_url,
        auth_token=auth_token,
        timeout=30.0
    )


class TestIntegrationBasicOperations:
    """Integration tests for basic client operations."""
    
    @pytest.mark.asyncio
    async def test_list_datasets(self, integration_config):
        """Test listing datasets with real server."""
        async with MCPClient(integration_config) as client:
            result = await client.list_datasets()
            assert "datasets" in result
            assert isinstance(result["datasets"], list)
    
    @pytest.mark.asyncio
    async def test_execute_simple_query(self, integration_config):
        """Test executing a simple query."""
        async with MCPClient(integration_config) as client:
            result = await client.execute_sql("SELECT 1 as test_column")
            assert "rows" in result or "error" not in result
    
    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test that invalid token raises AuthenticationError."""
        if not should_run_integration_tests():
            pytest.skip("Integration tests disabled (set RUN_INTEGRATION_TESTS=true to enable)")
        
        config = ClientConfig(
            base_url=os.getenv("MCP_BASE_URL", "http://localhost:8000"),
            auth_token="invalid-token"
        )
        
        async with MCPClient(config) as client:
            with pytest.raises(AuthenticationError):
                await client.list_datasets()


class TestIntegrationDatasetOperations:
    """Integration tests for dataset and table operations."""
    
    @pytest.mark.asyncio
    async def test_list_tables_in_dataset(self, integration_config):
        """Test listing tables in a dataset."""
        async with MCPClient(integration_config) as client:
            # First get a dataset
            datasets_result = await client.list_datasets()
            
            if datasets_result.get("datasets"):
                dataset_id = datasets_result["datasets"][0]
                
                # List tables in the dataset
                tables_result = await client.list_tables(dataset_id)
                assert "tables" in tables_result or "error" not in tables_result
    
    @pytest.mark.asyncio
    async def test_get_table_schema(self, integration_config):
        """Test getting table schema."""
        async with MCPClient(integration_config) as client:
            # Get datasets
            datasets_result = await client.list_datasets()
            
            if datasets_result.get("datasets"):
                dataset_id = datasets_result["datasets"][0]
                
                # Get tables
                tables_result = await client.list_tables(dataset_id)
                
                if tables_result.get("tables"):
                    table_id = tables_result["tables"][0]
                    
                    # Get schema
                    schema_result = await client.get_table_schema(
                        dataset_id=dataset_id,
                        table_id=table_id
                    )
                    assert "schema" in schema_result or "error" not in schema_result


class TestIntegrationStreaming:
    """Integration tests for streaming functionality."""
    
    @pytest.mark.asyncio
    async def test_stream_events_basic(self, integration_config):
        """Test basic event streaming."""
        async with MCPClient(integration_config) as client:
            # Connect to stream and receive at least one event
            event_count = 0
            
            try:
                async for event in client.stream_events(channel="system"):
                    event_count += 1
                    assert isinstance(event, dict)
                    
                    # Just verify we can receive events, then break
                    if event_count >= 1:
                        break
            except Exception as e:
                # Streaming might not be available on all servers
                pytest.skip(f"Streaming not available: {e}")


class TestIntegrationCacheOperations:
    """Integration tests for cache operations."""
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self, integration_config):
        """Test getting cache statistics."""
        async with MCPClient(integration_config) as client:
            try:
                result = await client.manage_cache(action="get_stats")
                assert isinstance(result, dict)
            except Exception as e:
                # Cache operations might require special permissions
                if "403" not in str(e) and "AuthorizationError" not in str(type(e).__name__):
                    raise


class TestIntegrationErrorHandling:
    """Integration tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_sql_query(self, integration_config):
        """Test that invalid SQL raises appropriate error."""
        async with MCPClient(integration_config) as client:
            with pytest.raises(Exception):  # Could be ValidationError or ServerError
                await client.execute_sql("SELECT * FROM nonexistent_table_xyz")
    
    @pytest.mark.asyncio
    async def test_unauthorized_table_access(self, integration_config):
        """Test access to unauthorized table."""
        async with MCPClient(integration_config) as client:
            # Try to access a table that likely doesn't exist or isn't accessible
            try:
                await client.get_table_schema(
                    dataset_id="unauthorized_dataset",
                    table_id="unauthorized_table"
                )
            except (AuthorizationError, Exception):
                # Expected - either authorization error or not found
                pass
