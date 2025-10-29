"""Agent module for conversational BigQuery insights."""

from .conversation import InsightsAgent
from .conversation_manager import ConversationManager, RateLimitExceeded
from .prompts import PromptBuilder
from .models import (
    AgentRequest,
    AgentResponse,
    SQLGenerationResult,
    ChartSuggestion,
    ConversationContext,
)
from .mcp_client import (
    MCPBigQueryClient,
    QueryResult,
    DatasetInfo,
    TableInfo,
    TableSchema,
    HealthStatus,
)
from .summarizer import (
    ResultSummarizer,
    DataSummary,
    ColumnStatistics,
)

__all__ = [
    "InsightsAgent",
    "ConversationManager",
    "RateLimitExceeded",
    "PromptBuilder",
    "AgentRequest",
    "AgentResponse",
    "SQLGenerationResult",
    "ChartSuggestion",
    "ConversationContext",
    "MCPBigQueryClient",
    "QueryResult",
    "DatasetInfo",
    "TableInfo",
    "TableSchema",
    "HealthStatus",
    "ResultSummarizer",
    "DataSummary",
    "ColumnStatistics",
]
