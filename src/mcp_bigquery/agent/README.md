# Agent Orchestrator

The agent module provides a conversational interface for BigQuery insights using Large Language Models (LLMs) to interpret natural language questions and generate SQL queries.

## Overview

The `InsightsAgent` class orchestrates the entire flow:

1. **Question Understanding**: Retrieves conversation context from chat history
2. **SQL Generation**: Uses LLMs to generate SQL queries constrained by user permissions
3. **Query Execution**: Executes queries through the MCP client
4. **Result Analysis**: Summarizes results in business-friendly language
5. **Visualization**: Suggests appropriate chart types for the data
6. **Persistence**: Stores conversation turns for context continuity

## Key Components

### InsightsAgent

The main orchestrator class that processes natural language questions and returns structured insights.

**Features:**
- Role-aware dataset access control
- Conversation context management
- LLM response caching
- Comprehensive error handling
- Retry logic for transient failures

### Models

Pydantic models for type-safe data handling:

- `AgentRequest`: Input request with question, user context, and permissions
- `AgentResponse`: Structured response with answer, SQL, results, and charts
- `SQLGenerationResult`: SQL query with metadata and warnings
- `ChartSuggestion`: Visualization recommendation with configuration
- `ConversationContext`: Session state with history and permissions

### PromptBuilder

Template-based prompt construction for consistent LLM interactions:

- System prompts with user permissions
- SQL generation prompts with schema context
- Result summarization prompts
- Chart suggestion prompts
- Clarification request prompts

## Usage

### Basic Example

```python
from mcp_bigquery.agent import InsightsAgent, AgentRequest
from mcp_bigquery.llm.factory import create_provider
from mcp_bigquery.client import MCPClient, ClientConfig
from mcp_bigquery.core.supabase_client import SupabaseKnowledgeBase

# Initialize dependencies
llm = create_provider("openai")
client = MCPClient(ClientConfig(base_url="http://localhost:8000"))
kb = SupabaseKnowledgeBase()

# Create agent
agent = InsightsAgent(
    llm_provider=llm,
    mcp_client=client,
    kb=kb,
    project_id="my-project"
)

# Process question
request = AgentRequest(
    question="What were the top 5 products by revenue last month?",
    session_id="session-123",
    user_id="user-456",
    allowed_datasets={"sales"},
    allowed_tables={"sales": {"orders", "products"}},
    context_turns=5  # Include last 5 conversation turns
)

response = await agent.process_question(request)

if response.success:
    print(response.answer)  # Natural language summary
    print(response.sql_query)  # Generated SQL
    print(response.results)  # Query results
    for chart in response.chart_suggestions:
        print(f"Chart: {chart.chart_type} - {chart.title}")
else:
    print(f"Error: {response.error}")
```

### With User Context

```python
from mcp_bigquery.core.auth import UserContext, hydrate_user_context

# Get user context from JWT
user_context = await hydrate_user_context(
    user_id="user-123",
    kb=kb
)

# Create request with user's permissions
request = AgentRequest(
    question="Show me my team's sales performance",
    session_id="session-123",
    user_id=user_context.user_id,
    allowed_datasets=user_context.allowed_datasets,
    allowed_tables=user_context.allowed_tables
)

response = await agent.process_question(request)
```

## Prompt Strategy

### System Prompt
Defines the agent's role, capabilities, and constraints:
- User's accessible datasets and tables
- BigQuery best practices
- Response format requirements
- Permission limitations

### SQL Generation
Includes:
- User's question
- Relevant table schemas
- Recent conversation history
- Expected JSON output format

### Result Summarization
Provides:
- Original question
- Executed SQL query
- Sample results
- Instructions for business-friendly language

### Chart Suggestions
Analyzes:
- Result schema (column types)
- Sample data
- Data statistics
- Appropriate visualization types

## Error Handling

The agent gracefully handles various error scenarios:

### Permission Errors
```python
# User asks about unauthorized data
response = await agent.process_question(request)
assert response.error_type == "authorization"
assert "Permission denied" in response.error
```

### Query Execution Errors
```python
# SQL syntax error or BigQuery failure
response = await agent.process_question(request)
assert response.error_type == "execution"
assert "Query execution failed" in response.error
```

### LLM Errors
```python
# LLM API failure
response = await agent.process_question(request)
# Agent returns graceful error message
assert response.success is False
```

### Validation Errors
```python
# Insufficient information to generate SQL
response = await agent.process_question(request)
assert response.error_type == "validation"
# Response includes clarification request
```

## Conversation Context

The agent maintains conversation history to handle follow-up questions:

```python
# First question
request1 = AgentRequest(
    question="Show me sales by region",
    session_id="session-123",
    user_id="user-456"
)
response1 = await agent.process_question(request1)

# Follow-up question (uses context)
request2 = AgentRequest(
    question="What about last quarter?",
    session_id="session-123",  # Same session
    user_id="user-456",
    context_turns=5  # Include previous exchange
)
response2 = await agent.process_question(request2)
# Agent understands "last quarter" applies to sales by region
```

## Chart Suggestions

The agent analyzes query results and suggests appropriate visualizations:

### Time Series Data
```python
# Results with datetime and numeric columns
# Suggests: line chart, area chart

response.chart_suggestions[0].chart_type == "line"
response.chart_suggestions[0].x_column == "date"
response.chart_suggestions[0].y_columns == ["revenue"]
```

### Categorical Comparisons
```python
# Results with categorical and numeric columns
# Suggests: bar chart, pie chart

response.chart_suggestions[0].chart_type == "bar"
response.chart_suggestions[0].x_column == "category"
response.chart_suggestions[0].y_columns == ["amount"]
```

### Single Metrics
```python
# Results with single numeric value
# Suggests: metric card

response.chart_suggestions[0].chart_type == "metric"
response.chart_suggestions[0].y_columns == ["total_revenue"]
```

## Configuration

### Enable/Disable Caching

```python
agent = InsightsAgent(
    llm_provider=llm,
    mcp_client=client,
    kb=kb,
    project_id="my-project",
    enable_caching=True  # Cache LLM responses
)
```

### Retry Configuration

```python
agent = InsightsAgent(
    llm_provider=llm,
    mcp_client=client,
    kb=kb,
    project_id="my-project",
    max_retries=3  # Retry failed operations
)
```

## Testing

Run the agent tests:

```bash
# All agent tests
uv run pytest tests/agent/ -v

# Specific test file
uv run pytest tests/agent/test_conversation.py -v

# With coverage
uv run pytest tests/agent/ -v --cov=src/mcp_bigquery/agent
```

## Architecture

```
User Question
    ↓
AgentRequest (with permissions)
    ↓
InsightsAgent.process_question()
    ↓
├─→ Get conversation context (Supabase)
├─→ Generate SQL (LLM + schema)
├─→ Execute query (MCP Client)
├─→ Generate summary (LLM)
├─→ Generate chart suggestions (LLM)
└─→ Save conversation turn (Supabase)
    ↓
AgentResponse (structured output)
```

## Best Practices

1. **Session Management**: Use consistent session IDs for related questions
2. **Context Length**: Limit `context_turns` to avoid token limits (5-10 recommended)
3. **Error Handling**: Always check `response.success` before using results
4. **Permissions**: Always provide accurate user permissions to prevent unauthorized access
5. **Caching**: Enable caching for production to reduce LLM costs
6. **Monitoring**: Log agent interactions for debugging and improvement

## Future Enhancements

Potential areas for extension:

- Multi-turn query refinement
- Schema-based query suggestions
- Query optimization recommendations
- Cost estimation before execution
- Export to various formats
- Integration with BI tools
- Multi-language support
- Custom prompt templates
