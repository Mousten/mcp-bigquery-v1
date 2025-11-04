# Agent Architecture Investigation & Redesign

## Executive Summary

**Status**: The AI agent is fundamentally broken - it exists but is not exposed as an API endpoint and cannot make intelligent tool decisions. The agent has good foundations but lacks proper tool orchestration and LLM-driven decision making.

**Root Causes**:
1. ❌ Agent has no HTTP endpoint - not accessible to users
2. ❌ LLM doesn't receive tool descriptions or choose tools
3. ❌ Tool routing is hardcoded via pattern matching, not LLM reasoning
4. ❌ Agent is unaware of 50% of available tools
5. ❌ No multi-step reasoning capability
6. ❌ Always routes to SQL generation when patterns don't match

---

## Phase 1: Current State Documentation

### 1.1 Current Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CURRENT ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────┘

User Question
     ↓
[ NO HTTP ENDPOINT ] ← ❌ BROKEN: Agent not accessible
     ↓
ConversationManager (internal only)
     ↓
InsightsAgent.process_question()
     ↓
┌────────────────────────────────────────────────┐
│  Decision Logic: _is_metadata_question()       │
│  - Simple keyword pattern matching             │
│  - No LLM involvement in routing               │
└────────────────────────────────────────────────┘
     ↓
     ├─ "datasets" → _handle_datasets_question()
     │               └→ mcp_client.list_datasets()
     │
     ├─ "tables" → _handle_tables_question()
     │             └→ mcp_client.list_tables()
     │
     ├─ "schema" → _handle_schema_question()
     │             └→ mcp_client.get_table_schema()
     │
     └─ EVERYTHING ELSE → SQL Generation Flow
                          └→ LLM generates SQL
                          └→ mcp_client.execute_sql()
                          └→ Summarize results
```

### 1.2 Entry Point Analysis

**Current State**: ❌ **NO AGENT ENDPOINT EXISTS**

**Files Checked**:
- `src/mcp_bigquery/routes/chat.py` - Chat persistence only (sessions, messages)
- `src/mcp_bigquery/routes/tools.py` - Direct tool endpoints, no agent orchestration
- `src/mcp_bigquery/routes/http_stream.py` - SSE/NDJSON streaming, no agent
- `src/mcp_bigquery/routes/health.py` - Health checks
- `src/mcp_bigquery/routes/resources.py` - MCP resources
- `src/mcp_bigquery/routes/events.py` - Event logging
- `src/mcp_bigquery/routes/preferences.py` - User preferences

**Finding**: The agent exists in `agent/conversation.py` and `agent/conversation_manager.py` but is never exposed as an HTTP endpoint.

**How Users Currently Access Tools**:
- Direct tool endpoints: `POST /tools/query`, `GET /tools/datasets`, etc.
- No intelligent routing or multi-step reasoning
- Users must know which tool to call manually

### 1.3 Agent Decision Logic

**Location**: `src/mcp_bigquery/agent/conversation.py` - `InsightsAgent` class

**Current Decision Process**:

```python
async def process_question(self, request: AgentRequest) -> AgentResponse:
    # Step 1: Get conversation context
    context = await self._get_conversation_context(...)
    
    # Step 2: Check if metadata question via pattern matching
    metadata_type = self._is_metadata_question(request.question)
    
    if metadata_type:
        # Route to metadata handlers
        if metadata_type == "datasets":
            response = await self._handle_datasets_question()
        elif metadata_type == "tables":
            response = await self._handle_tables_question(...)
        elif metadata_type == "schema":
            response = await self._handle_schema_question(...)
    else:
        # Everything else → SQL generation
        sql_result = await self._generate_sql(...)
        query_results = await self._execute_query(sql_result.sql)
        summary = await self._generate_summary(...)
        chart_suggestions = await self._generate_chart_suggestions(...)
```

**Pattern Matching** (`_is_metadata_question`):
```python
def _is_metadata_question(self, question: str) -> Optional[str]:
    question_lower = question.lower()
    
    # Dataset patterns
    dataset_patterns = [
        "what datasets", "list datasets", "show datasets", 
        "available datasets", "which datasets", ...
    ]
    if any(pattern in question_lower for pattern in dataset_patterns):
        return "datasets"
    
    # Table patterns
    table_patterns = [
        "what tables", "list tables", "show tables",
        "available tables", "tables in", ...
    ]
    if any(pattern in question_lower for pattern in table_patterns):
        return "tables"
    
    # Schema patterns
    schema_patterns = [
        "describe table", "table schema", "schema of",
        "table structure", "what columns", ...
    ]
    if any(pattern in question_lower for pattern in schema_patterns):
        return "schema"
    
    return None  # → Defaults to SQL generation
```

**Problems with Current Routing**:
1. ❌ Brittle pattern matching - easily broken by variations
2. ❌ No LLM reasoning about which tool to use
3. ❌ Falls back to SQL generation for unmatched patterns
4. ❌ Can't handle complex multi-step queries
5. ❌ Only knows about 3 tool types (datasets, tables, schemas)

### 1.4 LLM Integration

**Current LLM Usage**:

1. **SQL Generation** (`_generate_sql`):
   ```python
   # Build system prompt with user permissions
   system_prompt = self.prompt_builder.build_system_prompt(
       allowed_datasets=context.allowed_datasets,
       allowed_tables=context.allowed_tables,
       project_id=self.project_id
   )
   
   # Get relevant schema info
   schema_info = await self._get_relevant_schemas(...)
   
   # Build SQL generation prompt
   user_prompt = self.prompt_builder.build_sql_generation_prompt(
       question=question,
       schema_info=schema_info,
       conversation_history=conversation_history
   )
   
   # Call LLM
   messages = [
       Message(role="system", content=system_prompt),
       Message(role="user", content=user_prompt)
   ]
   response = await self.llm.generate(messages=messages, ...)
   ```

2. **Result Summarization** (`_generate_summary`):
   - Takes query results and generates business-friendly summary

3. **Chart Suggestions** (`_generate_chart_suggestions`):
   - Analyzes result schema and suggests visualizations

**What's Missing**:
- ❌ LLM doesn't receive tool descriptions
- ❌ LLM can't choose which tool to use
- ❌ No function calling / tool use API integration
- ❌ LLM only generates SQL, doesn't orchestrate tools
- ❌ No multi-step reasoning loop

### 1.5 Tool Inventory

**MCP Tools Registered** (in `api/mcp_app.py`):

#### Tools the Agent Knows About (via hardcoded routing):
| Tool | MCP Name | Purpose | Agent Handler |
|------|----------|---------|---------------|
| List Datasets | `get_datasets` | List all accessible datasets | `_handle_datasets_question()` |
| List Tables | `get_tables` | List tables in a dataset | `_handle_tables_question()` |
| Get Schema | `get_table_schema` | Get table schema/columns | `_handle_schema_question()` |
| Execute SQL | `execute_bigquery_sql` | Run SQL queries | `_execute_query()` |

#### Tools the Agent DOESN'T Know About:
| Tool | MCP Name | Purpose | Current Usage |
|------|----------|---------|---------------|
| Query Suggestions | `get_query_suggestions` | AI-powered query recommendations | ❌ Never used |
| Explain Table | `explain_table` | Explain table usage and context | ❌ Never used |
| Query Performance | `analyze_query_performance` | Analyze query performance | ❌ Never used |
| Schema Changes | `get_schema_changes` | Track schema evolution | ❌ Never used |
| Cache Management | `cache_management` | Manage query cache | ❌ Never used |

**Problem**: The agent only uses 4 out of 9 available tools!

#### Detailed Tool Specifications:

**1. execute_bigquery_sql**
```python
@mcp_app.tool(
    name="execute_bigquery_sql",
    description="Execute a read-only SQL query on BigQuery with intelligent caching"
)
async def execute_bigquery_sql(
    sql: str,
    auth_token: str,
    maximum_bytes_billed: int = 314572800,
    use_cache: bool = True,
    force_refresh: bool = False
) -> dict
```
- **Input**: SQL query string
- **Output**: Query results with rows and statistics
- **When to use**: User wants actual data from tables

**2. get_datasets**
```python
@mcp_app.tool(
    name="get_datasets",
    description="Retrieve the list of all datasets the user has access to"
)
async def get_datasets(auth_token: str) -> dict
```
- **Input**: None (auth only)
- **Output**: List of dataset objects
- **When to use**: "what datasets do I have?", "list datasets"

**3. get_tables**
```python
@mcp_app.tool(
    name="get_tables",
    description="Retrieve all tables within a specific dataset"
)
async def get_tables(dataset_id: str, auth_token: str) -> dict
```
- **Input**: dataset_id
- **Output**: List of table objects
- **When to use**: "show tables in Analytics", "list tables in dataset X"

**4. get_table_schema**
```python
@mcp_app.tool(
    name="get_table_schema",
    description="Retrieve comprehensive schema details for a specific table"
)
async def get_table_schema(
    dataset_id: str,
    table_id: str,
    auth_token: str,
    include_samples: bool = True,
    include_documentation: bool = True
) -> dict
```
- **Input**: dataset_id, table_id
- **Output**: Schema with columns, types, documentation
- **When to use**: "describe table X", "what columns does Y have?"

**5. get_query_suggestions** ❌ NOT USED BY AGENT
```python
@mcp_app.tool(
    name="get_query_suggestions",
    description="Get AI-powered query recommendations based on table schemas and usage patterns"
)
async def get_query_suggestions(
    auth_token: str,
    tables_mentioned: Optional[List[str]] = None,
    query_context: Optional[str] = None,
    limit: int = 5
) -> dict
```
- **When to use**: "what queries can I run?", "suggest some queries", "what insights can I get?"

**6. explain_table** ❌ NOT USED BY AGENT
```python
@mcp_app.tool(
    name="explain_table",
    description="Get detailed explanation of table purpose, usage patterns, and business context"
)
async def explain_table(
    dataset_id: str,
    table_id: str,
    auth_token: str
) -> dict
```
- **When to use**: "what is this table for?", "explain the Sales table"

**7. analyze_query_performance** ❌ NOT USED BY AGENT
```python
@mcp_app.tool(
    name="analyze_query_performance",
    description="Analyze query execution performance and get optimization suggestions"
)
async def analyze_query_performance(
    query_id: Optional[str] = None,
    sql: Optional[str] = None,
    auth_token: str = None
) -> dict
```
- **When to use**: "why is this query slow?", "how can I optimize this?"

**8. get_schema_changes** ❌ NOT USED BY AGENT
```python
@mcp_app.tool(
    name="get_schema_changes",
    description="Track schema evolution and changes over time"
)
async def get_schema_changes(
    project_id: str,
    dataset_id: Optional[str] = None,
    table_id: Optional[str] = None,
    auth_token: str = None,
    limit: int = 10
) -> dict
```
- **When to use**: "has the schema changed?", "what changed in this table?"

**9. cache_management** ❌ NOT USED BY AGENT
```python
@mcp_app.tool(
    name="cache_management",
    description="Manage query result caching"
)
async def cache_management(
    operation: str,
    auth_token: str,
    query_hash: Optional[str] = None
) -> dict
```
- **When to use**: "clear my cache", "show cached queries"

### 1.6 System Prompts

**Current System Prompt** (from `agent/prompts.py`):

```python
SYSTEM_PROMPT_TEMPLATE = """You are an AI assistant specialized in BigQuery data analysis.

**Your Capabilities:**
- Generate SQL queries for BigQuery to query actual data
- Analyze query results and provide insights
- Suggest appropriate visualizations
- Answer follow-up questions using conversation context

**User Permissions:**
The user has access to the following datasets and tables:
{dataset_permissions}

**CRITICAL: Table Name Accuracy**
- ALWAYS use the EXACT table names provided in the schema information
- NEVER transform, modify, or guess table names
[...more constraints...]

**Important: Metadata vs Data Queries:**
- Questions about listing datasets, tables, or schemas should NOT generate SQL
- These metadata questions are handled automatically by the system
- ONLY generate SQL for actual data queries

**Response Format:**
When generating SQL, structure your response as a JSON object with:
- "sql": The SQL query string
- "explanation": Brief explanation
- "tables_used": List of EXACT table names
- "estimated_complexity": "low", "medium", or "high"
- "warnings": List of any potential issues
"""
```

**Problems**:
- ❌ No mention of available tools
- ❌ No instructions on when to use which tool
- ❌ Only describes SQL generation capability
- ❌ Doesn't tell LLM it can call tools
- ❌ No function calling setup

### 1.7 Root Cause Analysis

#### Root Cause #1: No Agent API Endpoint
**Problem**: Agent exists but isn't exposed via HTTP
**Impact**: Users can't access intelligent agent, only direct tool calls
**Evidence**: No routes found in `routes/` directory for agent
**Fix Required**: Create `/chat/ask` or `/agent/query` endpoint

#### Root Cause #2: No LLM Tool Selection
**Problem**: LLM doesn't receive tool descriptions or choose tools
**Impact**: Agent uses hardcoded patterns instead of reasoning
**Evidence**: No function calling setup in LLM integration
**Fix Required**: Implement OpenAI function calling or Anthropic tool use

#### Root Cause #3: Missing Tool Registry
**Problem**: No formal tool registry with descriptions
**Impact**: Agent unaware of 50% of available tools
**Evidence**: Only 4/9 tools have handlers in agent
**Fix Required**: Create ToolRegistry with all tool definitions

#### Root Cause #4: No Multi-Step Reasoning
**Problem**: Agent processes question → single tool call → done
**Impact**: Can't handle complex queries requiring multiple steps
**Evidence**: No loop for iterative tool calling
**Fix Required**: Implement reasoning loop (ReAct pattern or native tool use)

#### Root Cause #5: Pattern Matching Instead of Intelligence
**Problem**: Simple keyword matching for routing
**Impact**: Brittle, can't handle variations or complex questions
**Evidence**: `_is_metadata_question()` uses hardcoded patterns
**Fix Required**: Let LLM make routing decisions

---

## Phase 2: New Architecture Design

### 2.1 Design Principles

1. **LLM as the Brain**
   - LLM makes ALL tool selection decisions
   - Use native function calling (OpenAI tools / Anthropic tool use)
   - LLM reasons before acting

2. **Tool Registry Pattern**
   - Single source of truth for all tools
   - Each tool has clear description, parameters, examples
   - Easy to add new tools

3. **Multi-Step Reasoning**
   - Agent can call multiple tools in sequence
   - Each tool result informs next decision
   - Support for reasoning loops (up to N iterations)

4. **Proper API Exposure**
   - New `/chat/ask` endpoint for agent queries
   - Streaming support for long-running queries
   - Backward compatible with existing endpoints

5. **Context Awareness**
   - Track conversation state
   - Remember user's current context (dataset, table)
   - Use history to inform decisions

### 2.2 Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       NEW SMART ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────┘

User Question
     ↓
POST /chat/ask (NEW ENDPOINT)
     ↓
AgentController
     ↓
SmartAgent (NEW)
     ↓
┌────────────────────────────────────────────────────────┐
│  LLM with Tool Descriptions (OpenAI Functions)         │
│  - Receives ALL 9 tool definitions                     │
│  - Reasons about which tool(s) to use                  │
│  - Can call multiple tools in sequence                 │
└────────────────────────────────────────────────────────┘
     ↓
LLM Decision: "I need to call get_tables with dataset=Analytics"
     ↓
ToolExecutor.execute_tool("get_tables", {"dataset_id": "Analytics"})
     ↓
Tool Result: [list of tables]
     ↓
Back to LLM: "Here are the tables: [...]"
     ↓
LLM Decision: "Now I'll call get_table_schema for table X"
     ↓
ToolExecutor.execute_tool("get_table_schema", {...})
     ↓
Tool Result: [schema]
     ↓
Back to LLM: "Generate final response"
     ↓
LLM Response: "The Analytics dataset contains 5 tables. Table X has..."
     ↓
Response to User
```

### 2.3 Component Design

#### 2.3.1 ToolRegistry (NEW)
```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    examples: List[str]
    
class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
    
    def register_tool(self, tool: ToolDefinition):
        self.tools[tool.name] = tool
    
    def get_openai_functions(self) -> List[Dict]:
        """Convert tools to OpenAI function calling format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in self.tools.values()
        ]
    
    def get_anthropic_tools(self) -> List[Dict]:
        """Convert tools to Anthropic tool use format"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters
            }
            for tool in self.tools.values()
        ]
```

#### 2.3.2 SmartAgent (NEW)
```python
class SmartAgent:
    """Intelligent agent that uses LLM to select and orchestrate tools."""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        mcp_client: MCPClient,
        kb: SupabaseKnowledgeBase,
        max_iterations: int = 5
    ):
        self.llm = llm_provider
        self.tools = tool_registry
        self.mcp_client = mcp_client
        self.kb = kb
        self.max_iterations = max_iterations
    
    async def process_question(
        self,
        question: str,
        user_context: UserContext,
        session_id: str,
        conversation_history: List[Dict]
    ) -> AgentResponse:
        """Process question with multi-step tool reasoning."""
        
        # Build messages with system prompt + tools
        messages = self._build_messages(
            question=question,
            conversation_history=conversation_history,
            user_context=user_context
        )
        
        # Get tool definitions for LLM
        tools = self.tools.get_openai_functions()  # or get_anthropic_tools()
        
        # Reasoning loop
        for iteration in range(self.max_iterations):
            # Let LLM decide what to do
            response = await self.llm.generate(
                messages=messages,
                tools=tools,
                tool_choice="auto"  # Let LLM decide
            )
            
            # Check if LLM wants to call tools
            if response.tool_calls:
                # Execute all tool calls
                tool_results = await self._execute_tool_calls(
                    response.tool_calls,
                    user_context
                )
                
                # Add tool results to conversation
                messages.append(response.to_message())
                messages.append(tool_results_message)
                
                # Continue loop - LLM will see results and decide next step
            else:
                # LLM gave final answer
                return self._create_response(response)
        
        # Max iterations reached
        return self._create_max_iterations_response()
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[ToolCall],
        user_context: UserContext
    ) -> List[Dict]:
        """Execute tool calls and return results."""
        results = []
        
        for tool_call in tool_calls:
            try:
                # Get tool handler
                tool = self.tools.get_tool(tool_call.name)
                
                # Execute tool
                result = await tool.handler(
                    **tool_call.arguments,
                    user_context=user_context
                )
                
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.name,
                    "content": json.dumps(result)
                })
            except Exception as e:
                # Return error to LLM so it can handle it
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.name,
                    "content": json.dumps({
                        "error": str(e),
                        "suggestion": self._get_error_suggestion(e)
                    })
                })
        
        return results
```

#### 2.3.3 Enhanced System Prompt
```python
SMART_AGENT_SYSTEM_PROMPT = """You are an intelligent BigQuery assistant with access to multiple tools.

**Available Tools:**
You have access to the following tools to help users explore and analyze their BigQuery data:

1. **get_datasets()** - List all datasets the user can access
   Use when: User asks "what datasets do I have?", "list datasets", "show my data"

2. **get_tables(dataset_id)** - List all tables in a specific dataset
   Use when: User asks "what tables are in X?", "show tables in dataset Y"

3. **get_table_schema(dataset_id, table_id)** - Get detailed schema for a table
   Use when: User asks "describe table X", "what columns does Y have?", "show me the schema"

4. **execute_bigquery_sql(sql)** - Execute a SQL query and return results
   Use when: User wants actual data, aggregations, or analysis

5. **get_query_suggestions(tables_mentioned, query_context)** - Get AI-powered query recommendations
   Use when: User asks "what can I query?", "suggest some queries", "what insights can I get?"

6. **explain_table(dataset_id, table_id)** - Get explanation of table's purpose and usage
   Use when: User asks "what is this table for?", "explain table X"

7. **analyze_query_performance(query_id or sql)** - Analyze query performance
   Use when: User asks "why is this slow?", "optimize my query", "performance issues"

8. **get_schema_changes(project_id, dataset_id, table_id)** - Track schema evolution
   Use when: User asks "has the schema changed?", "what changed in this table?"

9. **cache_management(operation)** - Manage query cache
   Use when: User asks "clear my cache", "show cached queries"

**Decision Making Process:**
1. Understand what the user is asking for
2. Determine which tool(s) you need to call
3. Call tools in the right order (e.g., get_tables before get_table_schema)
4. If a tool fails, explain the error and suggest alternatives
5. Synthesize tool results into a clear, helpful answer

**Multi-Step Reasoning:**
You can call multiple tools in sequence. For example:
- "Show me the schema of the largest table" → get_tables → get_table_schema
- "What queries can I run on the Sales data?" → get_tables → get_query_suggestions
- "Analyze the performance of my last query" → (user mentions query) → analyze_query_performance

**NEVER:**
- Guess or hallucinate table names - always verify with get_tables first
- Generate SQL without checking if tables exist
- Ignore tool errors - always explain them to the user

**User Permissions:**
The user has access to:
{dataset_permissions}

**Response Format:**
Always provide clear, actionable answers. Explain your reasoning when making decisions.
"""
```

#### 2.3.4 New API Route
```python
# routes/agent.py (NEW FILE)

@router.post("/chat/ask")
async def ask_agent(
    request: AgentQueryRequest,
    user: UserContext = Depends(auth_dependency)
) -> AgentResponse:
    """Ask the intelligent agent a question.
    
    The agent will:
    1. Understand your question
    2. Decide which tools to use
    3. Call tools in the right order
    4. Synthesize results into a clear answer
    
    Args:
        request: Question and optional session context
        user: Authenticated user context
        
    Returns:
        Agent response with answer and metadata
    """
    smart_agent = get_smart_agent()  # From dependency injection
    
    response = await smart_agent.process_question(
        question=request.question,
        user_context=user,
        session_id=request.session_id,
        conversation_history=request.conversation_history
    )
    
    return response

@router.post("/chat/ask/stream")
async def ask_agent_stream(
    request: AgentQueryRequest,
    user: UserContext = Depends(auth_dependency)
) -> StreamingResponse:
    """Stream agent responses for long-running queries."""
    # Similar but streams tool calls and results
    pass
```

### 2.4 Tool Registration

**Complete Tool Registry Setup**:
```python
def initialize_tool_registry(mcp_client: MCPClient) -> ToolRegistry:
    registry = ToolRegistry()
    
    # Tool 1: Get Datasets
    registry.register_tool(ToolDefinition(
        name="get_datasets",
        description="Retrieve list of all BigQuery datasets the user has access to. Use this when user asks about available datasets or wants to see their data sources.",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        },
        handler=lambda user_context: mcp_client.list_datasets(),
        examples=[
            "What datasets do I have?",
            "List all my datasets",
            "Show me available data sources"
        ]
    ))
    
    # Tool 2: Get Tables
    registry.register_tool(ToolDefinition(
        name="get_tables",
        description="List all tables within a specific BigQuery dataset. Use when user wants to see what tables are available in a dataset.",
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "The dataset ID to list tables from"
                }
            },
            "required": ["dataset_id"]
        },
        handler=lambda dataset_id, user_context: mcp_client.list_tables(dataset_id),
        examples=[
            "Show tables in the Analytics dataset",
            "What tables are in dataset X?",
            "List tables in the Sales dataset"
        ]
    ))
    
    # Tool 3: Get Table Schema
    registry.register_tool(ToolDefinition(
        name="get_table_schema",
        description="Get detailed schema information for a specific table including column names, types, and descriptions. Use when user asks about table structure or wants to know what columns are available.",
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset ID"},
                "table_id": {"type": "string", "description": "Table ID"},
                "include_samples": {"type": "boolean", "description": "Include sample data", "default": True},
                "include_documentation": {"type": "boolean", "description": "Include column documentation", "default": True}
            },
            "required": ["dataset_id", "table_id"]
        },
        handler=lambda dataset_id, table_id, include_samples, include_documentation, user_context: 
            mcp_client.get_table_schema(dataset_id, table_id, include_samples, include_documentation),
        examples=[
            "Describe the Daily_Sales table",
            "What columns does the Users table have?",
            "Show me the schema of dataset.table"
        ]
    ))
    
    # Tool 4: Execute SQL
    registry.register_tool(ToolDefinition(
        name="execute_bigquery_sql",
        description="Execute a read-only SQL query on BigQuery and return results. Use when user wants actual data, aggregations, or analysis. ALWAYS verify table names exist before generating SQL.",
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL SELECT query to execute"},
                "maximum_bytes_billed": {"type": "integer", "description": "Max bytes to bill", "default": 314572800},
                "use_cache": {"type": "boolean", "description": "Use cached results", "default": True}
            },
            "required": ["sql"]
        },
        handler=lambda sql, maximum_bytes_billed, use_cache, user_context:
            mcp_client.execute_sql(sql, maximum_bytes_billed, use_cache),
        examples=[
            "Show me top 10 rows from Sales",
            "What's the total revenue by product?",
            "Count users by country"
        ]
    ))
    
    # Tool 5: Get Query Suggestions
    registry.register_tool(ToolDefinition(
        name="get_query_suggestions",
        description="Get AI-powered query recommendations based on table schemas and usage patterns. Use when user asks what queries they can run or wants inspiration for data exploration.",
        parameters={
            "type": "object",
            "properties": {
                "tables_mentioned": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of table names mentioned by user"
                },
                "query_context": {"type": "string", "description": "Context about what user wants to analyze"},
                "limit": {"type": "integer", "description": "Max suggestions to return", "default": 5}
            },
            "required": []
        },
        handler=lambda tables_mentioned, query_context, limit, user_context:
            mcp_client.get_query_suggestions(tables_mentioned, query_context, limit),
        examples=[
            "What queries can I run?",
            "Suggest some interesting queries on the Sales data",
            "What insights can I get from this table?"
        ]
    ))
    
    # Tool 6: Explain Table
    registry.register_tool(ToolDefinition(
        name="explain_table",
        description="Get detailed explanation of a table's purpose, business context, and typical usage patterns. Use when user wants to understand what a table is for or how to use it.",
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset ID"},
                "table_id": {"type": "string", "description": "Table ID"}
            },
            "required": ["dataset_id", "table_id"]
        },
        handler=lambda dataset_id, table_id, user_context:
            mcp_client.explain_table(dataset_id, table_id),
        examples=[
            "What is the Sales table for?",
            "Explain the Users table",
            "Tell me about this table's purpose"
        ]
    ))
    
    # Tool 7: Analyze Query Performance
    registry.register_tool(ToolDefinition(
        name="analyze_query_performance",
        description="Analyze query execution performance and get optimization suggestions. Use when user reports slow queries or asks for optimization advice.",
        parameters={
            "type": "object",
            "properties": {
                "query_id": {"type": "string", "description": "BigQuery job ID of executed query"},
                "sql": {"type": "string", "description": "SQL query to analyze"}
            },
            "required": []  # At least one should be provided
        },
        handler=lambda query_id, sql, user_context:
            mcp_client.analyze_query_performance(query_id, sql),
        examples=[
            "Why is my query slow?",
            "How can I optimize this query?",
            "Analyze performance of my last query"
        ]
    ))
    
    # Tool 8: Get Schema Changes
    registry.register_tool(ToolDefinition(
        name="get_schema_changes",
        description="Track schema evolution and changes over time for tables. Use when user wants to know if schema has changed or see history of modifications.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "GCP project ID"},
                "dataset_id": {"type": "string", "description": "Dataset ID (optional)"},
                "table_id": {"type": "string", "description": "Table ID (optional)"},
                "limit": {"type": "integer", "description": "Max changes to return", "default": 10}
            },
            "required": ["project_id"]
        },
        handler=lambda project_id, dataset_id, table_id, limit, user_context:
            mcp_client.get_schema_changes(project_id, dataset_id, table_id, limit),
        examples=[
            "Has the schema changed?",
            "Show me schema history for this table",
            "What changed in the Users table?"
        ]
    ))
    
    # Tool 9: Cache Management
    registry.register_tool(ToolDefinition(
        name="cache_management",
        description="Manage query result caching - clear cache, view cached queries, or refresh specific entries. Use when user wants to manage their cached data.",
        parameters={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "clear", "clear_all", "refresh"],
                    "description": "Cache operation to perform"
                },
                "query_hash": {"type": "string", "description": "Specific query hash for clear/refresh operations"}
            },
            "required": ["operation"]
        },
        handler=lambda operation, query_hash, user_context:
            mcp_client.cache_management(operation, query_hash),
        examples=[
            "Clear my query cache",
            "Show me cached queries",
            "Refresh cached data"
        ]
    ))
    
    return registry
```

### 2.5 Migration Strategy

**Phase 1: Build New Components (Non-Breaking)**
1. Create `ToolRegistry` class
2. Create `SmartAgent` class
3. Add new `/chat/ask` endpoint
4. Keep existing agent code intact

**Phase 2: Switch Agent Implementation**
1. Update `ConversationManager` to use `SmartAgent`
2. Add feature flag for new vs old agent
3. Test with subset of users

**Phase 3: Deprecate Old Code**
1. Remove pattern matching logic
2. Remove old metadata handlers
3. Clean up unused code

**Phase 4: Documentation & Training**
1. Update API documentation
2. Create user guides
3. Add examples for common use cases

---

## Phase 3: Implementation Checklist

### Step 1: Core Components ✅ TODO
- [ ] Create `src/mcp_bigquery/agent/tool_registry.py`
- [ ] Create `src/mcp_bigquery/agent/smart_agent.py`
- [ ] Update `src/mcp_bigquery/agent/prompts.py` with new system prompt
- [ ] Add unit tests for ToolRegistry
- [ ] Add unit tests for SmartAgent

### Step 2: Tool Integration ✅ TODO
- [ ] Register all 9 tools in ToolRegistry
- [ ] Create tool handler wrappers for MCP client
- [ ] Add error handling for each tool
- [ ] Add tool execution logging
- [ ] Test each tool individually

### Step 3: LLM Integration ✅ TODO
- [ ] Add OpenAI function calling support
- [ ] Add Anthropic tool use support
- [ ] Implement tool call parsing
- [ ] Implement multi-step reasoning loop
- [ ] Add max iterations safeguard

### Step 4: API Endpoint ✅ TODO
- [ ] Create `src/mcp_bigquery/routes/agent.py`
- [ ] Implement `/chat/ask` endpoint
- [ ] Implement `/chat/ask/stream` endpoint
- [ ] Add request/response models
- [ ] Add authentication
- [ ] Add rate limiting

### Step 5: Testing ✅ TODO
- [ ] Unit tests for tool registry
- [ ] Unit tests for smart agent
- [ ] Integration tests for agent endpoint
- [ ] Test multi-step reasoning
- [ ] Test all tool combinations
- [ ] Test error handling
- [ ] Test rate limiting

### Step 6: Documentation ✅ TODO
- [ ] API documentation for `/chat/ask`
- [ ] Tool usage examples
- [ ] Migration guide
- [ ] User guide
- [ ] Developer guide

---

## Phase 4: Success Metrics

### Functional Requirements
- ✅ Agent correctly routes 100% of test questions to appropriate tools
- ✅ Agent can list datasets, tables, and schemas without errors
- ✅ Agent validates table names before generating SQL
- ✅ Agent provides clear, helpful error messages
- ✅ Agent can handle multi-step reasoning
- ✅ Agent maintains conversation context
- ✅ Agent uses ALL available tools appropriately

### Quality Requirements
- ✅ Agent NEVER hallucinates table names
- ✅ Agent ALWAYS verifies resources exist before using them
- ✅ Agent explains its reasoning to users
- ✅ Agent provides actionable error messages
- ✅ Agent maintains context across conversation
- ✅ LLM makes intelligent tool selection decisions

### Performance Requirements
- ✅ Agent responds within 5 seconds for simple queries
- ✅ Agent responds within 15 seconds for complex multi-step queries
- ✅ Tool calls execute in parallel when possible
- ✅ Caching reduces repeated queries

---

## Appendix A: Example Conversations

### Example 1: Multi-Step Discovery
```
User: "Show me the schema of the largest table in the Analytics dataset"

Agent Reasoning:
1. Call get_tables(dataset_id="Analytics") to see all tables
2. Identify largest table from results (by num_bytes)
3. Call get_table_schema(dataset_id="Analytics", table_id="largest_table")
4. Format and present schema

Response: "The Analytics dataset has 5 tables. The largest is Daily_Sales (2.3 GB) with the following schema: [schema details]"
```

### Example 2: Query Suggestions
```
User: "What interesting queries can I run on the Sales data?"

Agent Reasoning:
1. Call get_tables(dataset_id="Sales") to see available tables
2. Call get_query_suggestions(tables_mentioned=["Sales.Orders", "Sales.Products"], query_context="interesting queries")
3. Present suggestions with explanations

Response: "Here are 5 interesting queries you can run on the Sales data:
1. Top 10 products by revenue - Shows which products generate the most sales
2. Sales trends over time - Identifies seasonal patterns
[...]"
```

### Example 3: Performance Investigation
```
User: "My query is really slow: SELECT * FROM Sales.Orders WHERE date > '2024-01-01'"

Agent Reasoning:
1. Call analyze_query_performance(sql="SELECT * FROM Sales.Orders WHERE date > '2024-01-01'")
2. Get optimization recommendations
3. Explain findings to user

Response: "Your query is slow because:
1. SELECT * retrieves all columns - specify only needed columns
2. No LIMIT clause - consider adding LIMIT for testing
3. No partition filter - the date column is partitioned, use DATE(date) for better performance

Optimized query:
SELECT order_id, customer_id, amount, date
FROM Sales.Orders
WHERE DATE(date) > '2024-01-01'
LIMIT 1000"
```

### Example 4: Schema Evolution
```
User: "Has the Users table schema changed recently?"

Agent Reasoning:
1. Call get_schema_changes(project_id="my-project", dataset_id="Analytics", table_id="Users")
2. Analyze changes
3. Present findings

Response: "Yes, the Users table has had 2 schema changes in the past 30 days:
1. 2024-10-15: Added column 'last_login_at' (TIMESTAMP)
2. 2024-10-20: Added column 'subscription_tier' (STRING)

These changes are backward compatible (columns are nullable)."
```

---

## Appendix B: Code Locations

### Current Agent Code
- `src/mcp_bigquery/agent/conversation.py` - InsightsAgent (current implementation)
- `src/mcp_bigquery/agent/conversation_manager.py` - ConversationManager
- `src/mcp_bigquery/agent/prompts.py` - Prompt templates
- `src/mcp_bigquery/agent/models.py` - Pydantic models
- `src/mcp_bigquery/agent/mcp_client.py` - MCP client wrapper

### MCP Tools
- `src/mcp_bigquery/api/mcp_app.py` - Tool registration
- `src/mcp_bigquery/handlers/tools.py` - Tool handlers

### Routes
- `src/mcp_bigquery/routes/chat.py` - Chat persistence
- `src/mcp_bigquery/routes/tools.py` - Direct tool endpoints
- `src/mcp_bigquery/routes/http_stream.py` - Streaming

### New Files to Create
- `src/mcp_bigquery/agent/tool_registry.py` - Tool registry
- `src/mcp_bigquery/agent/smart_agent.py` - New smart agent
- `src/mcp_bigquery/routes/agent.py` - Agent API endpoint

---

## Conclusion

The agent has good foundations but is fundamentally broken due to:
1. No API exposure
2. No LLM-driven tool selection
3. Limited tool awareness (only 4/9 tools)
4. Hardcoded pattern matching instead of reasoning

The proposed redesign fixes all root causes by:
1. Creating `/chat/ask` API endpoint
2. Implementing LLM function calling for tool selection
3. Creating comprehensive tool registry
4. Enabling multi-step reasoning
5. Making all 9 tools accessible to the agent

This transforms the agent from a "dumb SQL generator" into an "intelligent data assistant".
