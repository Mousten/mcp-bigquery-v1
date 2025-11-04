"""Tool registry for BigQuery agent.

This module defines the available tools that the agent can use to interact
with BigQuery through the MCP client, and provides utilities for formatting
these tools for different LLM providers.
"""

from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
import logging

from ..llm.providers.base import ToolDefinition
from .mcp_client import MCPBigQueryClient

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Represents a tool available to the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format
    handler: Callable


class ToolRegistry:
    """Registry of all available BigQuery tools.
    
    This class maintains a catalog of tools that the agent can use,
    and provides utilities for formatting these tools for different
    LLM providers (OpenAI, Anthropic, etc.)
    
    Args:
        mcp_client: MCP BigQuery client for executing operations
        
    Example:
        >>> registry = ToolRegistry(mcp_client)
        >>> tools = registry.get_tools_for_llm("openai")
        >>> tool = registry.get_tool_by_name("list_datasets")
        >>> result = await tool.handler()
    """
    
    def __init__(self, mcp_client: MCPBigQueryClient):
        """Initialize the tool registry.
        
        Args:
            mcp_client: MCP client for BigQuery operations
        """
        self.mcp_client = mcp_client
        self.tools = self._register_tools()
    
    def _register_tools(self) -> List[Tool]:
        """Register all available tools.
        
        Returns:
            List of Tool objects
        """
        return [
            Tool(
                name="list_datasets",
                description=(
                    "List all BigQuery datasets the user has access to. "
                    "Use when user asks about available datasets, what datasets they have, "
                    "or wants to explore their data catalog. "
                    "Examples: 'what datasets do I have?', 'show me my datasets', 'list all datasets'"
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                handler=self.mcp_client.get_datasets
            ),
            Tool(
                name="list_tables",
                description=(
                    "List all tables in a specific BigQuery dataset. "
                    "Use when user asks about tables in a dataset. "
                    "Examples: 'what tables are in Analytics?', 'show tables in dataset X', 'list tables'"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "The ID of the dataset to list tables from"
                        }
                    },
                    "required": ["dataset_id"]
                },
                handler=self.mcp_client.get_tables
            ),
            Tool(
                name="get_table_schema",
                description=(
                    "Get the schema (columns and types) for a specific table. "
                    "Use when user asks about table structure, columns, or fields. "
                    "Examples: 'describe Daily_Sales table', 'what columns does X have?', "
                    "'show me the schema of table Y'"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "The dataset ID containing the table"
                        },
                        "table_id": {
                            "type": "string",
                            "description": "The table ID to get schema for"
                        },
                        "include_samples": {
                            "type": "boolean",
                            "description": "Whether to include sample rows (default: true)",
                            "default": True
                        }
                    },
                    "required": ["dataset_id", "table_id"]
                },
                handler=self.mcp_client.get_table_schema
            ),
            Tool(
                name="execute_sql",
                description=(
                    "Execute a SQL query against BigQuery to retrieve actual data. "
                    "Use when user wants to see data, analyze values, or run queries. "
                    "IMPORTANT: Before using this tool, verify table names exist using list_tables. "
                    "Examples: 'show me top 10 rows', 'what's the total revenue?', 'query the data'"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL query to execute (must be read-only)"
                        },
                        "maximum_bytes_billed": {
                            "type": "integer",
                            "description": "Maximum bytes to bill (default: 1GB)",
                            "default": 1000000000
                        },
                        "use_cache": {
                            "type": "boolean",
                            "description": "Whether to use query result caching (default: true)",
                            "default": True
                        }
                    },
                    "required": ["sql"]
                },
                handler=self.mcp_client.execute_sql
            ),
        ]
    
    def get_tools_for_llm(self, provider: str) -> List[ToolDefinition]:
        """Get tools formatted for specific LLM provider.
        
        Args:
            provider: LLM provider name ("openai", "anthropic", etc.)
            
        Returns:
            List of ToolDefinition objects compatible with the LLM provider
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider not in ("openai", "anthropic"):
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Both OpenAI and Anthropic use the same ToolDefinition format
        # The actual provider-specific formatting is handled by the LLM provider classes
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters
            )
            for tool in self.tools
        ]
    
    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get tool by name.
        
        Args:
            name: Tool name to look up
            
        Returns:
            Tool object if found, None otherwise
        """
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None
    
    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools.
        
        Returns:
            List of all Tool objects
        """
        return self.tools
