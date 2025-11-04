"""Tests to verify event loop closed error is fixed in tool execution."""

import pytest
import asyncio
from unittest.mock import AsyncMock

from src.mcp_bigquery.agent.mcp_client import MCPBigQueryClient, DatasetInfo, TableInfo
from src.mcp_bigquery.agent.tools import ToolRegistry
from src.mcp_bigquery.agent.tool_executor import ToolExecutor
from src.mcp_bigquery.llm.providers.base import ToolCall


class TestEventLoopFix:
    """Tests to ensure event loop closed error is fixed."""
    
    def test_mcp_client_has_list_methods(self):
        """Test that MCPBigQueryClient has list_datasets and list_tables methods."""
        client = MCPBigQueryClient("http://localhost:8000")
        
        # Verify methods exist
        assert hasattr(client, 'list_datasets'), "list_datasets method missing"
        assert hasattr(client, 'list_tables'), "list_tables method missing"
        assert hasattr(client, 'get_datasets'), "get_datasets method missing"
        assert hasattr(client, 'get_tables'), "get_tables method missing"
        
        # Verify they're async
        assert asyncio.iscoroutinefunction(client.list_datasets)
        assert asyncio.iscoroutinefunction(client.list_tables)
        assert asyncio.iscoroutinefunction(client.get_datasets)
        assert asyncio.iscoroutinefunction(client.get_tables)
    
    @pytest.mark.asyncio
    async def test_list_datasets_and_get_datasets_are_equivalent(self):
        """Test that list_datasets is an alias for get_datasets."""
        # Create mock client
        client = MCPBigQueryClient("http://localhost:8000")
        
        # Mock the _request method to return dataset data
        client._request = AsyncMock(return_value={
            "datasets": [
                {"datasetId": "test1", "projectId": "project1"},
                {"datasetId": "test2", "projectId": "project1"},
            ]
        })
        
        # Call both methods
        result1 = await client.get_datasets()
        result2 = await client.list_datasets()
        
        # Both should return the same data
        assert len(result1) == 2
        assert len(result2) == 2
        assert result1[0].dataset_id == result2[0].dataset_id
        assert result1[1].dataset_id == result2[1].dataset_id
    
    @pytest.mark.asyncio
    async def test_list_tables_and_get_tables_are_equivalent(self):
        """Test that list_tables is an alias for get_tables."""
        # Create mock client
        client = MCPBigQueryClient("http://localhost:8000")
        
        # Mock the _request method to return table data
        client._request = AsyncMock(return_value={
            "tables": [
                {"tableId": "table1", "projectId": "project1"},
                {"tableId": "table2", "projectId": "project1"},
            ]
        })
        
        # Call both methods
        result1 = await client.get_tables("Analytics")
        result2 = await client.list_tables("Analytics")
        
        # Both should return the same data
        assert len(result1) == 2
        assert len(result2) == 2
        assert result1[0].table_id == result2[0].table_id
        assert result1[1].table_id == result2[1].table_id
    
    @pytest.mark.asyncio
    async def test_tool_executor_list_datasets_no_event_loop_error(self):
        """Test that list_datasets tool executes without event loop errors."""
        # Create mock client with proper methods
        client = AsyncMock(spec=MCPBigQueryClient)
        client.list_datasets = AsyncMock(return_value=[
            DatasetInfo(dataset_id="Analytics", project_id="test-project"),
            DatasetInfo(dataset_id="Sales", project_id="test-project"),
        ])
        client.list_tables = AsyncMock(return_value=[])
        client.get_table_schema = AsyncMock()
        client.execute_sql = AsyncMock()
        
        # Create registry and executor
        registry = ToolRegistry(client)
        executor = ToolExecutor(registry)
        
        # Create tool call
        tool_call = ToolCall(
            id="call_123",
            name="list_datasets",
            arguments={}
        )
        
        # Execute - should not raise event loop error
        result = await executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert result["tool_name"] == "list_datasets"
        assert len(result["result"]) == 2
        client.list_datasets.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tool_executor_list_tables_no_event_loop_error(self):
        """Test that list_tables tool executes without event loop errors."""
        # Create mock client with proper methods
        client = AsyncMock(spec=MCPBigQueryClient)
        client.list_datasets = AsyncMock(return_value=[])
        client.list_tables = AsyncMock(return_value=[
            TableInfo(table_id="users", dataset_id="Analytics"),
            TableInfo(table_id="events", dataset_id="Analytics"),
        ])
        client.get_table_schema = AsyncMock()
        client.execute_sql = AsyncMock()
        
        # Create registry and executor
        registry = ToolRegistry(client)
        executor = ToolExecutor(registry)
        
        # Create tool call
        tool_call = ToolCall(
            id="call_456",
            name="list_tables",
            arguments={"dataset_id": "Analytics"}
        )
        
        # Execute - should not raise event loop error
        result = await executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert result["tool_name"] == "list_tables"
        assert len(result["result"]) == 2
        client.list_tables.assert_called_once_with(dataset_id="Analytics")
    
    @pytest.mark.asyncio
    async def test_tool_executor_sequential_calls_no_event_loop_error(self):
        """Test that sequential tool calls don't cause event loop errors."""
        # Create mock client with proper methods
        client = AsyncMock(spec=MCPBigQueryClient)
        client.list_datasets = AsyncMock(return_value=[
            DatasetInfo(dataset_id="Analytics", project_id="test-project"),
        ])
        client.list_tables = AsyncMock(return_value=[
            TableInfo(table_id="users", dataset_id="Analytics"),
        ])
        client.get_table_schema = AsyncMock()
        client.execute_sql = AsyncMock()
        
        # Create registry and executor
        registry = ToolRegistry(client)
        executor = ToolExecutor(registry)
        
        # Execute list_datasets first
        tool_call_1 = ToolCall(
            id="call_1",
            name="list_datasets",
            arguments={}
        )
        result_1 = await executor.execute_single_tool(tool_call_1)
        assert result_1["success"] is True
        
        # Then execute list_tables - should not have event loop closed error
        tool_call_2 = ToolCall(
            id="call_2",
            name="list_tables",
            arguments={"dataset_id": "Analytics"}
        )
        result_2 = await executor.execute_single_tool(tool_call_2)
        assert result_2["success"] is True
        
        # Verify both were called
        client.list_datasets.assert_called_once()
        client.list_tables.assert_called_once_with(dataset_id="Analytics")
    
    @pytest.mark.asyncio
    async def test_tool_executor_validates_async_handlers(self):
        """Test that tool executor validates handlers are async."""
        # Create mock client with a non-async handler (should not happen in practice)
        client = AsyncMock(spec=MCPBigQueryClient)
        
        # Create registry
        registry = ToolRegistry(client)
        
        # Manually create a tool with a non-async handler for testing
        from src.mcp_bigquery.agent.tools import Tool
        
        # Replace the handler with a non-async function
        for tool in registry.tools:
            if tool.name == "list_datasets":
                # Store original
                original_handler = tool.handler
                # Replace with sync function
                tool.handler = lambda: "sync_result"
                break
        
        executor = ToolExecutor(registry)
        
        # Create tool call
        tool_call = ToolCall(
            id="call_123",
            name="list_datasets",
            arguments={}
        )
        
        # Execute - should detect non-async handler and return error
        result = await executor.execute_single_tool(tool_call)
        
        assert result["success"] is False
        assert "not async" in result["error"]
