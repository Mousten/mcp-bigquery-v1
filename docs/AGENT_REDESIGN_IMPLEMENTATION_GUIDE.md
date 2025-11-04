# Agent Redesign Implementation Guide

## Quick Start

This guide provides step-by-step instructions for implementing the agent redesign based on the comprehensive investigation in `AGENT_ARCHITECTURE_INVESTIGATION.md`.

---

## Implementation Overview

**Goal**: Transform the agent from a "dumb SQL generator" into an "intelligent data assistant" that can:
- Make smart decisions about which tools to use
- Call multiple tools in sequence
- Handle complex multi-step queries
- Use ALL available tools (not just 4/9)
- Be accessible via API endpoint

**Approach**: Build new components alongside existing code, then switch over with feature flag.

---

## Step-by-Step Implementation

### Step 1: Create Tool Registry

**File**: `src/mcp_bigquery/agent/tool_registry.py`

```python
"""Tool registry for the smart agent."""

import logging
from typing import Dict, Any, List, Callable, Optional
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class ToolParameter(BaseModel):
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None  # For enum types


class ToolDefinition(BaseModel):
    """Complete definition of an available tool."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format
    handler: Any  # Callable - can't validate with Pydantic
    examples: List[str] = Field(default_factory=list)
    category: str = "general"  # metadata, data, performance, etc.
    
    class Config:
        arbitrary_types_allowed = True


class ToolRegistry:
    """Registry of all tools available to the smart agent.
    
    This provides a single source of truth for:
    - Tool definitions
    - Tool handlers
    - Tool descriptions for LLM
    - OpenAI function calling format
    - Anthropic tool use format
    
    Example:
        registry = ToolRegistry()
        registry.register_tool(ToolDefinition(
            name="get_datasets",
            description="List all BigQuery datasets",
            parameters={"type": "object", "properties": {}},
            handler=lambda: mcp_client.list_datasets(),
            examples=["What datasets do I have?"]
        ))
        
        # Get for OpenAI
        openai_funcs = registry.get_openai_functions()
        
        # Execute tool
        result = await registry.execute_tool("get_datasets", {})
    """
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        logger.info("ToolRegistry initialized")
    
    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a tool in the registry.
        
        Args:
            tool: Tool definition to register
        """
        if tool.name in self.tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (category: {tool.category})")
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool definition or None if not found
        """
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())
    
    def get_openai_functions(self) -> List[Dict[str, Any]]:
        """Convert tools to OpenAI function calling format.
        
        Returns:
            List of OpenAI function definitions
        """
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
    
    def get_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Convert tools to Anthropic tool use format.
        
        Returns:
            List of Anthropic tool definitions
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters
            }
            for tool in self.tools.values()
        ]
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        **extra_context
    ) -> Any:
        """Execute a tool by name with given arguments.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Arguments to pass to tool
            **extra_context: Additional context (e.g., user_context)
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool not found
            Exception: If tool execution fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        try:
            # Merge arguments with extra context
            all_args = {**arguments, **extra_context}
            
            # Execute tool handler
            result = await tool.handler(**all_args)
            
            logger.info(f"Tool {tool_name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            raise
    
    def get_tools_by_category(self, category: str) -> List[ToolDefinition]:
        """Get all tools in a specific category.
        
        Args:
            category: Tool category
            
        Returns:
            List of tool definitions in that category
        """
        return [
            tool for tool in self.tools.values()
            if tool.category == category
        ]


def create_tool_registry(mcp_client) -> ToolRegistry:
    """Create and populate the tool registry with all available tools.
    
    Args:
        mcp_client: MCP client instance for tool handlers
        
    Returns:
        Populated ToolRegistry
    """
    registry = ToolRegistry()
    
    # Category: Metadata
    
    registry.register_tool(ToolDefinition(
        name="get_datasets",
        description=(
            "Retrieve list of all BigQuery datasets the user has access to. "
            "Use this when user asks about available datasets, wants to see their data sources, "
            "or needs to know what datasets they can query."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        },
        handler=lambda user_context: mcp_client.list_datasets(),
        examples=[
            "What datasets do I have?",
            "List all my datasets",
            "Show me available data sources",
            "What data can I access?"
        ],
        category="metadata"
    ))
    
    registry.register_tool(ToolDefinition(
        name="get_tables",
        description=(
            "List all tables within a specific BigQuery dataset. "
            "Use when user wants to see what tables are available in a dataset, "
            "or needs to explore a dataset's contents."
        ),
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
            "List tables in the Sales dataset",
            "What's in the Analytics dataset?"
        ],
        category="metadata"
    ))
    
    registry.register_tool(ToolDefinition(
        name="get_table_schema",
        description=(
            "Get detailed schema information for a specific table including column names, "
            "data types, modes (NULLABLE, REQUIRED), and descriptions. "
            "Use when user asks about table structure, wants to know what columns are available, "
            "or needs to understand the data format before querying."
        ),
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "Dataset ID containing the table"
                },
                "table_id": {
                    "type": "string",
                    "description": "Table ID to get schema for"
                },
                "include_samples": {
                    "type": "boolean",
                    "description": "Whether to include sample data rows",
                    "default": True
                },
                "include_documentation": {
                    "type": "boolean",
                    "description": "Whether to include column documentation",
                    "default": True
                }
            },
            "required": ["dataset_id", "table_id"]
        },
        handler=lambda dataset_id, table_id, include_samples=True, include_documentation=True, user_context=None:
            mcp_client.get_table_schema(dataset_id, table_id, include_samples, include_documentation),
        examples=[
            "Describe the Daily_Sales table",
            "What columns does the Users table have?",
            "Show me the schema of Analytics.Orders",
            "What's the structure of the Sales table?"
        ],
        category="metadata"
    ))
    
    # Category: Data
    
    registry.register_tool(ToolDefinition(
        name="execute_bigquery_sql",
        description=(
            "Execute a read-only SQL query on BigQuery and return results. "
            "Use when user wants actual data, aggregations, counts, or analysis. "
            "IMPORTANT: ALWAYS verify table names exist by calling get_tables first before generating SQL. "
            "Only SELECT queries are allowed - no INSERT, UPDATE, DELETE, or DDL operations."
        ),
        parameters={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT query to execute with fully qualified table names (project.dataset.table)"
                },
                "maximum_bytes_billed": {
                    "type": "integer",
                    "description": "Maximum bytes to bill for the query (default: 300 MB)",
                    "default": 314572800
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to use cached query results",
                    "default": True
                }
            },
            "required": ["sql"]
        },
        handler=lambda sql, maximum_bytes_billed=314572800, use_cache=True, user_context=None:
            mcp_client.execute_sql(sql, maximum_bytes_billed, use_cache),
        examples=[
            "Show me top 10 rows from Sales",
            "What's the total revenue by product?",
            "Count users by country",
            "Get average order value for last month"
        ],
        category="data"
    ))
    
    registry.register_tool(ToolDefinition(
        name="get_query_suggestions",
        description=(
            "Get AI-powered query recommendations based on table schemas, usage patterns, "
            "and business context. Use when user asks what queries they can run, wants inspiration "
            "for data exploration, or needs examples of useful queries."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tables_mentioned": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of table names the user mentioned or is interested in"
                },
                "query_context": {
                    "type": "string",
                    "description": "Context about what user wants to analyze or their goals"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of suggestions to return",
                    "default": 5
                }
            },
            "required": []
        },
        handler=lambda tables_mentioned=None, query_context=None, limit=5, user_context=None:
            mcp_client.get_query_suggestions(tables_mentioned, query_context, limit),
        examples=[
            "What queries can I run?",
            "Suggest some interesting queries on the Sales data",
            "What insights can I get from this table?",
            "Give me query examples for the Orders table"
        ],
        category="data"
    ))
    
    # Category: Documentation
    
    registry.register_tool(ToolDefinition(
        name="explain_table",
        description=(
            "Get detailed explanation of a table's purpose, business context, typical usage patterns, "
            "and relationships to other tables. Use when user wants to understand what a table is for, "
            "how to use it, or its role in the data architecture."
        ),
        parameters={
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "Dataset ID containing the table"
                },
                "table_id": {
                    "type": "string",
                    "description": "Table ID to explain"
                }
            },
            "required": ["dataset_id", "table_id"]
        },
        handler=lambda dataset_id, table_id, user_context:
            mcp_client.explain_table(dataset_id, table_id),
        examples=[
            "What is the Sales table for?",
            "Explain the Users table",
            "Tell me about the Orders table's purpose",
            "How should I use the Analytics.Events table?"
        ],
        category="documentation"
    ))
    
    # Category: Performance
    
    registry.register_tool(ToolDefinition(
        name="analyze_query_performance",
        description=(
            "Analyze query execution performance and get optimization suggestions. "
            "Use when user reports slow queries, asks for optimization advice, "
            "or wants to understand query costs and bottlenecks."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query_id": {
                    "type": "string",
                    "description": "BigQuery job ID of an already-executed query"
                },
                "sql": {
                    "type": "string",
                    "description": "SQL query to analyze (if no query_id provided)"
                }
            },
            "required": []  # At least one should be provided
        },
        handler=lambda query_id=None, sql=None, user_context=None:
            mcp_client.analyze_query_performance(query_id, sql),
        examples=[
            "Why is my query slow?",
            "How can I optimize this query?",
            "Analyze performance of my last query",
            "Make this query faster"
        ],
        category="performance"
    ))
    
    # Category: Schema Evolution
    
    registry.register_tool(ToolDefinition(
        name="get_schema_changes",
        description=(
            "Track schema evolution and changes over time for datasets and tables. "
            "Use when user wants to know if schema has changed, see history of modifications, "
            "or understand when columns were added/removed/modified."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "GCP project ID"
                },
                "dataset_id": {
                    "type": "string",
                    "description": "Dataset ID to check for changes (optional - checks all if not provided)"
                },
                "table_id": {
                    "type": "string",
                    "description": "Table ID to check for changes (optional - checks all in dataset if not provided)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of changes to return",
                    "default": 10
                }
            },
            "required": ["project_id"]
        },
        handler=lambda project_id, dataset_id=None, table_id=None, limit=10, user_context=None:
            mcp_client.get_schema_changes(project_id, dataset_id, table_id, limit),
        examples=[
            "Has the schema changed?",
            "Show me schema history for the Users table",
            "What changed in the Analytics dataset?",
            "Did any columns get added to this table?"
        ],
        category="schema_evolution"
    ))
    
    # Category: Cache Management
    
    registry.register_tool(ToolDefinition(
        name="cache_management",
        description=(
            "Manage query result caching - clear cache, view cached queries, or refresh specific entries. "
            "Use when user wants to clear their cached data, see what's cached, or force fresh query results."
        ),
        parameters={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["list", "clear", "clear_all", "refresh"],
                    "description": "Cache operation: list (show cached), clear (remove one), clear_all (remove all), refresh (update one)"
                },
                "query_hash": {
                    "type": "string",
                    "description": "Specific query hash for clear/refresh operations (not needed for list/clear_all)"
                }
            },
            "required": ["operation"]
        },
        handler=lambda operation, query_hash=None, user_context=None:
            mcp_client.cache_management(operation, query_hash),
        examples=[
            "Clear my query cache",
            "Show me cached queries",
            "Refresh cached data",
            "Clear all my cached results"
        ],
        category="cache"
    ))
    
    logger.info(f"Tool registry created with {len(registry.tools)} tools")
    return registry
```

### Step 2: Create Smart Agent

**File**: `src/mcp_bigquery/agent/smart_agent.py`

```python
"""Smart agent with LLM-driven tool orchestration."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..llm.providers import LLMProvider, Message
from ..core.auth import UserContext
from ..core.supabase_client import SupabaseKnowledgeBase
from .tool_registry import ToolRegistry
from .models import AgentResponse

logger = logging.getLogger(__name__)


class SmartAgent:
    """Intelligent agent that uses LLM to select and orchestrate tools.
    
    This agent:
    - Receives tool descriptions and lets LLM choose which to use
    - Supports multi-step reasoning (calling multiple tools in sequence)
    - Handles tool errors gracefully
    - Provides clear explanations of its reasoning
    - Tracks token usage and performance
    
    Example:
        agent = SmartAgent(
            llm_provider=openai_provider,
            tool_registry=registry,
            kb=supabase_kb,
            project_id="my-project",
            max_iterations=5
        )
        
        response = await agent.process_question(
            question="Show me the schema of the largest table in Analytics",
            user_context=user_ctx,
            session_id="session-123"
        )
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        kb: SupabaseKnowledgeBase,
        project_id: str,
        max_iterations: int = 5,
        enable_reasoning_traces: bool = True
    ):
        """Initialize the smart agent.
        
        Args:
            llm_provider: LLM provider for reasoning and responses
            tool_registry: Registry of available tools
            kb: Supabase knowledge base for persistence
            project_id: GCP project ID
            max_iterations: Maximum tool calling iterations
            enable_reasoning_traces: Whether to include reasoning traces in responses
        """
        self.llm = llm_provider
        self.tools = tool_registry
        self.kb = kb
        self.project_id = project_id
        self.max_iterations = max_iterations
        self.enable_reasoning_traces = enable_reasoning_traces
        
        logger.info(
            f"SmartAgent initialized with {len(self.tools.list_tools())} tools, "
            f"max_iterations={max_iterations}"
        )
    
    async def process_question(
        self,
        question: str,
        user_context: UserContext,
        session_id: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> AgentResponse:
        """Process a user question with intelligent tool orchestration.
        
        Args:
            question: User's question
            user_context: User context with permissions
            session_id: Chat session ID
            conversation_history: Recent conversation turns
            
        Returns:
            Agent response with answer and metadata
        """
        start_time = datetime.now(timezone.utc)
        reasoning_trace = []
        
        try:
            # Build conversation messages
            messages = self._build_messages(
                question=question,
                conversation_history=conversation_history or [],
                user_context=user_context
            )
            
            # Get tool definitions for LLM
            tools = self.tools.get_openai_functions()  # TODO: Support anthropic
            
            # Multi-step reasoning loop
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1
                logger.info(f"Reasoning iteration {iteration}/{self.max_iterations}")
                
                # Let LLM decide next action
                response = await self.llm.generate(
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"  # Let LLM decide
                )
                
                # Check if LLM wants to call tools
                if response.tool_calls:
                    logger.info(f"LLM requested {len(response.tool_calls)} tool call(s)")
                    
                    # Add reasoning trace
                    reasoning_trace.append({
                        "iteration": iteration,
                        "action": "tool_calls",
                        "tools": [tc.function.name for tc in response.tool_calls]
                    })
                    
                    # Execute all tool calls
                    tool_results = await self._execute_tool_calls(
                        response.tool_calls,
                        user_context
                    )
                    
                    # Add tool calls and results to conversation
                    messages.append(Message(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=response.tool_calls
                    ))
                    
                    # Add tool results
                    for result in tool_results:
                        messages.append(Message(
                            role="tool",
                            content=result["content"],
                            tool_call_id=result["tool_call_id"],
                            name=result["name"]
                        ))
                    
                    # Continue loop - LLM will process results and decide next step
                    
                else:
                    # LLM provided final answer
                    logger.info("LLM provided final answer")
                    reasoning_trace.append({
                        "iteration": iteration,
                        "action": "final_answer"
                    })
                    
                    return self._create_success_response(
                        answer=response.content,
                        reasoning_trace=reasoning_trace,
                        messages=messages,
                        start_time=start_time
                    )
            
            # Max iterations reached without final answer
            logger.warning(f"Max iterations ({self.max_iterations}) reached")
            return self._create_max_iterations_response(
                reasoning_trace=reasoning_trace,
                messages=messages
            )
            
        except Exception as e:
            logger.error(f"Error processing question: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                error=f"Failed to process question: {str(e)}",
                error_type="unknown",
                metadata={
                    "reasoning_trace": reasoning_trace if self.enable_reasoning_traces else None
                }
            )
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[Any],
        user_context: UserContext
    ) -> List[Dict[str, Any]]:
        """Execute tool calls and return results.
        
        Args:
            tool_calls: List of tool calls from LLM
            user_context: User context for authorization
            
        Returns:
            List of tool results in LLM format
        """
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            
            try:
                # Parse arguments
                arguments = json.loads(tool_call.function.arguments)
                logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                
                # Execute tool
                result = await self.tools.execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    user_context=user_context
                )
                
                # Format result for LLM
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps({
                        "success": True,
                        "data": result
                    }, default=str)
                })
                
                logger.info(f"Tool {tool_name} executed successfully")
                
            except Exception as e:
                # Return error to LLM so it can handle it
                logger.error(f"Tool {tool_name} failed: {e}")
                
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps({
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "suggestion": self._get_error_suggestion(e)
                    })
                })
        
        return results
    
    def _build_messages(
        self,
        question: str,
        conversation_history: List[Dict[str, Any]],
        user_context: UserContext
    ) -> List[Message]:
        """Build conversation messages for LLM.
        
        Args:
            question: User's question
            conversation_history: Recent conversation turns
            user_context: User context with permissions
            
        Returns:
            List of messages including system prompt and history
        """
        messages = []
        
        # System prompt with tool descriptions
        system_prompt = self._build_system_prompt(user_context)
        messages.append(Message(role="system", content=system_prompt))
        
        # Add recent conversation history
        for msg in conversation_history[-10:]:  # Last 10 messages
            messages.append(Message(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))
        
        # Add current question
        messages.append(Message(role="user", content=question))
        
        return messages
    
    def _build_system_prompt(self, user_context: UserContext) -> str:
        """Build system prompt with tool descriptions and user permissions.
        
        Args:
            user_context: User context with permissions
            
        Returns:
            System prompt string
        """
        # Format user permissions
        if not user_context.allowed_datasets or "*" in user_context.allowed_datasets:
            permissions_text = f"All datasets in project `{self.project_id}`"
        else:
            permissions_list = []
            for dataset in sorted(user_context.allowed_datasets):
                tables = user_context.allowed_tables.get(dataset, set())
                if "*" in tables or not tables:
                    permissions_list.append(f"  - `{self.project_id}.{dataset}.*` (all tables)")
                else:
                    for table in sorted(tables):
                        permissions_list.append(f"  - `{self.project_id}.{dataset}.{table}`")
            permissions_text = "\n".join(permissions_list)
        
        # Get tool summaries
        tool_summaries = []
        for tool_name in self.tools.list_tools():
            tool = self.tools.get_tool(tool_name)
            if tool:
                tool_summaries.append(f"- {tool.name}: {tool.description}")
        
        tools_text = "\n".join(tool_summaries)
        
        prompt = f"""You are an intelligent BigQuery assistant with access to multiple tools.

**Your Role:**
Help users explore and analyze their BigQuery data by intelligently selecting and using the right tools.

**Available Tools:**
{tools_text}

**User's Data Access:**
The user has access to:
{permissions_text}

**How to Use Tools:**
1. Understand what the user is asking for
2. Determine which tool(s) you need - you can call multiple tools in sequence
3. Call tools with appropriate parameters
4. If a tool fails, read the error message and try an alternative approach
5. Synthesize tool results into a clear, helpful answer

**Multi-Step Reasoning Examples:**

Example 1: "Show me the schema of the largest table in Analytics"
Step 1: Call get_tables(dataset_id="Analytics") to list all tables
Step 2: Identify the largest table from the results
Step 3: Call get_table_schema(dataset_id="Analytics", table_id="<largest_table>")
Step 4: Present the schema clearly to the user

Example 2: "What interesting queries can I run on Sales data?"
Step 1: Call get_tables(dataset_id="Sales") to see available tables
Step 2: Call get_query_suggestions(tables_mentioned=[...], query_context="interesting queries")
Step 3: Present the suggestions with explanations

**CRITICAL Rules:**
1. NEVER guess or hallucinate table names - always call get_tables first to verify
2. NEVER generate SQL without first checking that tables exist
3. If a tool returns an error, explain it clearly to the user
4. Always provide context and reasoning for your decisions
5. Keep responses clear, concise, and actionable

**Response Style:**
- Be helpful and friendly
- Explain your reasoning when using multiple tools
- Provide actionable next steps
- If data is empty or missing, explain why and suggest alternatives
"""
        
        return prompt
    
    def _get_error_suggestion(self, error: Exception) -> str:
        """Get helpful suggestion based on error type.
        
        Args:
            error: Exception that occurred
            
        Returns:
            Suggestion for how to handle the error
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        if "not found" in error_msg.lower():
            return "The requested resource doesn't exist. Try listing available resources first."
        elif "permission" in error_msg.lower() or "denied" in error_msg.lower():
            return "You don't have permission to access this resource. Check user permissions."
        elif "invalid" in error_msg.lower():
            return "The request parameters are invalid. Check the tool's parameter requirements."
        else:
            return "Please try a different approach or ask the user for clarification."
    
    def _create_success_response(
        self,
        answer: str,
        reasoning_trace: List[Dict],
        messages: List[Message],
        start_time: datetime
    ) -> AgentResponse:
        """Create a successful agent response.
        
        Args:
            answer: Final answer from LLM
            reasoning_trace: List of reasoning steps
            messages: Full conversation messages
            start_time: Request start time
            
        Returns:
            AgentResponse
        """
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return AgentResponse(
            success=True,
            answer=answer,
            metadata={
                "reasoning_trace": reasoning_trace if self.enable_reasoning_traces else None,
                "iterations": len(reasoning_trace),
                "processing_time_ms": int(processing_time),
                "provider": self.llm.provider_name,
                "model": self.llm.config.model,
                "message_count": len(messages)
            }
        )
    
    def _create_max_iterations_response(
        self,
        reasoning_trace: List[Dict],
        messages: List[Message]
    ) -> AgentResponse:
        """Create response when max iterations reached.
        
        Args:
            reasoning_trace: List of reasoning steps
            messages: Full conversation messages
            
        Returns:
            AgentResponse with error
        """
        return AgentResponse(
            success=False,
            error=(
                f"I reached the maximum number of reasoning steps ({self.max_iterations}) "
                "without completing your request. This might be because your question requires "
                "more complex analysis than I can currently handle. Please try breaking it down "
                "into smaller questions."
            ),
            error_type="max_iterations",
            metadata={
                "reasoning_trace": reasoning_trace if self.enable_reasoning_traces else None,
                "iterations": len(reasoning_trace),
                "message_count": len(messages)
            }
        )
```

### Step 3: Create Agent API Route

**File**: `src/mcp_bigquery/routes/agent.py`

```python
"""Agent API routes for intelligent query processing."""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from ..core.auth import UserContext
from ..agent.smart_agent import SmartAgent
from ..agent.models import AgentResponse


class AgentQueryRequest(BaseModel):
    """Request model for agent queries."""
    question: str = Field(..., description="User's question or query", min_length=1)
    session_id: str = Field(..., description="Chat session ID for context")
    include_conversation_history: bool = Field(
        default=True,
        description="Whether to include conversation history in context"
    )
    max_history_turns: int = Field(
        default=10,
        description="Maximum conversation turns to include",
        ge=0,
        le=50
    )
    enable_reasoning_trace: bool = Field(
        default=False,
        description="Include detailed reasoning trace in response"
    )


def create_agent_router(
    smart_agent: SmartAgent,
    kb,
    auth_dependency
) -> APIRouter:
    """Create agent router with dependencies.
    
    Args:
        smart_agent: SmartAgent instance
        kb: SupabaseKnowledgeBase instance
        auth_dependency: Authentication dependency
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/chat", tags=["agent"])
    
    @router.post("/ask", response_model=AgentResponse)
    async def ask_agent(
        request: AgentQueryRequest = Body(...),
        user: UserContext = Depends(auth_dependency)
    ):
        """Ask the intelligent agent a question.
        
        The agent will:
        1. Understand your question using AI reasoning
        2. Automatically select the right tools to use
        3. Call multiple tools if needed (multi-step reasoning)
        4. Handle errors gracefully
        5. Provide a clear, comprehensive answer
        
        **Features:**
        - Intelligent tool selection (no need to specify which tool to use)
        - Multi-step reasoning (e.g., "show schema of largest table")
        - Context-aware (remembers conversation history)
        - Handles all 9 available tools automatically
        
        **Examples:**
        - "What datasets do I have access to?"
        - "Show me the schema of the largest table in Analytics"
        - "What interesting queries can I run on Sales data?"
        - "Has the Users table schema changed recently?"
        
        Args:
            request: Query request with question and options
            user: Authenticated user context
            
        Returns:
            Agent response with answer, reasoning trace, and metadata
            
        Raises:
            HTTPException: 400 for invalid request, 500 for processing errors
        """
        try:
            # Get conversation history if requested
            conversation_history = []
            if request.include_conversation_history:
                messages = await kb.get_chat_messages(
                    session_id=request.session_id,
                    user_id=user.user_id,
                    limit=request.max_history_turns * 2  # user+assistant pairs
                )
                conversation_history = messages
            
            # Process question with smart agent
            response = await smart_agent.process_question(
                question=request.question,
                user_context=user,
                session_id=request.session_id,
                conversation_history=conversation_history
            )
            
            # Save user question and agent response
            await kb.append_chat_message(
                session_id=request.session_id,
                user_id=user.user_id,
                role="user",
                content=request.question,
                metadata={"agent_query": True}
            )
            
            if response.success:
                await kb.append_chat_message(
                    session_id=request.session_id,
                    user_id=user.user_id,
                    role="assistant",
                    content=response.answer or "",
                    metadata={
                        "agent_response": True,
                        "iterations": response.metadata.get("iterations"),
                        "tools_used": response.metadata.get("tools_used", [])
                    }
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in ask_agent: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process agent query: {str(e)}"
            )
    
    return router
```

### Step 4: Wire Everything Together

**File**: `src/mcp_bigquery/main.py` (modifications)

Add to the main.py imports and setup:

```python
from .agent.tool_registry import create_tool_registry
from .agent.smart_agent import SmartAgent
from .routes.agent import create_agent_router

# After initializing mcp_client and knowledge_base:

# Create tool registry
tool_registry = create_tool_registry(mcp_client)
logger.info(f"Tool registry initialized with {len(tool_registry.list_tools())} tools")

# Create smart agent
smart_agent = SmartAgent(
    llm_provider=llm_provider,  # Initialize based on env
    tool_registry=tool_registry,
    kb=knowledge_base,
    project_id=config.project_id,
    max_iterations=5,
    enable_reasoning_traces=True
)
logger.info("Smart agent initialized")

# Create agent router
agent_router = create_agent_router(
    smart_agent=smart_agent,
    kb=knowledge_base,
    auth_dependency=auth_dependency
)

# Include in FastAPI app
fastapi_app.include_router(agent_router)
```

### Step 5: Test the Implementation

**Test File**: `tests/agent/test_smart_agent.py`

```python
"""Tests for the smart agent."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from src.mcp_bigquery.agent.smart_agent import SmartAgent
from src.mcp_bigquery.agent.tool_registry import ToolRegistry, ToolDefinition
from src.mcp_bigquery.core.auth import UserContext


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.provider_name = "openai"
    llm.config = Mock(model="gpt-4")
    return llm


@pytest.fixture
def mock_tool_registry():
    registry = ToolRegistry()
    
    # Add a simple test tool
    registry.register_tool(ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        handler=AsyncMock(return_value={"result": "success"}),
        examples=[]
    ))
    
    return registry


@pytest.fixture
def mock_kb():
    kb = AsyncMock()
    return kb


@pytest.fixture
def smart_agent(mock_llm, mock_tool_registry, mock_kb):
    return SmartAgent(
        llm_provider=mock_llm,
        tool_registry=mock_tool_registry,
        kb=mock_kb,
        project_id="test-project",
        max_iterations=3
    )


@pytest.mark.asyncio
async def test_process_question_simple(smart_agent, mock_llm):
    """Test simple question with direct answer (no tools)."""
    # Mock LLM response with no tool calls
    mock_response = Mock()
    mock_response.content = "This is the answer"
    mock_response.tool_calls = None
    mock_llm.generate.return_value = mock_response
    
    user_context = UserContext(
        user_id="test-user",
        allowed_datasets={"test_dataset"},
        allowed_tables={"test_dataset": {"test_table"}}
    )
    
    response = await smart_agent.process_question(
        question="What is 2+2?",
        user_context=user_context,
        session_id="test-session"
    )
    
    assert response.success is True
    assert response.answer == "This is the answer"
    assert mock_llm.generate.called


@pytest.mark.asyncio
async def test_process_question_with_tool_call(smart_agent, mock_llm, mock_tool_registry):
    """Test question that requires tool call."""
    # First response: LLM wants to call tool
    tool_call = Mock()
    tool_call.id = "call_123"
    tool_call.function.name = "test_tool"
    tool_call.function.arguments = "{}"
    
    first_response = Mock()
    first_response.content = ""
    first_response.tool_calls = [tool_call]
    
    # Second response: LLM provides final answer after tool result
    second_response = Mock()
    second_response.content = "Based on the tool result, the answer is X"
    second_response.tool_calls = None
    
    mock_llm.generate.side_effect = [first_response, second_response]
    
    user_context = UserContext(
        user_id="test-user",
        allowed_datasets=set(),
        allowed_tables={}
    )
    
    response = await smart_agent.process_question(
        question="Call the test tool",
        user_context=user_context,
        session_id="test-session"
    )
    
    assert response.success is True
    assert "answer is X" in response.answer
    assert mock_llm.generate.call_count == 2


@pytest.mark.asyncio
async def test_max_iterations_reached(smart_agent, mock_llm):
    """Test that max iterations limit is enforced."""
    # Mock LLM to always request more tool calls
    tool_call = Mock()
    tool_call.id = "call_123"
    tool_call.function.name = "test_tool"
    tool_call.function.arguments = "{}"
    
    mock_response = Mock()
    mock_response.content = ""
    mock_response.tool_calls = [tool_call]
    
    mock_llm.generate.return_value = mock_response
    
    user_context = UserContext(
        user_id="test-user",
        allowed_datasets=set(),
        allowed_tables={}
    )
    
    response = await smart_agent.process_question(
        question="Keep calling tools",
        user_context=user_context,
        session_id="test-session"
    )
    
    assert response.success is False
    assert "maximum number of reasoning steps" in response.error
    assert response.error_type == "max_iterations"
```

---

## Testing Strategy

### Manual Testing Checklist

1. **Basic Questions**:
   - [ ] "What datasets do I have?" → Should call get_datasets
   - [ ] "Show tables in Analytics" → Should call get_tables
   - [ ] "Describe the Sales table" → Should call get_table_schema

2. **Multi-Step Questions**:
   - [ ] "Show me the schema of the largest table in Analytics" → get_tables → get_table_schema
   - [ ] "What queries can I run on the Sales data?" → get_tables → get_query_suggestions

3. **Data Questions**:
   - [ ] "Show me top 10 rows from Sales.Orders" → execute_bigquery_sql
   - [ ] "What's the total revenue?" → execute_bigquery_sql

4. **Error Handling**:
   - [ ] Ask about non-existent table → Should explain table doesn't exist
   - [ ] Ask about unauthorized data → Should explain permission denied

5. **Advanced Tools**:
   - [ ] "Has the schema changed?" → get_schema_changes
   - [ ] "Why is my query slow?" → analyze_query_performance
   - [ ] "Clear my cache" → cache_management

### API Testing

```bash
# Create a session
curl -X POST http://localhost:8000/chat/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}'

# Ask agent a question
curl -X POST http://localhost:8000/chat/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What datasets do I have?",
    "session_id": "<session-id>",
    "enable_reasoning_trace": true
  }'

# Multi-step question
curl -X POST http://localhost:8000/chat/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the schema of the largest table in Analytics",
    "session_id": "<session-id>",
    "enable_reasoning_trace": true
  }'
```

---

## Deployment Checklist

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] API documentation updated
- [ ] Environment variables configured (LLM API keys)
- [ ] Rate limiting configured
- [ ] Monitoring/logging in place
- [ ] User documentation written
- [ ] Feature flag for gradual rollout
- [ ] Backup plan if issues arise

---

## Troubleshooting

### Issue: LLM keeps calling tools in loops
**Solution**: Adjust system prompt to be more explicit about when to stop. Lower max_iterations.

### Issue: Agent doesn't use certain tools
**Solution**: Check tool descriptions - make them more explicit about when to use each tool.

### Issue: Tool execution fails
**Solution**: Check tool handler implementation, verify MCP client methods work correctly.

### Issue: High latency
**Solution**: Enable parallel tool execution, cache tool results, use faster LLM model.

---

## Next Steps

After basic implementation:
1. Add streaming support for long-running queries
2. Add tool result caching
3. Add parallel tool execution
4. Add conversation context summarization
5. Add user feedback collection
6. Add A/B testing for prompt variations
7. Add analytics dashboard for tool usage
