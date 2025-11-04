"""Tool executor for running LLM-requested tool calls.

This module handles the execution of tool calls requested by the LLM,
including error handling and result formatting for both OpenAI and Anthropic.
"""

import json
import logging
from typing import List, Dict, Any

from ..llm.providers.base import ToolCall
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tool calls from LLM.
    
    This class takes tool calls from the LLM response and executes them
    using the tool registry, handling errors and formatting results.
    
    Args:
        tool_registry: Registry of available tools
        
    Example:
        >>> executor = ToolExecutor(tool_registry)
        >>> results = await executor.execute_tool_calls(tool_calls, "openai")
        >>> for result in results:
        ...     print(result["tool_name"], result["success"])
    """
    
    def __init__(self, tool_registry: ToolRegistry):
        """Initialize the tool executor.
        
        Args:
            tool_registry: Registry of available tools
        """
        self.registry = tool_registry
    
    async def execute_tool_calls(
        self,
        tool_calls: List[ToolCall]
    ) -> List[Dict[str, Any]]:
        """Execute multiple tool calls and return results.
        
        Args:
            tool_calls: List of ToolCall objects from LLM
            
        Returns:
            List of result dictionaries with tool_call_id, tool_name, success, and result/error
        """
        results = []
        
        for tool_call in tool_calls:
            result = await self.execute_single_tool(tool_call)
            results.append(result)
        
        return results
    
    async def execute_single_tool(
        self,
        tool_call: ToolCall
    ) -> Dict[str, Any]:
        """Execute a single tool call.
        
        Args:
            tool_call: ToolCall object from LLM
            
        Returns:
            Dict with tool_call_id, tool_name, success, and result/error
        """
        tool_name = None
        call_id = None
        
        try:
            tool_name = tool_call.name
            arguments = tool_call.arguments
            call_id = tool_call.id
            
            logger.info(f"Executing tool: {tool_name} with args: {arguments}")
            
            # Get tool from registry
            tool = self.registry.get_tool_by_name(tool_name)
            if not tool:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            # Ensure handler is a coroutine function
            import asyncio
            if not asyncio.iscoroutinefunction(tool.handler):
                raise ValueError(f"Tool handler for {tool_name} is not async")
            
            # Execute tool handler
            result = await tool.handler(**arguments)
            
            logger.info(f"Tool {tool_name} executed successfully")
            
            return {
                "tool_call_id": call_id,
                "tool_name": tool_name,
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name if tool_name else 'unknown'}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "tool_call_id": call_id,
                "tool_name": tool_name if tool_name else "unknown",
                "success": False,
                "error": str(e)
            }
