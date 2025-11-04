"""Conversational agent for BigQuery insights using LLMs and MCP client."""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple
from pydantic import ValidationError

from ..llm.providers import (
    LLMProvider,
    Message,
    GenerationResponse,
    LLMGenerationError,
)
from ..client import MCPClient
from ..client.exceptions import AuthorizationError, AuthenticationError
from ..core.supabase_client import SupabaseKnowledgeBase
from ..core.auth import UserContext
from .models import (
    AgentRequest,
    AgentResponse,
    SQLGenerationResult,
    ChartSuggestion,
    ConversationContext,
)
from .prompts import PromptBuilder
from .tools import ToolRegistry
from .tool_executor import ToolExecutor
from .mcp_client import MCPBigQueryClient

logger = logging.getLogger(__name__)


class InsightsAgent:
    """Conversational agent that orchestrates BigQuery insights generation.
    
    This agent:
    - Interprets natural language questions using LLMs
    - Generates SQL queries constrained to user permissions
    - Executes queries through MCP client
    - Summarizes results in business-friendly language
    - Suggests appropriate visualizations
    - Maintains conversation context
    
    Example:
        ```python
        agent = InsightsAgent(
            llm_provider=openai_provider,
            mcp_client=client,
            kb=supabase_kb,
            project_id="my-project"
        )
        
        request = AgentRequest(
            question="What are the top 5 products by revenue?",
            session_id="session-123",
            user_id="user-456",
            allowed_datasets={"sales"},
            allowed_tables={"sales": {"orders", "products"}}
        )
        
        response = await agent.process_question(request)
        print(response.answer)
        ```
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        mcp_client: MCPClient,
        kb: SupabaseKnowledgeBase,
        project_id: str,
        max_retries: int = 2,
        enable_caching: bool = True,
        enable_tool_selection: bool = True
    ):
        """Initialize the insights agent.
        
        Args:
            llm_provider: LLM provider instance (OpenAI, Anthropic, etc.)
            mcp_client: MCP client for BigQuery operations
            kb: Supabase knowledge base for persistence
            project_id: Google Cloud project ID
            max_retries: Maximum retries for failed operations
            enable_caching: Whether to cache LLM responses
            enable_tool_selection: Whether to use LLM-based tool selection (default: True)
        """
        self.llm = llm_provider
        self.mcp_client = mcp_client
        self.kb = kb
        self.project_id = project_id
        self.max_retries = max_retries
        self.enable_caching = enable_caching
        self.enable_tool_selection = enable_tool_selection
        self.prompt_builder = PromptBuilder()
        
        # Initialize tool selection infrastructure if enabled
        if self.enable_tool_selection and self.llm.supports_functions():
            # Create a wrapper MCP client from the agent's mcp_client
            # The agent's mcp_client is MCPClient, but we need MCPBigQueryClient for tools
            # Since they have the same interface, we'll use the mcp_client directly
            self.tool_registry = ToolRegistry(self.mcp_client)
            self.tool_executor = ToolExecutor(self.tool_registry)
            logger.info(f"Tool selection enabled with {len(self.tool_registry.get_all_tools())} tools")
        else:
            self.tool_registry = None
            self.tool_executor = None
            if self.enable_tool_selection:
                logger.warning(f"Tool selection requested but LLM provider {self.llm.provider_name} doesn't support functions")
    
    async def process_question(self, request: AgentRequest) -> AgentResponse:
        """Process a user question and return insights.
        
        Args:
            request: Agent request with question and context
            
        Returns:
            Agent response with answer, SQL, results, and suggestions
        """
        try:
            # Step 1: Retrieve conversation context
            context = await self._get_conversation_context(
                session_id=request.session_id,
                user_id=request.user_id,
                allowed_datasets=request.allowed_datasets,
                allowed_tables=request.allowed_tables,
                context_turns=request.context_turns
            )
            
            # Save user question
            await self._save_message(
                session_id=request.session_id,
                user_id=request.user_id,
                role="user",
                content=request.question,
                metadata={"request_metadata": request.metadata}
            )
            
            # Use tool selection if enabled
            if self.enable_tool_selection and self.tool_registry:
                return await self._process_with_tool_selection(request, context)
            
            # Fallback to pattern-based routing
            # Step 2: Check if this is a metadata question (datasets/tables/schema)
            metadata_type = self._is_metadata_question(request.question)
            if metadata_type:
                logger.info(f"Routing to metadata handler: {metadata_type}")
                
                if metadata_type == "datasets":
                    response = await self._handle_datasets_question()
                elif metadata_type == "tables":
                    response = await self._handle_tables_question(request.question, context)
                elif metadata_type == "schema":
                    response = await self._handle_schema_question(request.question, context)
                else:
                    response = AgentResponse(
                        success=False,
                        error="Unknown metadata question type",
                        error_type="unknown"
                    )
                
                # Save assistant response
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=response.answer or response.error or "",
                    metadata=response.metadata or {}
                )
                
                return response
            
            # Step 3: Generate SQL query (for data questions)
            sql_result = await self._generate_sql(
                question=request.question,
                context=context
            )
            
            if not sql_result.sql:
                # Need clarification
                error_response = AgentResponse(
                    success=False,
                    error=sql_result.explanation,
                    error_type="validation"
                )
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=sql_result.explanation,
                    metadata={"error": True, "error_type": "validation"}
                )
                return error_response
            
            # Step 4: Validate SQL before execution
            is_valid, validation_error = self._is_valid_sql(sql_result.sql)
            if not is_valid:
                error_msg = f"Invalid SQL query: {validation_error}"
                logger.warning(f"SQL validation failed: {validation_error}")
                error_response = AgentResponse(
                    success=False,
                    sql_query=sql_result.sql,
                    sql_explanation=sql_result.explanation,
                    error=error_msg,
                    error_type="validation"
                )
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=error_msg,
                    metadata={
                        "error": True,
                        "error_type": "validation",
                        "sql": sql_result.sql,
                        "validation_error": validation_error
                    }
                )
                return error_response
            
            # Step 5: Execute query
            try:
                query_results = await self._execute_query(sql_result.sql)
            except (AuthorizationError, AuthenticationError) as e:
                error_msg = f"Permission denied: {str(e)}"
                error_response = AgentResponse(
                    success=False,
                    sql_query=sql_result.sql,
                    sql_explanation=sql_result.explanation,
                    error=error_msg,
                    error_type="authorization"
                )
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=error_msg,
                    metadata={
                        "error": True,
                        "error_type": "authorization",
                        "sql": sql_result.sql
                    }
                )
                return error_response
            except Exception as e:
                error_msg = f"Query execution failed: {str(e)}"
                logger.error(f"Query execution error: {e}", exc_info=True)
                error_response = AgentResponse(
                    success=False,
                    sql_query=sql_result.sql,
                    sql_explanation=sql_result.explanation,
                    error=error_msg,
                    error_type="execution"
                )
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=error_msg,
                    metadata={
                        "error": True,
                        "error_type": "execution",
                        "sql": sql_result.sql,
                        "error_details": str(e)
                    }
                )
                return error_response
            
            # Step 6: Generate summary
            summary = await self._generate_summary(
                question=request.question,
                sql_query=sql_result.sql,
                results=query_results
            )
            
            # Step 7: Generate chart suggestions
            chart_suggestions = await self._generate_chart_suggestions(
                results=query_results
            )
            
            # Step 8: Build response
            response = AgentResponse(
                success=True,
                answer=summary,
                sql_query=sql_result.sql,
                sql_explanation=sql_result.explanation,
                results=query_results,
                chart_suggestions=chart_suggestions,
                metadata={
                    "tables_used": sql_result.tables_used,
                    "complexity": sql_result.estimated_complexity,
                    "warnings": sql_result.warnings,
                    "llm_provider": self.llm.provider_name,
                    "llm_model": self.llm.config.model
                }
            )
            
            # Save assistant response
            await self._save_message(
                session_id=request.session_id,
                user_id=request.user_id,
                role="assistant",
                content=summary,
                metadata={
                    "sql": sql_result.sql,
                    "sql_explanation": sql_result.explanation,
                    "row_count": len(query_results.get("rows", [])),
                    "chart_suggestions": len(chart_suggestions),
                    "tables_used": sql_result.tables_used
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Agent processing error: {e}", exc_info=True)
            error_response = AgentResponse(
                success=False,
                error=f"An unexpected error occurred: {str(e)}",
                error_type="unknown"
            )
            
            # Try to save error message
            try:
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=error_response.error,
                    metadata={"error": True, "error_type": "unknown"}
                )
            except Exception as save_error:
                logger.error(f"Failed to save error message: {save_error}")
            
            return error_response
    
    async def _process_with_tool_selection(
        self,
        request: AgentRequest,
        context: ConversationContext
    ) -> AgentResponse:
        """Process question using LLM-based tool selection.
        
        Args:
            request: Agent request with question and context
            context: Conversation context
            
        Returns:
            Agent response with answer and results
        """
        try:
            logger.info(f"Processing with tool selection: {request.question}")
            
            # Build system prompt for tool-based interaction
            system_prompt = self._build_tool_selection_system_prompt(context)
            
            # Build messages
            messages = [Message(role="system", content=system_prompt)]
            
            # Add conversation history
            for msg in context.messages[-10:]:  # Last 5 turns (10 messages)
                messages.append(Message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", "")
                ))
            
            # Add current question
            messages.append(Message(role="user", content=request.question))
            
            # Get tools for the LLM provider
            tools = self.tool_registry.get_tools_for_llm(self.llm.provider_name)
            
            logger.info(f"Calling LLM with {len(tools)} tools available")
            
            # Call LLM with tools
            response = await self.llm.generate(messages=messages, tools=tools)
            
            # Check if LLM wants to call tools
            if response.has_tool_calls():
                logger.info(f"LLM requested {len(response.tool_calls)} tool call(s)")
                
                # Execute tool calls
                tool_results = await self.tool_executor.execute_tool_calls(response.tool_calls)
                
                # Format tool results for the LLM
                tool_result_messages = self._format_tool_results_for_llm(
                    tool_results,
                    response
                )
                
                # Add assistant message with tool calls
                if response.content:
                    messages.append(Message(role="assistant", content=response.content))
                
                # Add tool results
                messages.extend(tool_result_messages)
                
                # Get final response from LLM
                logger.info("Sending tool results back to LLM for final response")
                final_response = await self.llm.generate(messages=messages)
                answer = final_response.content or "I processed your request."
                
                # Build response based on tool results
                agent_response = self._build_response_from_tool_results(
                    answer=answer,
                    tool_results=tool_results,
                    request=request
                )
                
            else:
                # LLM provided direct answer without tools
                logger.info("LLM provided direct answer without tool calls")
                answer = response.content or "I don't have enough information to answer that."
                
                agent_response = AgentResponse(
                    success=True,
                    answer=answer,
                    metadata={
                        "llm_provider": self.llm.provider_name,
                        "llm_model": self.llm.config.model,
                        "tool_calls": 0
                    }
                )
            
            # Save assistant response
            await self._save_message(
                session_id=request.session_id,
                user_id=request.user_id,
                role="assistant",
                content=agent_response.answer or agent_response.error or "",
                metadata=agent_response.metadata or {}
            )
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Tool selection processing error: {e}", exc_info=True)
            error_response = AgentResponse(
                success=False,
                error=f"An error occurred: {str(e)}",
                error_type="unknown"
            )
            
            # Try to save error message
            try:
                await self._save_message(
                    session_id=request.session_id,
                    user_id=request.user_id,
                    role="assistant",
                    content=error_response.error,
                    metadata={"error": True, "error_type": "unknown"}
                )
            except Exception as save_error:
                logger.error(f"Failed to save error message: {save_error}")
            
            return error_response
    
    def _build_tool_selection_system_prompt(self, context: ConversationContext) -> str:
        """Build system prompt for tool-based interaction.
        
        Args:
            context: Conversation context
            
        Returns:
            System prompt describing tools and how to use them
        """
        datasets_str = ", ".join(sorted(context.allowed_datasets)) if context.allowed_datasets and "*" not in context.allowed_datasets else "all datasets"
        
        return f"""You are a helpful BigQuery assistant. You help users explore and query their BigQuery data.

You have access to these tools to interact with BigQuery:

1. **list_datasets()** - List all datasets the user has access to
   - Use when: User asks about available datasets or what data they have
   - Examples: "what datasets do I have?", "show me my datasets"

2. **list_tables(dataset_id)** - List all tables in a specific dataset
   - Use when: User asks about tables in a dataset
   - Examples: "what tables are in Analytics?", "show tables in dataset X"

3. **get_table_schema(dataset_id, table_id)** - Get schema (columns and types) for a table
   - Use when: User asks about table structure, columns, or wants to understand the data
   - Examples: "describe the Sales table", "what columns does X have?", "show me the schema"

4. **execute_sql(sql)** - Execute a SQL query to retrieve actual data
   - Use when: User wants to see data, analyze values, or run queries
   - IMPORTANT: Always verify table names using list_tables first before writing SQL
   - Examples: "show me top 10 rows", "what's the total revenue?", "query the data"

DECISION LOGIC:
- For questions about datasets → use list_datasets
- For questions about tables in a dataset → use list_tables (ask for dataset if not specified)
- For questions about table structure/columns → use get_table_schema
- For questions requesting actual data → first verify tables exist with list_tables, then generate SQL and use execute_sql

IMPORTANT RULES:
- NEVER guess or hallucinate table names - always call list_tables first
- NEVER guess column names - always call get_table_schema first
- Always verify resources exist before generating SQL queries
- Provide clear, friendly explanations to users
- If you need more information (like a dataset or table name), ask the user

User has access to: {datasets_str}
Project ID: {self.project_id}

Be helpful, accurate, and explain your reasoning when appropriate."""
    
    def _format_tool_results_for_llm(
        self,
        tool_results: List[Dict[str, Any]],
        llm_response: GenerationResponse
    ) -> List[Message]:
        """Format tool results as messages for the LLM.
        
        Args:
            tool_results: Results from tool execution
            llm_response: Original LLM response with tool calls
            
        Returns:
            List of messages representing tool results
        """
        messages = []
        
        for result in tool_results:
            # Format the result content
            if result["success"]:
                # Convert result to readable format
                result_data = result["result"]
                
                # Handle different result types
                if isinstance(result_data, list):
                    if result["tool_name"] == "list_datasets":
                        # Format datasets
                        datasets = [d.dataset_id if hasattr(d, 'dataset_id') else str(d) for d in result_data]
                        content = f"Found {len(datasets)} dataset(s): {', '.join(datasets)}"
                    elif result["tool_name"] == "list_tables":
                        # Format tables
                        tables = [t.table_id if hasattr(t, 'table_id') else str(t) for t in result_data]
                        content = f"Found {len(tables)} table(s): {', '.join(tables)}"
                    else:
                        content = json.dumps(result_data, default=str, indent=2)
                elif hasattr(result_data, 'schema_fields'):
                    # Table schema
                    content = f"Table schema with {len(result_data.schema_fields)} columns:\n{json.dumps(result_data.schema_fields, indent=2)}"
                elif hasattr(result_data, 'rows'):
                    # Query result
                    row_count = len(result_data.rows)
                    content = f"Query returned {row_count} row(s):\n{json.dumps(result_data.rows[:10], default=str, indent=2)}"
                    if row_count > 10:
                        content += f"\n... and {row_count - 10} more rows"
                else:
                    content = json.dumps(result_data, default=str, indent=2)
            else:
                content = f"Error: {result['error']}"
            
            # Add as tool message
            messages.append(Message(
                role="tool",
                content=content
            ))
        
        return messages
    
    def _build_response_from_tool_results(
        self,
        answer: str,
        tool_results: List[Dict[str, Any]],
        request: AgentRequest
    ) -> AgentResponse:
        """Build agent response from tool execution results.
        
        Args:
            answer: Final answer from LLM
            tool_results: Results from tool execution
            request: Original request
            
        Returns:
            Agent response
        """
        # Check if any tool was execute_sql
        sql_result = None
        sql_query = None
        query_results = None
        
        for result in tool_results:
            if result["tool_name"] == "execute_sql" and result["success"]:
                # The result is a QueryResult object, not a dict
                result_obj = result["result"]
                
                # Extract SQL from the tool call arguments (not from result)
                # We need to get it from the original tool call
                sql_query = None  # Will be populated from tool call args if available
                
                # Convert QueryResult to dict format for response
                if hasattr(result_obj, 'rows'):
                    query_results = {
                        "rows": result_obj.rows,
                        "statistics": result_obj.statistics if hasattr(result_obj, 'statistics') else None,
                        "cached": result_obj.cached if hasattr(result_obj, 'cached') else False
                    }
                else:
                    query_results = result_obj
                    
                sql_result = result
                break
        
        # Build response
        metadata = {
            "llm_provider": self.llm.provider_name,
            "llm_model": self.llm.config.model,
            "tool_calls": len(tool_results),
            "tools_used": [r["tool_name"] for r in tool_results]
        }
        
        if sql_result:
            # Data query was executed
            return AgentResponse(
                success=True,
                answer=answer,
                sql_query=sql_query,
                results=query_results,
                metadata=metadata
            )
        else:
            # Metadata query (datasets/tables/schema)
            return AgentResponse(
                success=True,
                answer=answer,
                metadata=metadata
            )
    
    async def _get_conversation_context(
        self,
        session_id: str,
        user_id: str,
        allowed_datasets: Set[str],
        allowed_tables: Dict[str, Set[str]],
        context_turns: int = 5
    ) -> ConversationContext:
        """Retrieve conversation context from knowledge base.
        
        Args:
            session_id: Chat session ID
            user_id: User ID
            allowed_datasets: User's allowed datasets
            allowed_tables: User's allowed tables per dataset
            context_turns: Number of recent turns to retrieve
            
        Returns:
            Conversation context with history
        """
        messages = await self.kb.get_chat_messages(
            session_id=session_id,
            user_id=user_id,
            limit=context_turns * 2  # Multiply by 2 for user+assistant pairs
        )
        
        return ConversationContext(
            session_id=session_id,
            user_id=user_id,
            messages=messages,
            allowed_datasets=allowed_datasets,
            allowed_tables=allowed_tables
        )
    
    async def _generate_sql(
        self,
        question: str,
        context: ConversationContext
    ) -> SQLGenerationResult:
        """Generate SQL query using LLM.
        
        Args:
            question: User's question
            context: Conversation context
            
        Returns:
            SQL generation result with query and metadata
        """
        try:
            # Extract potential table references from the question
            mentioned_tables = self._extract_table_references_from_question(question)
            
            # Build system prompt
            system_prompt = self.prompt_builder.build_system_prompt(
                allowed_datasets=context.allowed_datasets,
                allowed_tables=context.allowed_tables,
                project_id=self.project_id
            )
            
            # Get relevant schema information (prioritize mentioned tables)
            schema_info = await self._get_relevant_schemas(
                context.allowed_datasets,
                mentioned_tables=mentioned_tables
            )
            
            # Format conversation history
            conversation_history = self.prompt_builder.format_conversation_history(
                messages=context.messages
            )
            
            # Build SQL generation prompt
            user_prompt = self.prompt_builder.build_sql_generation_prompt(
                question=question,
                schema_info=schema_info,
                conversation_history=conversation_history
            )
            
            # Check cache if enabled
            if self.enable_caching:
                cached = await self.kb.get_cached_llm_response(
                    prompt=user_prompt,
                    provider=self.llm.provider_name,
                    model=self.llm.config.model
                )
                if cached:
                    logger.info("Using cached SQL generation")
                    return self._parse_sql_generation(cached["response"])
            
            # Generate with LLM
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt)
            ]
            
            response = await self.llm.generate(messages, temperature=0.1)
            
            # Cache response if enabled
            if self.enable_caching and response.content:
                await self.kb.cache_llm_response(
                    prompt=user_prompt,
                    provider=self.llm.provider_name,
                    model=self.llm.config.model,
                    response=response.content,
                    metadata={
                        "finish_reason": response.finish_reason,
                        "usage": response.usage
                    }
                )
            
            sql_result = self._parse_sql_generation(response.content or "")
            
            # Validate table references in generated SQL
            if sql_result.sql:
                validation_result = await self._validate_sql_tables(
                    sql_result.sql,
                    context.allowed_datasets,
                    context.allowed_tables
                )
                
                if not validation_result["valid"]:
                    # Add warning about invalid table references
                    sql_result.warnings.append(validation_result["error"])
                    logger.warning(f"SQL validation warning: {validation_result['error']}")
            
            return sql_result
            
        except LLMGenerationError as e:
            logger.error(f"LLM generation error: {e}")
            return SQLGenerationResult(
                sql="",
                explanation=f"I encountered an error generating the SQL query. Please try rephrasing your question or providing more details.",
                warnings=[str(e)]
            )
        except Exception as e:
            logger.error(f"SQL generation error: {e}", exc_info=True)
            return SQLGenerationResult(
                sql="",
                explanation=f"An unexpected error occurred while processing your question. Please try again.",
                warnings=[str(e)]
            )
    
    def _parse_sql_generation(self, content: str) -> SQLGenerationResult:
        """Parse LLM response for SQL generation.
        
        Args:
            content: LLM response content
            
        Returns:
            Parsed SQL generation result
        """
        try:
            # Try to extract JSON from response
            content = content.strip()
            
            # Handle markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            return SQLGenerationResult(
                sql=data.get("sql", ""),
                explanation=data.get("explanation", ""),
                tables_used=data.get("tables_used", []),
                estimated_complexity=data.get("estimated_complexity", "medium"),
                warnings=data.get("warnings", [])
            )
        except json.JSONDecodeError:
            # Fallback: try to extract SQL from content
            logger.warning("Failed to parse JSON response, attempting SQL extraction")
            
            # Look for SQL code blocks
            if "```sql" in content:
                parts = content.split("```sql")
                if len(parts) > 1:
                    sql = parts[1].split("```")[0].strip()
                    explanation = parts[0].strip() if parts[0].strip() else "Generated SQL query"
                    return SQLGenerationResult(
                        sql=sql,
                        explanation=explanation,
                        warnings=["Could not parse structured response"]
                    )
            
            # No SQL found
            return SQLGenerationResult(
                sql="",
                explanation="I wasn't able to generate a SQL query. Could you provide more details about what data you're looking for?",
                warnings=["Failed to parse LLM response"]
            )
        except Exception as e:
            logger.error(f"Error parsing SQL generation: {e}")
            return SQLGenerationResult(
                sql="",
                explanation="An error occurred while processing the response.",
                warnings=[str(e)]
            )
    
    async def _execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query through MCP client.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Query results
            
        Raises:
            AuthorizationError: If user lacks permissions
            Exception: On query execution errors
        """
        result = await self.mcp_client.execute_sql(sql)
        return result
    
    async def _generate_summary(
        self,
        question: str,
        sql_query: str,
        results: Dict[str, Any]
    ) -> str:
        """Generate natural language summary of results.
        
        Args:
            question: Original user question
            sql_query: Executed SQL query
            results: Query results
            
        Returns:
            Natural language summary
        """
        try:
            rows = results.get("rows", [])
            schema = results.get("schema", [])
            row_count = len(rows)
            
            # Provide clear, explicit messaging for empty results
            if not rows:
                summary = "**Query Result:** ✅ The query executed successfully but returned 0 rows.\n\n"
                summary += "**What this means:**\n"
                summary += "- The query syntax is correct and the table exists\n"
                summary += "- However, no data matches your query criteria\n\n"
                summary += "**Possible reasons:**\n"
                summary += "1. The table is empty or has no data yet\n"
                summary += "2. Your filter conditions (WHERE clause) don't match any records\n"
                summary += "3. Date ranges or other criteria are too restrictive\n"
                summary += "4. There might be a join condition that eliminates all rows\n\n"
                summary += "**Next steps:**\n"
                summary += "- Try removing some filter conditions to see if data exists\n"
                summary += "- Ask me to 'describe table <name>' to see schema and row count\n"
                summary += "- Try a simpler query like 'SELECT * FROM table LIMIT 10'"
                return summary
            
            # Prepare results preview (first 5 rows)
            preview_rows = rows[:5]
            columns = [field["name"] for field in schema]
            
            results_preview = f"Columns: {', '.join(columns)}\n\n"
            results_preview += "Sample rows:\n"
            for i, row in enumerate(preview_rows, 1):
                row_str = ", ".join([f"{k}={v}" for k, v in row.items()])
                results_preview += f"{i}. {row_str}\n"
            
            if len(rows) > 5:
                results_preview += f"\n... and {len(rows) - 5} more rows"
            
            # Build summary prompt
            summary_prompt = self.prompt_builder.build_summary_prompt(
                question=question,
                sql_query=sql_query,
                results_preview=results_preview,
                row_count=row_count,
                columns=columns
            )
            
            # Check cache
            if self.enable_caching:
                cached = await self.kb.get_cached_llm_response(
                    prompt=summary_prompt,
                    provider=self.llm.provider_name,
                    model=self.llm.config.model
                )
                if cached:
                    logger.info("Using cached summary")
                    return cached["response"]
            
            # Generate with LLM
            messages = [Message(role="user", content=summary_prompt)]
            response = await self.llm.generate(messages, temperature=0.3)
            
            summary = response.content or "Here are the query results."
            
            # Add context about total result size
            if row_count > 5:
                summary += f"\n\n*Note: Showing {row_count} total rows. Analysis based on first 5 rows.*"
            
            # Cache response
            if self.enable_caching:
                await self.kb.cache_llm_response(
                    prompt=summary_prompt,
                    provider=self.llm.provider_name,
                    model=self.llm.config.model,
                    response=summary,
                    metadata={"usage": response.usage}
                )
            
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation error: {e}", exc_info=True)
            row_count = len(results.get('rows', []))
            if row_count == 0:
                return "**Query Result:** ✅ The query executed successfully but returned 0 rows. No data matches your query criteria."
            else:
                return f"The query returned {row_count} rows. Review the data below for details."
    
    async def _generate_chart_suggestions(
        self,
        results: Dict[str, Any]
    ) -> List[ChartSuggestion]:
        """Generate chart suggestions based on results.
        
        Args:
            results: Query results
            
        Returns:
            List of chart suggestions
        """
        try:
            rows = results.get("rows", [])
            schema = results.get("schema", [])
            
            if not rows or len(rows) < 2:
                # Not enough data for meaningful charts
                return [ChartSuggestion(
                    chart_type="table",
                    title="Data Table",
                    description="Display results in a table format",
                    config={}
                )]
            
            # Analyze schema
            numeric_cols = []
            categorical_cols = []
            datetime_cols = []
            
            for field in schema:
                field_type = field.get("type", "").upper()
                field_name = field.get("name", "")
                
                if field_type in ("INTEGER", "FLOAT", "NUMERIC", "BIGNUMERIC"):
                    numeric_cols.append(field_name)
                elif field_type in ("DATE", "DATETIME", "TIMESTAMP", "TIME"):
                    datetime_cols.append(field_name)
                else:
                    categorical_cols.append(field_name)
            
            # Prepare sample data
            sample_data = json.dumps(rows[:3], indent=2)
            result_schema = json.dumps(schema, indent=2)
            
            # Build chart suggestion prompt
            chart_prompt = self.prompt_builder.build_chart_suggestion_prompt(
                result_schema=result_schema,
                sample_data=sample_data,
                row_count=len(rows),
                numeric_columns=numeric_cols,
                categorical_columns=categorical_cols,
                datetime_columns=datetime_cols
            )
            
            # Generate with LLM
            messages = [Message(role="user", content=chart_prompt)]
            response = await self.llm.generate(messages, temperature=0.2)
            
            # Parse response
            suggestions = self._parse_chart_suggestions(response.content or "[]")
            
            # Fallback suggestions if parsing fails
            if not suggestions:
                suggestions = self._generate_fallback_suggestions(
                    numeric_cols, categorical_cols, datetime_cols
                )
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Chart suggestion error: {e}", exc_info=True)
            return [ChartSuggestion(
                chart_type="table",
                title="Data Table",
                description="Display results in a table format",
                config={}
            )]
    
    def _parse_chart_suggestions(self, content: str) -> List[ChartSuggestion]:
        """Parse LLM response for chart suggestions.
        
        Args:
            content: LLM response content
            
        Returns:
            List of chart suggestions
        """
        try:
            content = content.strip()
            
            # Handle markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            suggestions = []
            for item in data:
                try:
                    suggestion = ChartSuggestion(**item)
                    suggestions.append(suggestion)
                except ValidationError as e:
                    logger.warning(f"Invalid chart suggestion: {e}")
                    continue
            
            return suggestions
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse chart suggestions JSON")
            return []
        except Exception as e:
            logger.error(f"Error parsing chart suggestions: {e}")
            return []
    
    def _generate_fallback_suggestions(
        self,
        numeric_cols: List[str],
        categorical_cols: List[str],
        datetime_cols: List[str]
    ) -> List[ChartSuggestion]:
        """Generate fallback chart suggestions based on column types.
        
        Args:
            numeric_cols: Numeric column names
            categorical_cols: Categorical column names
            datetime_cols: Datetime column names
            
        Returns:
            List of chart suggestions
        """
        suggestions = []
        
        # Always suggest table view
        suggestions.append(ChartSuggestion(
            chart_type="table",
            title="Data Table",
            description="Display all results in a table format",
            config={}
        ))
        
        # Time series if datetime + numeric
        if datetime_cols and numeric_cols:
            suggestions.append(ChartSuggestion(
                chart_type="line",
                title=f"{numeric_cols[0]} over time",
                x_column=datetime_cols[0],
                y_columns=[numeric_cols[0]],
                description="Time series visualization of numeric values",
                config={"interpolation": "linear"}
            ))
        
        # Bar chart if categorical + numeric
        elif categorical_cols and numeric_cols:
            suggestions.append(ChartSuggestion(
                chart_type="bar",
                title=f"{numeric_cols[0]} by {categorical_cols[0]}",
                x_column=categorical_cols[0],
                y_columns=[numeric_cols[0]],
                description="Compare values across categories",
                config={"orientation": "vertical"}
            ))
        
        # Metric if single numeric value
        elif numeric_cols and len(numeric_cols) >= 1:
            suggestions.append(ChartSuggestion(
                chart_type="metric",
                title=numeric_cols[0],
                y_columns=[numeric_cols[0]],
                description="Display key metric value",
                config={"format": "number"}
            ))
        
        return suggestions
    
    async def _get_relevant_schemas(
        self,
        allowed_datasets: Set[str],
        mentioned_tables: Optional[List[Tuple[Optional[str], str]]] = None
    ) -> str:
        """Get schema information for allowed datasets, prioritizing mentioned tables.
        
        Args:
            allowed_datasets: Set of dataset IDs
            mentioned_tables: List of (dataset_id, table_id) tuples mentioned in question
            
        Returns:
            Formatted schema information
        """
        try:
            schemas = []
            
            # First, fetch schemas for specifically mentioned tables
            if mentioned_tables:
                for dataset_id, table_id in mentioned_tables:
                    try:
                        # If dataset not specified, try to find it
                        if not dataset_id:
                            # Try each allowed dataset
                            for ds in allowed_datasets:
                                if ds == "*":
                                    continue
                                try:
                                    schema_result = await self.mcp_client.get_table_schema(
                                        dataset_id=ds,
                                        table_id=table_id,
                                        include_samples=False
                                    )
                                    schemas.append({
                                        "table_name": f"{self.project_id}.{ds}.{table_id}",
                                        "fields": schema_result.get("schema", [])
                                    })
                                    break  # Found it, stop searching
                                except Exception:
                                    continue
                        else:
                            # Dataset specified
                            schema_result = await self.mcp_client.get_table_schema(
                                dataset_id=dataset_id,
                                table_id=table_id,
                                include_samples=False
                            )
                            schemas.append({
                                "table_name": f"{self.project_id}.{dataset_id}.{table_id}",
                                "fields": schema_result.get("schema", [])
                            })
                    except Exception as e:
                        logger.warning(f"Failed to get schema for {dataset_id}.{table_id}: {e}")
            
            # If we have enough schemas, return early
            if len(schemas) >= 5:
                return self.prompt_builder.format_schema_info(schemas)
            
            # Otherwise, fetch additional schemas from allowed datasets
            if not allowed_datasets or "*" in allowed_datasets:
                # Get all datasets
                datasets_result = await self.mcp_client.list_datasets()
                datasets = datasets_result.get("datasets", [])
            else:
                datasets = [{"datasetId": ds} for ds in allowed_datasets]
            
            # Limit to first 3 datasets to avoid token limits
            datasets = datasets[:3]
            
            for dataset in datasets:
                dataset_id = dataset.get("datasetId", "")
                if not dataset_id:
                    continue
                
                # Skip if we already have enough schemas
                if len(schemas) >= 10:
                    break
                
                try:
                    # Get tables in dataset
                    tables_result = await self.mcp_client.list_tables(dataset_id)
                    tables = tables_result.get("tables", [])
                    
                    # Get schemas for tables we haven't fetched yet
                    for table in tables[:5]:  # Limit per dataset
                        table_id = table.get("tableId", "")
                        if not table_id:
                            continue
                        
                        # Skip if we already have this table's schema
                        table_name = f"{self.project_id}.{dataset_id}.{table_id}"
                        if any(s["table_name"] == table_name for s in schemas):
                            continue
                        
                        # Get table schema
                        schema_result = await self.mcp_client.get_table_schema(
                            dataset_id=dataset_id,
                            table_id=table_id,
                            include_samples=False
                        )
                        
                        schemas.append({
                            "table_name": table_name,
                            "fields": schema_result.get("schema", [])
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to get schema for {dataset_id}: {e}")
                    continue
            
            if not schemas:
                return "Schema information is currently unavailable. Please specify table names explicitly."
            
            return self.prompt_builder.format_schema_info(schemas)
            
        except Exception as e:
            logger.error(f"Error getting schemas: {e}", exc_info=True)
            return "Schema information is currently unavailable. Please specify table names explicitly."
    
    async def _save_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save a message to the conversation history.
        
        Args:
            session_id: Chat session ID
            user_id: User ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
        """
        try:
            await self.kb.append_chat_message(
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to save message: {e}", exc_info=True)
    
    def _is_metadata_question(self, question: str) -> Optional[str]:
        """Determine if question is about metadata (datasets/tables/schemas).
        
        Args:
            question: User's question
            
        Returns:
            Type of metadata question ("datasets", "tables", "schema") or None
        """
        question_lower = question.lower()
        
        # Dataset listing patterns
        dataset_patterns = [
            "what datasets", "list datasets", "show datasets", "available datasets",
            "which datasets", "dataset list", "datasets do i have", "datasets can i access",
            "what data sets", "list data sets", "show data sets", "list all datasets",
            "show all datasets", "all datasets", "show me datasets"
        ]
        if any(pattern in question_lower for pattern in dataset_patterns):
            return "datasets"
        
        # Table listing patterns
        table_patterns = [
            "what tables", "list tables", "show tables", "available tables",
            "which tables", "table list", "tables in", "tables do i have",
            "show me tables", "show me the tables", "list the tables",
            "what are the tables", "tables are"
        ]
        if any(pattern in question_lower for pattern in table_patterns):
            return "tables"
        
        # Schema/describe patterns
        schema_patterns = [
            "describe table", "describe the table", "table schema", "schema of",
            "table structure", "what columns", "show schema", "show structure",
            "what fields", "table definition", "column names"
        ]
        if any(pattern in question_lower for pattern in schema_patterns):
            return "schema"
        
        return None
    
    def _is_valid_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate SQL query before execution.
        
        Args:
            sql: SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not sql or not sql.strip():
            return False, "SQL query is empty"
        
        sql = sql.strip()
        
        # Check if it's only a comment
        if sql.startswith('--'):
            lines = sql.split('\n')
            non_comment_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('--')]
            if not non_comment_lines:
                return False, "SQL query contains only comments, no actual query"
        
        # Check for forbidden operations first (should be read-only)
        sql_upper = sql.upper()
        forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'TRUNCATE']
        for keyword in forbidden_keywords:
            if keyword in sql_upper.split():
                return False, f"Only read-only SELECT queries are allowed. {keyword} is not permitted."
        
        # Check if it contains required SQL keywords
        required_keywords = ['SELECT', 'WITH']
        if not any(keyword in sql_upper for keyword in required_keywords):
            return False, "SQL query must contain a SELECT statement"
        
        return True, None
    
    async def _handle_datasets_question(self) -> AgentResponse:
        """Handle question about listing datasets.
        
        Returns:
            Agent response with dataset information
        """
        try:
            datasets_result = await self.mcp_client.list_datasets()
            datasets = datasets_result.get("datasets", [])
            
            if not datasets:
                answer = "You currently don't have access to any datasets. Please contact your administrator to grant access."
            else:
                dataset_names = [d.get("datasetId", d.get("dataset_id", "")) for d in datasets]
                answer = f"You have access to {len(datasets)} dataset(s):\n\n"
                for i, name in enumerate(dataset_names, 1):
                    answer += f"{i}. {name}\n"
                answer += "\nYou can ask me to show tables in any of these datasets or query their data."
            
            return AgentResponse(
                success=True,
                answer=answer,
                metadata={
                    "metadata_type": "datasets",
                    "dataset_count": len(datasets)
                }
            )
        except Exception as e:
            logger.error(f"Error listing datasets: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                error=f"Failed to retrieve datasets: {str(e)}",
                error_type="execution"
            )
    
    async def _handle_tables_question(self, question: str, context: ConversationContext) -> AgentResponse:
        """Handle question about listing tables in a dataset.
        
        Args:
            question: User's question
            context: Conversation context
            
        Returns:
            Agent response with table information
        """
        try:
            # Try to extract dataset name from question (case-insensitive)
            dataset_id = None
            question_lower = question.lower()
            
            # Look for dataset names in the question (case-insensitive)
            for ds in context.allowed_datasets:
                if ds == "*":
                    continue
                # Check both lowercase and original case
                if ds.lower() in question_lower:
                    dataset_id = ds
                    break
            
            # Try to extract dataset name using patterns like "in <dataset>" or "dataset <name>"
            if not dataset_id:
                # Pattern: "in <dataset_name>"
                in_pattern = re.search(r'\bin\s+(?:the\s+)?([a-zA-Z0-9_]+)(?:\s+dataset)?', question, re.IGNORECASE)
                if in_pattern:
                    potential_dataset = in_pattern.group(1)
                    # Check if this matches any allowed dataset (case-insensitive)
                    for ds in context.allowed_datasets:
                        if ds != "*" and ds.lower() == potential_dataset.lower():
                            dataset_id = ds
                            break
            
            # If not found, check if user has access to only one dataset
            if not dataset_id and context.allowed_datasets:
                non_wildcard_datasets = [ds for ds in context.allowed_datasets if ds != "*"]
                if len(non_wildcard_datasets) == 1:
                    dataset_id = non_wildcard_datasets[0]
                elif len(non_wildcard_datasets) > 1:
                    # Multiple datasets available, ask for clarification
                    datasets_list = ", ".join(sorted(non_wildcard_datasets))
                    return AgentResponse(
                        success=False,
                        error=f"Please specify which dataset you'd like to see tables for. Available datasets: {datasets_list}",
                        error_type="validation",
                        metadata={
                            "available_datasets": list(non_wildcard_datasets),
                            "suggestion": "Try asking: 'show me tables in the <dataset_name> dataset'"
                        }
                    )
            
            if not dataset_id:
                # Fetch available datasets to help user
                try:
                    datasets_result = await self.mcp_client.list_datasets()
                    datasets = datasets_result.get("datasets", [])
                    dataset_names = [d.get("datasetId", d.get("dataset_id", "")) for d in datasets]
                    datasets_list = ", ".join(dataset_names) if dataset_names else "none"
                    
                    return AgentResponse(
                        success=False,
                        error=f"Please specify which dataset you'd like to see tables for. Available datasets: {datasets_list}",
                        error_type="validation",
                        metadata={
                            "available_datasets": dataset_names,
                            "suggestion": "Try asking: 'show me tables in the <dataset_name> dataset'"
                        }
                    )
                except Exception:
                    return AgentResponse(
                        success=False,
                        error="Please specify which dataset you'd like to see tables for.",
                        error_type="validation"
                    )
            
            # List tables in the dataset
            tables_result = await self.mcp_client.list_tables(dataset_id)
            tables = tables_result.get("tables", [])
            
            if not tables:
                # Provide helpful context
                answer = f"The dataset '{dataset_id}' has no tables, or you don't have access to any tables in it.\n\n"
                answer += "Possible reasons:\n"
                answer += "1. The dataset is empty\n"
                answer += "2. You don't have permission to view tables in this dataset\n"
                answer += "3. The dataset name might be incorrect\n\n"
                answer += "Try asking: 'what datasets do I have access to?' to see all available datasets."
            else:
                table_names = [t.get("tableId", t.get("table_id", "")) for t in tables]
                answer = f"Dataset '{dataset_id}' contains {len(tables)} table(s):\n\n"
                for i, name in enumerate(table_names, 1):
                    answer += f"{i}. {name}\n"
                answer += "\nYou can ask me to:\n"
                answer += f"- Describe any table: 'describe table {dataset_id}.{table_names[0]}'\n"
                answer += f"- Query the data: 'show me top 10 rows from {table_names[0]}'"
            
            return AgentResponse(
                success=True,
                answer=answer,
                metadata={
                    "metadata_type": "tables",
                    "dataset_id": dataset_id,
                    "table_count": len(tables),
                    "table_names": table_names if tables else []
                }
            )
        except Exception as e:
            logger.error(f"Error listing tables: {e}", exc_info=True)
            
            # Provide more helpful error message
            error_msg = f"I encountered an error while trying to list tables"
            if "dataset_id" in locals() and dataset_id:
                error_msg += f" in dataset '{dataset_id}'"
            error_msg += f".\n\nError details: {str(e)}\n\n"
            error_msg += "You can try:\n"
            error_msg += "1. Checking if the dataset name is correct\n"
            error_msg += "2. Asking 'what datasets do I have access to?'\n"
            error_msg += "3. Verifying your permissions with your administrator"
            
            return AgentResponse(
                success=False,
                error=error_msg,
                error_type="execution",
                metadata={"error_details": str(e)}
            )
    
    def _extract_table_references_from_question(self, question: str) -> List[Tuple[Optional[str], str]]:
        """Extract table references from user question.
        
        Args:
            question: User's question
            
        Returns:
            List of (dataset_id, table_id) tuples. dataset_id may be None.
        """
        references = []
        
        # Pattern 1: project.dataset.table or dataset.table
        full_ref_pattern = r'(?:FROM|from|table|TABLE)\s+[`"]?([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)[`"]?'
        matches = re.findall(full_ref_pattern, question)
        for match in matches:
            # match is (project, dataset, table) - we use dataset and table
            references.append((match[1], match[2]))
        
        # Pattern 2: dataset.table
        dataset_table_pattern = r'(?:FROM|from|table|TABLE)\s+[`"]?([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)[`"]?'
        matches = re.findall(dataset_table_pattern, question)
        for match in matches:
            if (match[0], match[1]) not in references:
                references.append((match[0], match[1]))
        
        # Pattern 3: Just table name (no dataset)
        table_only_pattern = r'(?:FROM|from|table|TABLE)\s+[`"]?([a-zA-Z0-9_]+)[`"]?'
        matches = re.findall(table_only_pattern, question)
        for match in matches:
            # Only add if not already found with a dataset
            if not any(r[1] == match for r in references):
                references.append((None, match))
        
        return references
    
    async def _validate_sql_tables(
        self,
        sql: str,
        allowed_datasets: Set[str],
        allowed_tables: Dict[str, Set[str]]
    ) -> Dict[str, Any]:
        """Validate that table references in SQL exist and are accessible.
        
        Args:
            sql: SQL query to validate
            allowed_datasets: User's allowed datasets
            allowed_tables: User's allowed tables per dataset
            
        Returns:
            Dict with "valid" bool and optional "error" message
        """
        try:
            # Extract table references from SQL
            pattern = r'(?:FROM|JOIN)\s+`?([a-zA-Z0-9_.-]+)`?'
            matches = re.findall(pattern, sql, re.IGNORECASE)
            
            for table_ref in matches:
                parts = table_ref.split('.')
                
                if len(parts) >= 2:
                    # Has dataset.table or project.dataset.table
                    dataset_id = parts[-2]
                    table_id = parts[-1]
                    
                    # Check if user has access
                    if "*" in allowed_datasets:
                        continue  # User has access to all
                    
                    if dataset_id not in allowed_datasets:
                        return {
                            "valid": False,
                            "error": f"Table '{table_ref}' references dataset '{dataset_id}' which you don't have access to. Available datasets: {', '.join(sorted(allowed_datasets))}"
                        }
                    
                    # Check table access
                    if dataset_id in allowed_tables:
                        dataset_tables = allowed_tables[dataset_id]
                        if "*" not in dataset_tables and table_id not in dataset_tables:
                            return {
                                "valid": False,
                                "error": f"You don't have access to table '{table_id}' in dataset '{dataset_id}'"
                            }
            
            return {"valid": True}
            
        except Exception as e:
            logger.warning(f"Error validating SQL tables: {e}")
            # Don't block on validation errors
            return {"valid": True}
    
    async def _handle_schema_question(self, question: str, context: ConversationContext) -> AgentResponse:
        """Handle question about table schema.
        
        Args:
            question: User's question
            context: Conversation context
            
        Returns:
            Agent response with schema information
        """
        try:
            # Try to extract table reference from question
            # Look for patterns like "dataset.table" or just "table"
            table_ref_match = re.search(r'([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)', question)
            
            dataset_id = None
            table_id = None
            
            if table_ref_match:
                dataset_id = table_ref_match.group(1)
                table_id = table_ref_match.group(2)
            else:
                # Look for just a table name
                words = question.split()
                for i, word in enumerate(words):
                    if word.lower() in ['table', 'describe', 'schema', 'structure']:
                        if i + 1 < len(words):
                            potential_table = words[i + 1].strip('.,?!')
                            table_id = potential_table
                            break
            
            if not table_id:
                return AgentResponse(
                    success=False,
                    error="Please specify which table you'd like to see the schema for (e.g., 'describe table dataset.tablename').",
                    error_type="validation"
                )
            
            # If dataset not specified, try to find it
            if not dataset_id and context.allowed_datasets:
                if "*" not in context.allowed_datasets:
                    dataset_id = list(context.allowed_datasets)[0]
            
            if not dataset_id:
                return AgentResponse(
                    success=False,
                    error=f"Please specify the dataset for table '{table_id}' (e.g., 'dataset.{table_id}').",
                    error_type="validation"
                )
            
            schema_result = await self.mcp_client.get_table_schema(
                dataset_id=dataset_id,
                table_id=table_id,
                include_samples=False
            )
            
            schema = schema_result.get("schema", [])
            
            if not schema:
                answer = f"Could not retrieve schema for table {dataset_id}.{table_id}."
            else:
                answer = f"Schema for table {dataset_id}.{table_id}:\n\n"
                for field in schema:
                    field_name = field.get("name", "")
                    field_type = field.get("type", "")
                    field_mode = field.get("mode", "NULLABLE")
                    description = field.get("description", "")
                    
                    answer += f"• {field_name} ({field_type}, {field_mode})"
                    if description:
                        answer += f": {description}"
                    answer += "\n"
                
                num_rows = schema_result.get("numRows") or schema_result.get("num_rows")
                if num_rows is not None:
                    answer += f"\nTotal rows: {num_rows:,}"
            
            return AgentResponse(
                success=True,
                answer=answer,
                metadata={
                    "metadata_type": "schema",
                    "dataset_id": dataset_id,
                    "table_id": table_id,
                    "field_count": len(schema)
                }
            )
        except Exception as e:
            logger.error(f"Error getting table schema: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                error=f"Failed to retrieve table schema: {str(e)}",
                error_type="execution"
            )
