"""Tests for agent models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from mcp_bigquery.agent.models import (
    ChartSuggestion,
    SQLGenerationResult,
    ConversationContext,
    AgentRequest,
    AgentResponse,
)


class TestChartSuggestion:
    """Tests for ChartSuggestion model."""
    
    def test_valid_chart_suggestion(self):
        """Test creating a valid chart suggestion."""
        chart = ChartSuggestion(
            chart_type="bar",
            title="Sales by Region",
            x_column="region",
            y_columns=["total_sales"],
            description="Bar chart showing sales by region",
            config={"orientation": "vertical"}
        )
        
        assert chart.chart_type == "bar"
        assert chart.title == "Sales by Region"
        assert chart.x_column == "region"
        assert chart.y_columns == ["total_sales"]
        assert chart.config["orientation"] == "vertical"
    
    def test_invalid_chart_type(self):
        """Test that invalid chart types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChartSuggestion(
                chart_type="invalid_type",
                title="Test",
                description="Test chart"
            )
        
        assert "Chart type must be one of" in str(exc_info.value)
    
    def test_chart_type_case_insensitive(self):
        """Test that chart types are normalized to lowercase."""
        chart = ChartSuggestion(
            chart_type="BAR",
            title="Test",
            description="Test chart"
        )
        
        assert chart.chart_type == "bar"


class TestSQLGenerationResult:
    """Tests for SQLGenerationResult model."""
    
    def test_valid_sql_result(self):
        """Test creating a valid SQL generation result."""
        result = SQLGenerationResult(
            sql="SELECT * FROM table",
            explanation="Simple select query",
            tables_used=["project.dataset.table"],
            estimated_complexity="low",
            warnings=[]
        )
        
        assert result.sql == "SELECT * FROM table"
        assert result.explanation == "Simple select query"
        assert result.estimated_complexity == "low"
        assert len(result.warnings) == 0
    
    def test_invalid_complexity(self):
        """Test that invalid complexity values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SQLGenerationResult(
                sql="SELECT 1",
                explanation="Test",
                estimated_complexity="invalid"
            )
        
        assert "Complexity must be one of" in str(exc_info.value)
    
    def test_defaults(self):
        """Test default values."""
        result = SQLGenerationResult(
            sql="SELECT 1",
            explanation="Test"
        )
        
        assert result.estimated_complexity == "medium"
        assert result.tables_used == []
        assert result.warnings == []


class TestConversationContext:
    """Tests for ConversationContext model."""
    
    def test_valid_context(self):
        """Test creating a valid conversation context."""
        context = ConversationContext(
            session_id="session-123",
            user_id="user-456",
            messages=[{"role": "user", "content": "Hello"}],
            allowed_datasets={"dataset1", "dataset2"},
            allowed_tables={"dataset1": {"table1", "table2"}},
            metadata={"key": "value"}
        )
        
        assert context.session_id == "session-123"
        assert context.user_id == "user-456"
        assert len(context.messages) == 1
        assert "dataset1" in context.allowed_datasets
    
    def test_empty_session_id(self):
        """Test that empty session IDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationContext(
                session_id="",
                user_id="user-123"
            )
        
        assert "ID cannot be empty" in str(exc_info.value)
    
    def test_defaults(self):
        """Test default values."""
        context = ConversationContext(
            session_id="session-123",
            user_id="user-456"
        )
        
        assert context.messages == []
        assert context.allowed_datasets == set()
        assert context.allowed_tables == {}
        assert context.metadata == {}


class TestAgentRequest:
    """Tests for AgentRequest model."""
    
    def test_valid_request(self):
        """Test creating a valid agent request."""
        request = AgentRequest(
            question="What are the top sales?",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"sales"},
            allowed_tables={"sales": {"orders"}},
            context_turns=10,
            metadata={"source": "web"}
        )
        
        assert request.question == "What are the top sales?"
        assert request.session_id == "session-123"
        assert request.context_turns == 10
    
    def test_empty_question(self):
        """Test that empty questions are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentRequest(
                question="",
                session_id="session-123",
                user_id="user-456"
            )
        
        assert "Question cannot be empty" in str(exc_info.value)
    
    def test_context_turns_validation(self):
        """Test that context_turns is validated."""
        # Too high
        with pytest.raises(ValidationError):
            AgentRequest(
                question="Test",
                session_id="session-123",
                user_id="user-456",
                context_turns=100
            )
        
        # Negative
        with pytest.raises(ValidationError):
            AgentRequest(
                question="Test",
                session_id="session-123",
                user_id="user-456",
                context_turns=-1
            )
    
    def test_defaults(self):
        """Test default values."""
        request = AgentRequest(
            question="Test",
            session_id="session-123",
            user_id="user-456"
        )
        
        assert request.context_turns == 5
        assert request.allowed_datasets == set()
        assert request.metadata == {}


class TestAgentResponse:
    """Tests for AgentResponse model."""
    
    def test_success_response(self):
        """Test creating a successful response."""
        response = AgentResponse(
            success=True,
            answer="Here are the results",
            sql_query="SELECT * FROM table",
            sql_explanation="Simple query",
            results={"rows": [{"col": "value"}]},
            chart_suggestions=[
                ChartSuggestion(
                    chart_type="bar",
                    title="Test",
                    description="Test chart"
                )
            ],
            metadata={"key": "value"}
        )
        
        assert response.success is True
        assert response.answer == "Here are the results"
        assert response.sql_query == "SELECT * FROM table"
        assert len(response.chart_suggestions) == 1
        assert response.error is None
    
    def test_error_response(self):
        """Test creating an error response."""
        response = AgentResponse(
            success=False,
            error="Query failed",
            error_type="execution"
        )
        
        assert response.success is False
        assert response.error == "Query failed"
        assert response.error_type == "execution"
        assert response.answer is None
    
    def test_invalid_error_type(self):
        """Test that invalid error types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentResponse(
                success=False,
                error="Test error",
                error_type="invalid_type"
            )
        
        assert "Error type must be one of" in str(exc_info.value)
    
    def test_timestamp_default(self):
        """Test that timestamp is set by default."""
        response = AgentResponse(success=True)
        
        assert response.timestamp is not None
        assert isinstance(response.timestamp, datetime)
    
    def test_defaults(self):
        """Test default values."""
        response = AgentResponse(success=True)
        
        assert response.answer is None
        assert response.sql_query is None
        assert response.chart_suggestions == []
        assert response.error is None
        assert response.metadata == {}
