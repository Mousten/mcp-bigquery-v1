"""Tests for the conversation agent."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from mcp_bigquery.agent.conversation import InsightsAgent
from mcp_bigquery.agent.models import (
    AgentRequest,
    AgentResponse,
    SQLGenerationResult,
    ChartSuggestion,
)
from mcp_bigquery.llm.providers import (
    Message,
    GenerationResponse,
    LLMGenerationError,
)
from mcp_bigquery.client.exceptions import AuthorizationError


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.provider_name = "openai"
    provider.config.model = "gpt-4"
    provider.generate = AsyncMock()
    provider.count_tokens = MagicMock(return_value=100)
    provider.supports_functions = MagicMock(return_value=False)  # Disable tool selection for these tests
    return provider


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = MagicMock()
    client.execute_sql = AsyncMock()
    client.list_datasets = AsyncMock()
    client.list_tables = AsyncMock()
    client.get_table_schema = AsyncMock()
    return client


@pytest.fixture
def mock_kb():
    """Create a mock knowledge base."""
    kb = MagicMock()
    kb.get_chat_messages = AsyncMock(return_value=[])
    kb.append_chat_message = AsyncMock()
    kb.get_cached_llm_response = AsyncMock(return_value=None)
    kb.cache_llm_response = AsyncMock()
    return kb


@pytest.fixture
def agent(mock_llm_provider, mock_mcp_client, mock_kb):
    """Create an insights agent with mocks."""
    return InsightsAgent(
        llm_provider=mock_llm_provider,
        mcp_client=mock_mcp_client,
        kb=mock_kb,
        project_id="test-project",
        enable_caching=False
    )


@pytest.mark.asyncio
class TestInsightsAgent:
    """Tests for InsightsAgent."""
    
    async def test_process_question_success(
        self, agent, mock_llm_provider, mock_mcp_client, mock_kb
    ):
        """Test successful question processing."""
        # Setup mocks
        mock_llm_provider.generate.side_effect = [
            # SQL generation
            GenerationResponse(
                content=json.dumps({
                    "sql": "SELECT * FROM table LIMIT 10",
                    "explanation": "Get first 10 rows",
                    "tables_used": ["table"],
                    "estimated_complexity": "low",
                    "warnings": []
                }),
                finish_reason="stop",
                usage={"total_tokens": 100}
            ),
            # Summary generation
            GenerationResponse(
                content="Here are the top 10 results from the table.",
                finish_reason="stop",
                usage={"total_tokens": 50}
            ),
            # Chart suggestions
            GenerationResponse(
                content=json.dumps([
                    {
                        "chart_type": "table",
                        "title": "Data Table",
                        "description": "Display data in table format",
                        "config": {}
                    }
                ]),
                finish_reason="stop",
                usage={"total_tokens": 75}
            )
        ]
        
        mock_mcp_client.execute_sql.return_value = {
            "rows": [
                {"id": 1, "name": "Test1"},
                {"id": 2, "name": "Test2"},
                {"id": 3, "name": "Test3"}
            ],
            "schema": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "STRING"}
            ]
        }
        
        # Create request
        request = AgentRequest(
            question="Show me data from the table",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"dataset1"},
            allowed_tables={"dataset1": {"table"}}
        )
        
        # Process question
        response = await agent.process_question(request)
        
        # Verify response
        assert response.success is True
        assert response.answer is not None
        assert response.sql_query == "SELECT * FROM table LIMIT 10"
        assert response.sql_explanation == "Get first 10 rows"
        assert response.results is not None
        assert len(response.chart_suggestions) == 1
        
        # Verify mocks called
        assert mock_llm_provider.generate.call_count == 3
        mock_mcp_client.execute_sql.assert_called_once()
        assert mock_kb.append_chat_message.call_count == 2  # user + assistant
    
    async def test_process_question_authorization_error(
        self, agent, mock_llm_provider, mock_mcp_client, mock_kb
    ):
        """Test handling of authorization errors."""
        # Setup mocks
        mock_llm_provider.generate.return_value = GenerationResponse(
            content=json.dumps({
                "sql": "SELECT * FROM unauthorized_table",
                "explanation": "Query unauthorized table",
                "tables_used": ["unauthorized_table"],
                "estimated_complexity": "low",
                "warnings": []
            }),
            finish_reason="stop",
            usage={"total_tokens": 100}
        )
        
        mock_mcp_client.execute_sql.side_effect = AuthorizationError(
            "User lacks permission to access table"
        )
        
        # Create request
        request = AgentRequest(
            question="Show me unauthorized data",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"dataset1"}
        )
        
        # Process question
        response = await agent.process_question(request)
        
        # Verify response
        assert response.success is False
        assert response.error_type == "authorization"
        assert "Permission denied" in response.error
        assert response.sql_query is not None
        
        # Verify error message saved
        mock_kb.append_chat_message.assert_called()
    
    async def test_process_question_execution_error(
        self, agent, mock_llm_provider, mock_mcp_client, mock_kb
    ):
        """Test handling of query execution errors."""
        # Setup mocks
        mock_llm_provider.generate.return_value = GenerationResponse(
            content=json.dumps({
                "sql": "SELECT * FROM invalid_syntax",
                "explanation": "Invalid query",
                "tables_used": [],
                "estimated_complexity": "low",
                "warnings": []
            }),
            finish_reason="stop",
            usage={"total_tokens": 100}
        )
        
        mock_mcp_client.execute_sql.side_effect = Exception("Syntax error")
        
        # Create request
        request = AgentRequest(
            question="Run invalid query",
            session_id="session-123",
            user_id="user-456"
        )
        
        # Process question
        response = await agent.process_question(request)
        
        # Verify response
        assert response.success is False
        assert response.error_type == "execution"
        assert "Query execution failed" in response.error
    
    async def test_process_question_llm_error(
        self, agent, mock_llm_provider, mock_mcp_client, mock_kb
    ):
        """Test handling of LLM generation errors."""
        # Setup mocks
        mock_llm_provider.generate.side_effect = LLMGenerationError(
            "API rate limit exceeded"
        )
        
        # Create request
        request = AgentRequest(
            question="Test question",
            session_id="session-123",
            user_id="user-456"
        )
        
        # Process question
        response = await agent.process_question(request)
        
        # Verify response - should handle gracefully
        assert response.success is False
        # Agent should save error message
        mock_kb.append_chat_message.assert_called()
    
    async def test_get_conversation_context(self, agent, mock_kb):
        """Test retrieving conversation context."""
        # Setup mock
        mock_kb.get_chat_messages.return_value = [
            {
                "role": "user",
                "content": "Previous question",
                "created_at": "2024-01-01"
            },
            {
                "role": "assistant",
                "content": "Previous answer",
                "created_at": "2024-01-01"
            }
        ]
        
        # Get context
        context = await agent._get_conversation_context(
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"dataset1"},
            allowed_tables={"dataset1": {"table1"}},
            context_turns=5
        )
        
        # Verify context
        assert context.session_id == "session-123"
        assert context.user_id == "user-456"
        assert len(context.messages) == 2
        assert "dataset1" in context.allowed_datasets
        
        # Verify mock called with correct limit
        mock_kb.get_chat_messages.assert_called_once()
        call_args = mock_kb.get_chat_messages.call_args
        assert call_args.kwargs["limit"] == 10  # 5 turns * 2 messages
    
    async def test_parse_sql_generation_valid_json(self, agent):
        """Test parsing valid JSON SQL generation response."""
        content = json.dumps({
            "sql": "SELECT * FROM table",
            "explanation": "Simple query",
            "tables_used": ["table"],
            "estimated_complexity": "low",
            "warnings": []
        })
        
        result = agent._parse_sql_generation(content)
        
        assert result.sql == "SELECT * FROM table"
        assert result.explanation == "Simple query"
        assert result.estimated_complexity == "low"
    
    async def test_parse_sql_generation_markdown_json(self, agent):
        """Test parsing JSON wrapped in markdown code blocks."""
        content = "```json\n" + json.dumps({
            "sql": "SELECT 1",
            "explanation": "Test"
        }) + "\n```"
        
        result = agent._parse_sql_generation(content)
        
        assert result.sql == "SELECT 1"
        assert result.explanation == "Test"
    
    async def test_parse_sql_generation_sql_code_block(self, agent):
        """Test fallback parsing of SQL code blocks."""
        content = "Here's the query:\n```sql\nSELECT * FROM table\n```\nThis queries the table."
        
        result = agent._parse_sql_generation(content)
        
        assert result.sql == "SELECT * FROM table"
        assert len(result.warnings) > 0
    
    async def test_parse_sql_generation_no_sql(self, agent):
        """Test parsing when no SQL is found."""
        content = "I'm not sure how to answer that question."
        
        result = agent._parse_sql_generation(content)
        
        assert result.sql == ""
        assert "more details" in result.explanation.lower()
    
    async def test_generate_fallback_suggestions(self, agent):
        """Test generating fallback chart suggestions."""
        # Time series data
        suggestions = agent._generate_fallback_suggestions(
            numeric_cols=["sales"],
            categorical_cols=[],
            datetime_cols=["date"]
        )
        
        assert len(suggestions) > 0
        assert any(s.chart_type == "line" for s in suggestions)
        assert any(s.chart_type == "table" for s in suggestions)
        
        # Categorical data
        suggestions = agent._generate_fallback_suggestions(
            numeric_cols=["amount"],
            categorical_cols=["category"],
            datetime_cols=[]
        )
        
        assert any(s.chart_type == "bar" for s in suggestions)
        
        # Single metric
        suggestions = agent._generate_fallback_suggestions(
            numeric_cols=["total"],
            categorical_cols=[],
            datetime_cols=[]
        )
        
        assert any(s.chart_type == "metric" for s in suggestions)
    
    async def test_parse_chart_suggestions_valid(self, agent):
        """Test parsing valid chart suggestions."""
        content = json.dumps([
            {
                "chart_type": "bar",
                "title": "Sales Chart",
                "x_column": "region",
                "y_columns": ["sales"],
                "description": "Bar chart of sales",
                "config": {}
            }
        ])
        
        suggestions = agent._parse_chart_suggestions(content)
        
        assert len(suggestions) == 1
        assert suggestions[0].chart_type == "bar"
        assert suggestions[0].title == "Sales Chart"
    
    async def test_parse_chart_suggestions_invalid(self, agent):
        """Test parsing invalid chart suggestions."""
        content = "Not valid JSON"
        
        suggestions = agent._parse_chart_suggestions(content)
        
        assert len(suggestions) == 0
    
    async def test_execute_query(self, agent, mock_mcp_client):
        """Test query execution."""
        mock_mcp_client.execute_sql.return_value = {
            "rows": [{"col": "value"}],
            "schema": []
        }
        
        result = await agent._execute_query("SELECT 1")
        
        assert "rows" in result
        mock_mcp_client.execute_sql.assert_called_once_with("SELECT 1")
    
    async def test_save_message(self, agent, mock_kb):
        """Test saving messages."""
        await agent._save_message(
            session_id="session-123",
            user_id="user-456",
            role="user",
            content="Test message",
            metadata={"key": "value"}
        )
        
        mock_kb.append_chat_message.assert_called_once()
        call_args = mock_kb.append_chat_message.call_args
        assert call_args.kwargs["session_id"] == "session-123"
        assert call_args.kwargs["role"] == "user"
        assert call_args.kwargs["content"] == "Test message"
    
    async def test_save_message_error_handling(self, agent, mock_kb):
        """Test that save_message errors don't crash the agent."""
        mock_kb.append_chat_message.side_effect = Exception("Database error")
        
        # Should not raise
        await agent._save_message(
            session_id="session-123",
            user_id="user-456",
            role="user",
            content="Test"
        )
    
    async def test_conversation_context_used(
        self, agent, mock_llm_provider, mock_mcp_client, mock_kb
    ):
        """Test that conversation context is passed to LLM."""
        # Setup mock with conversation history
        mock_kb.get_chat_messages.return_value = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"}
        ]
        
        mock_llm_provider.generate.side_effect = [
            GenerationResponse(
                content=json.dumps({
                    "sql": "SELECT * FROM table",
                    "explanation": "Query",
                    "tables_used": [],
                    "estimated_complexity": "low",
                    "warnings": []
                }),
                finish_reason="stop"
            ),
            GenerationResponse(content="Summary"),
            GenerationResponse(content="[]")
        ]
        
        mock_mcp_client.execute_sql.return_value = {
            "rows": [],
            "schema": []
        }
        
        request = AgentRequest(
            question="Follow-up question",
            session_id="session-123",
            user_id="user-456"
        )
        
        await agent.process_question(request)
        
        # Verify conversation history was retrieved
        mock_kb.get_chat_messages.assert_called_once()
        
        # Verify LLM was called with context
        assert mock_llm_provider.generate.call_count > 0
        first_call_messages = mock_llm_provider.generate.call_args_list[0][0][0]
        
        # Should have system and user messages
        assert len(first_call_messages) >= 2
