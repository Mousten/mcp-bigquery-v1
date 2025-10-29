"""Conversational agent for BigQuery insights using LLMs and MCP client."""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
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
        enable_caching: bool = True
    ):
        """Initialize the insights agent.
        
        Args:
            llm_provider: LLM provider instance (OpenAI, Anthropic, etc.)
            mcp_client: MCP client for BigQuery operations
            kb: Supabase knowledge base for persistence
            project_id: Google Cloud project ID
            max_retries: Maximum retries for failed operations
            enable_caching: Whether to cache LLM responses
        """
        self.llm = llm_provider
        self.mcp_client = mcp_client
        self.kb = kb
        self.project_id = project_id
        self.max_retries = max_retries
        self.enable_caching = enable_caching
        self.prompt_builder = PromptBuilder()
    
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
            
            # Step 2: Generate SQL query
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
            
            # Step 3: Execute query
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
            
            # Step 4: Generate summary
            summary = await self._generate_summary(
                question=request.question,
                sql_query=sql_result.sql,
                results=query_results
            )
            
            # Step 5: Generate chart suggestions
            chart_suggestions = await self._generate_chart_suggestions(
                results=query_results
            )
            
            # Step 6: Build response
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
            # Build system prompt
            system_prompt = self.prompt_builder.build_system_prompt(
                allowed_datasets=context.allowed_datasets,
                allowed_tables=context.allowed_tables,
                project_id=self.project_id
            )
            
            # Get relevant schema information
            schema_info = await self._get_relevant_schemas(context.allowed_datasets)
            
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
            
            return self._parse_sql_generation(response.content or "")
            
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
            
            if not rows:
                return "The query executed successfully but returned no results. This might mean there's no data matching your criteria, or the tables might be empty."
            
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
                row_count=len(rows),
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
            return f"The query returned {len(results.get('rows', []))} rows. Review the data below for details."
    
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
    
    async def _get_relevant_schemas(self, allowed_datasets: Set[str]) -> str:
        """Get schema information for allowed datasets.
        
        Args:
            allowed_datasets: Set of dataset IDs
            
        Returns:
            Formatted schema information
        """
        try:
            if not allowed_datasets or "*" in allowed_datasets:
                # Get all datasets
                datasets_result = await self.mcp_client.list_datasets()
                datasets = datasets_result.get("datasets", [])
            else:
                datasets = [{"datasetId": ds} for ds in allowed_datasets]
            
            # Limit to first 3 datasets to avoid token limits
            datasets = datasets[:3]
            
            schemas = []
            for dataset in datasets:
                dataset_id = dataset.get("datasetId", "")
                if not dataset_id:
                    continue
                
                try:
                    # Get tables in dataset
                    tables_result = await self.mcp_client.list_tables(dataset_id)
                    tables = tables_result.get("tables", [])[:5]  # Limit to 5 tables
                    
                    for table in tables:
                        table_id = table.get("tableId", "")
                        if not table_id:
                            continue
                        
                        # Get table schema
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
                    logger.warning(f"Failed to get schema for {dataset_id}: {e}")
                    continue
            
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
