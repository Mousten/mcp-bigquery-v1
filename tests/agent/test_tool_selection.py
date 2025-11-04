"""Tests for LLM-based tool selection functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
import json

from src.mcp_bigquery.agent.tools import Tool, ToolRegistry
from src.mcp_bigquery.agent.tool_executor import ToolExecutor
from src.mcp_bigquery.agent.conversation import InsightsAgent
from src.mcp_bigquery.agent.models import AgentRequest
from src.mcp_bigquery.agent.mcp_client import DatasetInfo, TableInfo, TableSchema
from src.mcp_bigquery.llm.providers.base import (
    Message,
    GenerationResponse,
    ToolCall,
    ToolDefinition,
)


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = AsyncMock()
    
    # Mock list_datasets
    client.list_datasets = AsyncMock(return_value=[
        DatasetInfo(dataset_id="Analytics", project_id="test-project"),
        DatasetInfo(dataset_id="Sales", project_id="test-project"),
    ])
    
    # Mock list_tables
    client.list_tables = AsyncMock(return_value=[
        TableInfo(table_id="users", dataset_id="Analytics"),
        TableInfo(table_id="events", dataset_id="Analytics"),
    ])
    
    # Mock get_table_schema
    client.get_table_schema = AsyncMock(return_value=TableSchema(
        table_id="users",
        dataset_id="Analytics",
        schema_fields=[
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "STRING"},
        ]
    ))
    
    # Mock execute_sql - return a proper QueryResult-like object
    from src.mcp_bigquery.agent.mcp_client import QueryResult
    client.execute_sql = AsyncMock(return_value=QueryResult(
        rows=[{"id": 1, "name": "Alice"}],
        statistics={"totalBytesProcessed": 1000}
    ))
    
    return client


@pytest.fixture
def tool_registry(mock_mcp_client):
    """Create a tool registry."""
    return ToolRegistry(mock_mcp_client)


@pytest.fixture
def tool_executor(tool_registry):
    """Create a tool executor."""
    return ToolExecutor(tool_registry)


class TestToolRegistry:
    """Tests for ToolRegistry."""
    
    def test_registry_initialization(self, tool_registry):
        """Test that registry initializes with correct tools."""
        tools = tool_registry.get_all_tools()
        assert len(tools) == 4
        
        tool_names = [t.name for t in tools]
        assert "list_datasets" in tool_names
        assert "list_tables" in tool_names
        assert "get_table_schema" in tool_names
        assert "execute_sql" in tool_names
    
    def test_get_tool_by_name(self, tool_registry):
        """Test getting tool by name."""
        tool = tool_registry.get_tool_by_name("list_datasets")
        assert tool is not None
        assert tool.name == "list_datasets"
        assert tool.description is not None
        
    def test_get_tool_by_name_not_found(self, tool_registry):
        """Test getting non-existent tool."""
        tool = tool_registry.get_tool_by_name("nonexistent")
        assert tool is None
    
    def test_get_tools_for_openai(self, tool_registry):
        """Test formatting tools for OpenAI."""
        tools = tool_registry.get_tools_for_llm("openai")
        assert len(tools) == 4
        assert all(isinstance(t, ToolDefinition) for t in tools)
        
        # Check first tool structure
        tool = tools[0]
        assert tool.name == "list_datasets"
        assert tool.description is not None
        assert "type" in tool.parameters
        assert tool.parameters["type"] == "object"
    
    def test_get_tools_for_anthropic(self, tool_registry):
        """Test formatting tools for Anthropic."""
        tools = tool_registry.get_tools_for_llm("anthropic")
        assert len(tools) == 4
        assert all(isinstance(t, ToolDefinition) for t in tools)
    
    def test_unsupported_provider(self, tool_registry):
        """Test that unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            tool_registry.get_tools_for_llm("unsupported")


class TestToolExecutor:
    """Tests for ToolExecutor."""
    
    @pytest.mark.asyncio
    async def test_execute_list_datasets(self, tool_executor, mock_mcp_client):
        """Test executing list_datasets tool."""
        tool_call = ToolCall(
            id="call_123",
            name="list_datasets",
            arguments={}
        )
        
        result = await tool_executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert result["tool_name"] == "list_datasets"
        assert result["tool_call_id"] == "call_123"
        assert len(result["result"]) == 2
        mock_mcp_client.list_datasets.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_list_tables(self, tool_executor, mock_mcp_client):
        """Test executing list_tables tool."""
        tool_call = ToolCall(
            id="call_456",
            name="list_tables",
            arguments={"dataset_id": "Analytics"}
        )
        
        result = await tool_executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert result["tool_name"] == "list_tables"
        assert len(result["result"]) == 2
        mock_mcp_client.list_tables.assert_called_once_with(dataset_id="Analytics")
    
    @pytest.mark.asyncio
    async def test_execute_get_table_schema(self, tool_executor, mock_mcp_client):
        """Test executing get_table_schema tool."""
        tool_call = ToolCall(
            id="call_789",
            name="get_table_schema",
            arguments={
                "dataset_id": "Analytics",
                "table_id": "users"
            }
        )
        
        result = await tool_executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert result["tool_name"] == "get_table_schema"
        mock_mcp_client.get_table_schema.assert_called_once_with(
            dataset_id="Analytics",
            table_id="users"
        )
    
    @pytest.mark.asyncio
    async def test_execute_sql(self, tool_executor, mock_mcp_client):
        """Test executing execute_sql tool."""
        tool_call = ToolCall(
            id="call_999",
            name="execute_sql",
            arguments={"sql": "SELECT * FROM users LIMIT 10"}
        )
        
        result = await tool_executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert result["tool_name"] == "execute_sql"
        mock_mcp_client.execute_sql.assert_called_once_with(
            sql="SELECT * FROM users LIMIT 10"
        )
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, tool_executor):
        """Test executing unknown tool returns error."""
        tool_call = ToolCall(
            id="call_unknown",
            name="unknown_tool",
            arguments={}
        )
        
        result = await tool_executor.execute_single_tool(tool_call)
        
        assert result["success"] is False
        assert "Unknown tool" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_multiple_tools(self, tool_executor, mock_mcp_client):
        """Test executing multiple tool calls."""
        tool_calls = [
            ToolCall(id="call_1", name="list_datasets", arguments={}),
            ToolCall(id="call_2", name="list_tables", arguments={"dataset_id": "Analytics"}),
        ]
        
        results = await tool_executor.execute_tool_calls(tool_calls)
        
        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert results[0]["tool_name"] == "list_datasets"
        assert results[1]["tool_name"] == "list_tables"


class TestInsightsAgentWithToolSelection:
    """Tests for InsightsAgent with tool selection."""
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = Mock()
        provider.provider_name = "openai"
        provider.config = Mock(model="gpt-4o")
        provider.supports_functions = Mock(return_value=True)
        return provider
    
    @pytest.fixture
    def mock_kb(self):
        """Create a mock knowledge base."""
        kb = AsyncMock()
        kb.get_chat_messages = AsyncMock(return_value=[])
        kb.append_chat_message = AsyncMock()
        return kb
    
    @pytest.fixture
    def agent(self, mock_llm_provider, mock_mcp_client, mock_kb):
        """Create an InsightsAgent with tool selection enabled."""
        agent = InsightsAgent(
            llm_provider=mock_llm_provider,
            mcp_client=mock_mcp_client,
            kb=mock_kb,
            project_id="test-project",
            enable_tool_selection=True
        )
        return agent
    
    def test_agent_initialization_with_tool_selection(self, agent):
        """Test that agent initializes with tool selection."""
        assert agent.enable_tool_selection is True
        assert agent.tool_registry is not None
        assert agent.tool_executor is not None
    
    @pytest.mark.asyncio
    async def test_list_datasets_question(self, agent, mock_llm_provider, mock_mcp_client):
        """Test that 'what datasets' questions call list_datasets tool."""
        # Mock LLM to return tool call
        mock_llm_provider.generate = AsyncMock(return_value=GenerationResponse(
            content=None,
            tool_calls=[
                ToolCall(id="call_1", name="list_datasets", arguments={})
            ],
            finish_reason="tool_calls"
        ))
        
        # Second call returns final answer
        mock_llm_provider.generate.side_effect = [
            GenerationResponse(
                content=None,
                tool_calls=[ToolCall(id="call_1", name="list_datasets", arguments={})],
                finish_reason="tool_calls"
            ),
            GenerationResponse(
                content="You have access to 2 datasets: Analytics and Sales.",
                tool_calls=[],
                finish_reason="stop"
            )
        ]
        
        request = AgentRequest(
            question="what datasets do I have?",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"*"},
            allowed_tables={}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        assert "datasets" in response.answer.lower() or "Analytics" in response.answer
        mock_mcp_client.list_datasets.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_tables_question(self, agent, mock_llm_provider, mock_mcp_client):
        """Test that 'show tables' questions call list_tables tool."""
        mock_llm_provider.generate = AsyncMock()
        mock_llm_provider.generate.side_effect = [
            GenerationResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="list_tables", arguments={"dataset_id": "Analytics"})
                ],
                finish_reason="tool_calls"
            ),
            GenerationResponse(
                content="The Analytics dataset contains 2 tables: users and events.",
                tool_calls=[],
                finish_reason="stop"
            )
        ]
        
        request = AgentRequest(
            question="show tables in Analytics",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"Analytics"},
            allowed_tables={"Analytics": {"*"}}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        mock_mcp_client.list_tables.assert_called_once_with(dataset_id="Analytics")
    
    @pytest.mark.asyncio
    async def test_get_schema_question(self, agent, mock_llm_provider, mock_mcp_client):
        """Test that 'describe table' questions call get_table_schema tool."""
        mock_llm_provider.generate = AsyncMock()
        mock_llm_provider.generate.side_effect = [
            GenerationResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="get_table_schema",
                        arguments={"dataset_id": "Analytics", "table_id": "users"}
                    )
                ],
                finish_reason="tool_calls"
            ),
            GenerationResponse(
                content="The users table has 2 columns: id (INTEGER) and name (STRING).",
                tool_calls=[],
                finish_reason="stop"
            )
        ]
        
        request = AgentRequest(
            question="describe the users table",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"Analytics"},
            allowed_tables={"Analytics": {"users"}}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        mock_mcp_client.get_table_schema.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_sql_question(self, agent, mock_llm_provider, mock_mcp_client):
        """Test that data questions call execute_sql tool."""
        mock_llm_provider.generate = AsyncMock()
        mock_llm_provider.generate.side_effect = [
            GenerationResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="execute_sql",
                        arguments={"sql": "SELECT * FROM Analytics.users LIMIT 10"}
                    )
                ],
                finish_reason="tool_calls"
            ),
            GenerationResponse(
                content="Here are the results: Found 1 user named Alice.",
                tool_calls=[],
                finish_reason="stop"
            )
        ]
        
        request = AgentRequest(
            question="show me data from users table",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"Analytics"},
            allowed_tables={"Analytics": {"users"}}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        mock_mcp_client.execute_sql.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_tool_calls(self, agent, mock_llm_provider):
        """Test LLM providing direct answer without tool calls."""
        mock_llm_provider.generate = AsyncMock(return_value=GenerationResponse(
            content="I can help you explore your BigQuery data. What would you like to know?",
            tool_calls=[],
            finish_reason="stop"
        ))
        
        request = AgentRequest(
            question="hello",
            session_id="test_session",
            user_id="test_user",
            allowed_datasets={"*"},
            allowed_tables={}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        assert "help" in response.answer.lower() or "explore" in response.answer.lower()


class TestToolSelectionIntegration:
    """Integration tests for tool selection."""
    
    @pytest.mark.asyncio
    async def test_tool_selection_with_openai_format(self, mock_mcp_client):
        """Test tool selection works with OpenAI format."""
        registry = ToolRegistry(mock_mcp_client)
        executor = ToolExecutor(registry)
        
        # Simulate OpenAI tool call
        tool_call = ToolCall(
            id="call_abc123",
            name="list_datasets",
            arguments={}
        )
        
        result = await executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert len(result["result"]) == 2
    
    @pytest.mark.asyncio
    async def test_tool_selection_with_anthropic_format(self, mock_mcp_client):
        """Test tool selection works with Anthropic format."""
        registry = ToolRegistry(mock_mcp_client)
        executor = ToolExecutor(registry)
        
        # Simulate Anthropic tool call (same structure as OpenAI in our implementation)
        tool_call = ToolCall(
            id="toolu_abc123",
            name="list_tables",
            arguments={"dataset_id": "Analytics"}
        )
        
        result = await executor.execute_single_tool(tool_call)
        
        assert result["success"] is True
        assert len(result["result"]) == 2
