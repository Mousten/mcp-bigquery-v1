"""Pydantic models for the agent orchestrator."""

from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field, field_validator


class ChartSuggestion(BaseModel):
    """Suggested chart/visualization for query results."""
    chart_type: str
    title: str
    x_column: Optional[str] = None
    y_columns: List[str] = Field(default_factory=list)
    description: str
    config: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('chart_type')
    @classmethod
    def validate_chart_type(cls, v: str) -> str:
        """Validate chart type is one of the supported types."""
        allowed_types = {
            "bar", "line", "pie", "scatter", "area", "table",
            "metric", "map", "heatmap", "histogram"
        }
        if v.lower() not in allowed_types:
            raise ValueError(f"Chart type must be one of {allowed_types}, got: {v}")
        return v.lower()


class SQLGenerationResult(BaseModel):
    """Result of SQL generation from LLM."""
    sql: str
    explanation: str
    tables_used: List[str] = Field(default_factory=list)
    estimated_complexity: str = Field(default="medium")
    warnings: List[str] = Field(default_factory=list)
    
    @field_validator('estimated_complexity')
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        """Validate complexity is one of the allowed values."""
        allowed = {"low", "medium", "high"}
        if v.lower() not in allowed:
            raise ValueError(f"Complexity must be one of {allowed}, got: {v}")
        return v.lower()


class ConversationContext(BaseModel):
    """Conversation context including history and user info."""
    session_id: str
    user_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    allowed_datasets: Set[str] = Field(default_factory=set)
    allowed_tables: Dict[str, Set[str]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('session_id', 'user_id')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate IDs are not empty."""
        if not v or not v.strip():
            raise ValueError("ID cannot be empty")
        return v.strip()


class AgentRequest(BaseModel):
    """Request to the insights agent."""
    question: str
    session_id: str
    user_id: str
    allowed_datasets: Set[str] = Field(default_factory=set)
    allowed_tables: Dict[str, Set[str]] = Field(default_factory=dict)
    context_turns: int = Field(default=5, ge=0, le=20)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate question is not empty."""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()


class AgentResponse(BaseModel):
    """Response from the insights agent."""
    success: bool
    answer: Optional[str] = None
    sql_query: Optional[str] = None
    sql_explanation: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    chart_suggestions: List[ChartSuggestion] = Field(default_factory=list)
    error: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    @field_validator('error_type')
    @classmethod
    def validate_error_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate error type if provided."""
        if v is None:
            return v
        allowed = {
            "authentication", "authorization", "validation",
            "execution", "llm", "network", "rate_limit", "unknown"
        }
        if v.lower() not in allowed:
            raise ValueError(f"Error type must be one of {allowed}, got: {v}")
        return v.lower()
