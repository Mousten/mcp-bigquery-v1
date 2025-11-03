"""Prompt templates and builder for the insights agent."""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime


class PromptBuilder:
    """Builder for constructing prompts for the LLM."""
    
    SYSTEM_PROMPT_TEMPLATE = """You are an AI assistant specialized in BigQuery data analysis. Your role is to help users explore and analyze their data through natural language conversations.

**Your Capabilities:**
- Generate SQL queries for BigQuery to query actual data
- Analyze query results and provide insights
- Suggest appropriate visualizations
- Answer follow-up questions using conversation context

**User Permissions:**
The user has access to the following datasets and tables:
{dataset_permissions}

**Important Constraints:**
1. ONLY generate SQL queries using the datasets and tables listed above
2. If the user asks about data they don't have access to, politely explain the limitation
3. Always use fully qualified table names: `project.dataset.table`
4. Keep queries efficient and respect BigQuery best practices
5. When unsure about schema, ask for clarification
6. NEVER generate SQL comments as queries (e.g., "-- No data available")
7. If you cannot generate a valid SQL query, explain why in the explanation field and leave sql empty

**Important: Metadata vs Data Queries:**
- Questions about listing datasets, tables, or schemas should NOT generate SQL
- These metadata questions are handled automatically by the system
- ONLY generate SQL for actual data queries (SELECT statements that retrieve data from tables)
- Examples of metadata questions (do NOT generate SQL):
  * "what datasets do I have access to?"
  * "what tables are in dataset X?"
  * "describe table Y"
  * "show me the schema of table Z"
- Examples of data queries (DO generate SQL):
  * "show me the top 10 rows from table X"
  * "what is the total revenue by product?"
  * "count the number of users in table Y"

**Response Format:**
When generating SQL, structure your response as a JSON object with:
- "sql": The SQL query string (MUST be a valid SELECT query, never a comment)
- "explanation": Brief explanation of what the query does
- "tables_used": List of table names used
- "estimated_complexity": "low", "medium", or "high"
- "warnings": List of any potential issues or notes

When summarizing results, provide:
- Clear, business-friendly language
- Key insights and trends
- Actionable recommendations when appropriate"""

    SQL_GENERATION_PROMPT = """Based on the user's question and conversation context, generate a BigQuery SQL query.

**User Question:** {question}

**Available Schema Information:**
{schema_info}

**Recent Conversation:**
{conversation_history}

Generate a SQL query that answers the user's question. Ensure the query:
1. Uses only the tables the user has access to
2. Is optimized for BigQuery
3. Handles NULL values appropriately
4. Includes appropriate aggregations or filters
5. Limits results to a reasonable number (use LIMIT if needed)

Respond with a JSON object containing: sql, explanation, tables_used, estimated_complexity, and warnings."""

    SUMMARY_PROMPT = """Analyze the following query results and provide a clear, business-friendly summary.

**Original Question:** {question}

**SQL Query:**
```sql
{sql_query}
```

**Results:**
{results_preview}

**Result Metadata:**
- Total rows: {row_count}
- Columns: {columns}

Provide a summary that:
1. Directly answers the user's question
2. Highlights key findings and trends
3. Uses clear, non-technical language
4. Suggests next steps or follow-up questions if relevant
5. Keeps it concise (2-4 paragraphs)"""

    CHART_SUGGESTION_PROMPT = """Based on the query results, suggest appropriate visualizations.

**Query Results Schema:**
{result_schema}

**Sample Data:**
{sample_data}

**Result Statistics:**
- Row count: {row_count}
- Numeric columns: {numeric_columns}
- Categorical columns: {categorical_columns}
- Date/time columns: {datetime_columns}

Suggest 1-3 chart types that would best visualize this data. For each suggestion, provide:
- chart_type: One of [bar, line, pie, scatter, area, table, metric, map, heatmap, histogram]
- title: Descriptive chart title
- x_column: Column for x-axis (if applicable)
- y_columns: List of columns for y-axis/values
- description: Why this chart is appropriate
- config: Additional configuration (colors, stacking, etc.)

Respond with a JSON array of chart suggestions."""

    CLARIFICATION_PROMPT = """The user's question requires more information to generate an accurate query.

**User Question:** {question}

**Issue:** {issue}

**Available Datasets:** {datasets}

Generate a helpful response that:
1. Acknowledges the question
2. Explains what information is needed
3. Suggests specific details they should provide
4. Offers examples if helpful

Keep it friendly and concise."""

    @staticmethod
    def build_system_prompt(
        allowed_datasets: Set[str],
        allowed_tables: Dict[str, Set[str]],
        project_id: str
    ) -> str:
        """Build the system prompt with user permissions.
        
        Args:
            allowed_datasets: Set of dataset IDs user can access
            allowed_tables: Dict mapping dataset IDs to table IDs
            project_id: Google Cloud project ID
            
        Returns:
            Formatted system prompt
        """
        if not allowed_datasets:
            permissions_text = "No datasets currently accessible. Please contact your administrator."
        elif "*" in allowed_datasets:
            permissions_text = f"All datasets in project `{project_id}`"
        else:
            permissions_list = []
            for dataset in sorted(allowed_datasets):
                tables = allowed_tables.get(dataset, set())
                if "*" in tables or not tables:
                    permissions_list.append(f"  - `{project_id}.{dataset}.*` (all tables)")
                else:
                    for table in sorted(tables):
                        permissions_list.append(f"  - `{project_id}.{dataset}.{table}`")
            permissions_text = "\n".join(permissions_list)
        
        return PromptBuilder.SYSTEM_PROMPT_TEMPLATE.format(
            dataset_permissions=permissions_text
        )
    
    @staticmethod
    def build_sql_generation_prompt(
        question: str,
        schema_info: str,
        conversation_history: str
    ) -> str:
        """Build prompt for SQL generation.
        
        Args:
            question: User's question
            schema_info: Schema information for relevant tables
            conversation_history: Recent conversation turns
            
        Returns:
            Formatted SQL generation prompt
        """
        return PromptBuilder.SQL_GENERATION_PROMPT.format(
            question=question,
            schema_info=schema_info,
            conversation_history=conversation_history
        )
    
    @staticmethod
    def build_summary_prompt(
        question: str,
        sql_query: str,
        results_preview: str,
        row_count: int,
        columns: List[str]
    ) -> str:
        """Build prompt for result summarization.
        
        Args:
            question: Original user question
            sql_query: Executed SQL query
            results_preview: Preview of results (first few rows)
            row_count: Total number of rows returned
            columns: List of column names
            
        Returns:
            Formatted summary prompt
        """
        return PromptBuilder.SUMMARY_PROMPT.format(
            question=question,
            sql_query=sql_query,
            results_preview=results_preview,
            row_count=row_count,
            columns=", ".join(columns)
        )
    
    @staticmethod
    def build_chart_suggestion_prompt(
        result_schema: str,
        sample_data: str,
        row_count: int,
        numeric_columns: List[str],
        categorical_columns: List[str],
        datetime_columns: List[str]
    ) -> str:
        """Build prompt for chart suggestions.
        
        Args:
            result_schema: Schema of query results
            sample_data: Sample rows from results
            row_count: Total number of rows
            numeric_columns: List of numeric column names
            categorical_columns: List of categorical column names
            datetime_columns: List of datetime column names
            
        Returns:
            Formatted chart suggestion prompt
        """
        return PromptBuilder.CHART_SUGGESTION_PROMPT.format(
            result_schema=result_schema,
            sample_data=sample_data,
            row_count=row_count,
            numeric_columns=", ".join(numeric_columns) if numeric_columns else "None",
            categorical_columns=", ".join(categorical_columns) if categorical_columns else "None",
            datetime_columns=", ".join(datetime_columns) if datetime_columns else "None"
        )
    
    @staticmethod
    def build_clarification_prompt(
        question: str,
        issue: str,
        datasets: List[str]
    ) -> str:
        """Build prompt for requesting clarification.
        
        Args:
            question: User's question
            issue: Description of what's unclear
            datasets: Available datasets
            
        Returns:
            Formatted clarification prompt
        """
        return PromptBuilder.CLARIFICATION_PROMPT.format(
            question=question,
            issue=issue,
            datasets=", ".join(datasets)
        )
    
    @staticmethod
    def format_conversation_history(messages: List[Dict[str, Any]], limit: int = 5) -> str:
        """Format recent conversation messages for context.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            limit: Maximum number of messages to include
            
        Returns:
            Formatted conversation history string
        """
        if not messages:
            return "No previous conversation."
        
        recent_messages = messages[-limit:] if len(messages) > limit else messages
        formatted = []
        
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("created_at", "")
            
            if timestamp:
                formatted.append(f"[{role} - {timestamp}]: {content}")
            else:
                formatted.append(f"[{role}]: {content}")
        
        return "\n\n".join(formatted)
    
    @staticmethod
    def format_schema_info(schemas: List[Dict[str, Any]]) -> str:
        """Format schema information for tables.
        
        Args:
            schemas: List of schema dicts from BigQuery
            
        Returns:
            Formatted schema information
        """
        if not schemas:
            return "No schema information available."
        
        formatted = []
        for schema in schemas:
            table_name = schema.get("table_name", "unknown")
            fields = schema.get("fields", [])
            
            formatted.append(f"Table: {table_name}")
            formatted.append("Columns:")
            
            for field in fields:
                field_name = field.get("name", "")
                field_type = field.get("type", "")
                field_mode = field.get("mode", "NULLABLE")
                description = field.get("description", "")
                
                col_info = f"  - {field_name} ({field_type}, {field_mode})"
                if description:
                    col_info += f": {description}"
                formatted.append(col_info)
            
            formatted.append("")  # Empty line between tables
        
        return "\n".join(formatted)
