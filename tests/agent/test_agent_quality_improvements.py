"""Tests for agent quality improvements (Issue 1-4)."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from mcp_bigquery.agent.conversation import InsightsAgent
from mcp_bigquery.agent.models import AgentRequest, AgentResponse
from mcp_bigquery.llm.providers import Message, GenerationResponse


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
class TestTableListingImprovements:
    """Test Issue 1: Tables Listing Fails."""
    
    async def test_list_tables_with_case_insensitive_dataset(
        self, agent, mock_mcp_client
    ):
        """Test that dataset extraction is case-insensitive."""
        mock_mcp_client.list_tables.return_value = {
            "tables": [
                {"tableId": "Table1"},
                {"tableId": "Table2"}
            ]
        }
        
        request = AgentRequest(
            question="show me tables in the ANALYTICS dataset",  # Uppercase
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"analytics"}  # Lowercase
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        assert "analytics" in response.answer.lower()
        assert "Table1" in response.answer
        assert "Table2" in response.answer
        mock_mcp_client.list_tables.assert_called_once_with("analytics")
    
    async def test_list_tables_with_pattern_extraction(
        self, agent, mock_mcp_client
    ):
        """Test extracting dataset from 'in the <dataset> dataset' pattern."""
        mock_mcp_client.list_tables.return_value = {
            "tables": [{"tableId": "Sales_Table"}]
        }
        
        request = AgentRequest(
            question="what tables are in the Analytics dataset?",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"Analytics"}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        assert "Sales_Table" in response.answer
    
    async def test_list_tables_multiple_datasets_asks_clarification(
        self, agent, mock_mcp_client
    ):
        """Test that agent asks for clarification when multiple datasets available."""
        request = AgentRequest(
            question="show me the tables",  # No dataset specified
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"Dataset1", "Dataset2", "Dataset3"}
        )
        
        response = await agent.process_question(request)
        
        # Should ask for clarification
        assert response.success is False
        assert response.error_type == "validation"
        assert "Dataset1" in response.error or "specify" in response.error.lower()
    
    async def test_list_tables_single_dataset_auto_select(
        self, agent, mock_mcp_client
    ):
        """Test auto-selection when user has only one dataset."""
        mock_mcp_client.list_tables.return_value = {
            "tables": [{"tableId": "OnlyTable"}]
        }
        
        request = AgentRequest(
            question="show me the tables",  # No dataset specified
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"OnlyDataset"}  # Only one
        )
        
        response = await agent.process_question(request)
        
        assert response.success is True
        assert "OnlyTable" in response.answer
        mock_mcp_client.list_tables.assert_called_once_with("OnlyDataset")
    
    async def test_list_tables_error_shows_helpful_message(
        self, agent, mock_mcp_client
    ):
        """Test that errors provide helpful context."""
        mock_mcp_client.list_tables.side_effect = Exception("Access denied")
        
        request = AgentRequest(
            question="show tables in Analytics",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"Analytics"}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is False
        assert "encountered an error" in response.error.lower()
        assert "Access denied" in response.error or "access denied" in response.error.lower()
        # Should provide next steps
        assert "try:" in response.error.lower() or "you can" in response.error.lower()


@pytest.mark.asyncio
class TestSQLGenerationAccuracy:
    """Test Issue 2: Wrong SQL Generation."""
    
    async def test_extract_table_references_from_question(self, agent):
        """Test table reference extraction."""
        # Test with dataset.table format
        refs = agent._extract_table_references_from_question(
            "show me data from Analytics.Daily_Sales"
        )
        assert len(refs) > 0
        # Should find Daily_Sales
        assert any(table_id == "Daily_Sales" for _, table_id in refs)
    
    async def test_validate_sql_tables_with_invalid_dataset(self, agent):
        """Test SQL validation catches invalid dataset references."""
        sql = "SELECT * FROM `unauthorized_dataset.some_table`"
        
        result = await agent._validate_sql_tables(
            sql=sql,
            allowed_datasets={"allowed_dataset"},
            allowed_tables={"allowed_dataset": {"table1"}}
        )
        
        assert result["valid"] is False
        assert "unauthorized_dataset" in result["error"]
    
    async def test_validate_sql_tables_with_valid_access(self, agent):
        """Test SQL validation passes for valid table references."""
        sql = "SELECT * FROM `allowed_dataset.table1`"
        
        result = await agent._validate_sql_tables(
            sql=sql,
            allowed_datasets={"allowed_dataset"},
            allowed_tables={"allowed_dataset": {"table1", "table2"}}
        )
        
        assert result["valid"] is True


@pytest.mark.asyncio
class TestEmptyResultHandling:
    """Test Issue 3: Misleading Empty Results."""
    
    async def test_empty_results_provide_clear_explanation(
        self, agent, mock_llm_provider, mock_mcp_client
    ):
        """Test that empty results are explained clearly."""
        # Setup SQL generation
        mock_llm_provider.generate.side_effect = [
            GenerationResponse(
                content=json.dumps({
                    "sql": "SELECT * FROM table WHERE false",
                    "explanation": "Test query",
                    "tables_used": ["table"],
                    "estimated_complexity": "low",
                    "warnings": []
                }),
                finish_reason="stop"
            )
        ]
        
        # Return empty results
        mock_mcp_client.execute_sql.return_value = {
            "rows": [],  # Empty!
            "schema": [{"name": "id", "type": "INTEGER"}]
        }
        
        request = AgentRequest(
            question="Show me data",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"dataset1"}
        )
        
        response = await agent.process_question(request)
        
        # Should succeed but explain 0 rows
        assert response.success is True
        assert "0 rows" in response.answer or "no data" in response.answer.lower()
        # Should distinguish from error
        assert "succeeded" in response.answer.lower() or "executed" in response.answer.lower()
        # Should provide reasons
        assert "reason" in response.answer.lower() or "might" in response.answer.lower()


@pytest.mark.asyncio
class TestErrorHandling:
    """Test Issue 4: Poor Error Handling."""
    
    async def test_error_messages_include_details(
        self, agent, mock_mcp_client
    ):
        """Test that error messages are detailed and helpful."""
        mock_mcp_client.list_tables.side_effect = Exception(
            "404: Dataset not found"
        )
        
        request = AgentRequest(
            question="show tables in NonExistent",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"NonExistent"}
        )
        
        response = await agent.process_question(request)
        
        assert response.success is False
        # Should include the actual error
        assert "404" in response.error or "not found" in response.error.lower()
        # Should provide suggestions
        assert "try" in response.error.lower() or "can" in response.error.lower()
    
    async def test_metadata_questions_dont_generate_sql(
        self, agent, mock_llm_provider, mock_mcp_client
    ):
        """Test that metadata questions don't invoke SQL generation."""
        mock_mcp_client.list_datasets.return_value = {
            "datasets": [{"datasetId": "TestDataset"}]
        }
        
        request = AgentRequest(
            question="what datasets do I have access to?",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"*"}
        )
        
        response = await agent.process_question(request)
        
        # Should succeed
        assert response.success is True
        assert "TestDataset" in response.answer
        
        # LLM should NOT have been called for SQL generation
        # (It's a direct metadata call)
        assert mock_llm_provider.generate.call_count == 0


@pytest.mark.asyncio
class TestPromptImprovements:
    """Test that prompts guide LLM correctly."""
    
    async def test_system_prompt_emphasizes_exact_table_names(self, agent):
        """Test that system prompt has strong guidance on table names."""
        from mcp_bigquery.agent.prompts import PromptBuilder
        
        prompt = PromptBuilder.build_system_prompt(
            allowed_datasets={"Analytics"},
            allowed_tables={"Analytics": {"Daily_Sales", "Monthly_Sales"}},
            project_id="test-project"
        )
        
        # Should have strong guidance
        assert "EXACT" in prompt or "exact" in prompt
        assert "NEVER" in prompt or "never" in prompt.lower()
        # Should mention not transforming names
        assert "transform" in prompt.lower() or "modify" in prompt.lower()
        # Should list the actual tables
        assert "Daily_Sales" in prompt
        assert "Monthly_Sales" in prompt
