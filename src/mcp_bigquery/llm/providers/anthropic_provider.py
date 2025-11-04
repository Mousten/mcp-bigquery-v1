"""Anthropic LLM provider implementation.

This module provides an implementation of the LLMProvider interface
for Anthropic's Claude API using the official Anthropic SDK.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from anthropic import AsyncAnthropic, AnthropicError

from .base import (
    LLMProvider,
    LLMProviderConfig,
    LLMProviderError,
    LLMConfigurationError,
    LLMGenerationError,
    Message,
    GenerationResponse,
    ToolCall,
    ToolDefinition,
)


class AnthropicProviderConfig(LLMProviderConfig):
    """Configuration for Anthropic provider."""
    model: str = Field(default="claude-3-5-sonnet-20241022")
    base_url: Optional[str] = None


class AnthropicProvider(LLMProvider):
    """Anthropic implementation of the LLM provider interface.
    
    Supports:
    - Text generation with Claude models
    - Tool use (Anthropic's version of function calling)
    - Vision (for Claude 3+ models)
    - Token counting via Anthropic's SDK utilities
    """
    
    def __init__(self, config: AnthropicProviderConfig):
        """Initialize Anthropic provider.
        
        Args:
            config: Anthropic-specific configuration
            
        Raises:
            LLMConfigurationError: If configuration is invalid
        """
        super().__init__(config)
        
        try:
            self.client = AsyncAnthropic(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
        except Exception as e:
            raise LLMConfigurationError(f"Failed to initialize Anthropic client: {e}")
        
        self._model_supports_tools = self._check_tool_support()
        self._model_supports_vision = self._check_vision_support()
    
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> GenerationResponse:
        """Generate a response using Anthropic's API.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions for tool use
            **kwargs: Additional Anthropic-specific parameters
            
        Returns:
            GenerationResponse with the LLM's output
            
        Raises:
            LLMGenerationError: If generation fails
        """
        try:
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                elif msg.role == "tool":
                    # Anthropic requires tool results in specific format
                    anthropic_messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content or ""
                            }
                        ]
                    })
                elif msg.role == "assistant" and msg.tool_calls:
                    # Assistant message with tool calls
                    content_blocks = []
                    if msg.content:
                        content_blocks.append({
                            "type": "text",
                            "text": msg.content
                        })
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments
                        })
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": content_blocks
                    })
                else:
                    role = "user" if msg.role in ("user", "function") else "assistant"
                    anthropic_messages.append({
                        "role": role,
                        "content": msg.content or "",
                    })
            
            request_params: Dict[str, Any] = {
                "model": self.config.model,
                "messages": anthropic_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": self.config.max_tokens or 4096,
            }
            
            if system_message:
                request_params["system"] = system_message
            
            if tools and self._model_supports_tools:
                request_params["tools"] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.parameters,
                    }
                    for tool in tools
                ]
                if kwargs.get("tool_choice"):
                    request_params["tool_choice"] = kwargs["tool_choice"]
            
            response = await self.client.messages.create(**request_params)
            
            content_text = None
            tool_calls_list = []
            
            for block in response.content:
                if block.type == "text":
                    content_text = block.text
                elif block.type == "tool_use":
                    tool_calls_list.append(
                        ToolCall(
                            id=block.id,
                            name=block.name,
                            arguments=block.input if hasattr(block, 'input') else {},
                        )
                    )
            
            usage_dict = {}
            if response.usage:
                usage_dict = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                }
            
            return GenerationResponse(
                content=content_text,
                tool_calls=tool_calls_list,
                finish_reason=response.stop_reason,
                usage=usage_dict,
                raw_response=response,
            )
            
        except AnthropicError as e:
            raise LLMGenerationError(f"Anthropic generation failed: {e}")
        except Exception as e:
            raise LLMGenerationError(f"Unexpected error during generation: {e}")
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens using Anthropic's counting utility.
        
        Args:
            text: Text to count tokens for
            model: Optional model name (not used for Anthropic)
            
        Returns:
            Approximate number of tokens in the text
            
        Raises:
            LLMProviderError: If token counting fails
        """
        try:
            count_result = self.client.count_tokens(text)
            return count_result
        except Exception:
            return self._approximate_token_count(text)
    
    def count_messages_tokens(
        self,
        messages: List[Message],
        model: Optional[str] = None
    ) -> int:
        """Count tokens in messages.
        
        Args:
            messages: List of messages to count tokens for
            model: Optional model name (not used for Anthropic)
            
        Returns:
            Approximate total number of tokens
            
        Raises:
            LLMProviderError: If token counting fails
        """
        try:
            total_tokens = 0
            
            for message in messages:
                total_tokens += self.count_tokens(message.content)
                total_tokens += 4
            
            return total_tokens
            
        except Exception as e:
            raise LLMProviderError(f"Message token counting failed: {e}")
    
    def supports_functions(self) -> bool:
        """Check if the current model supports tool use.
        
        Returns:
            True if model supports tool use
        """
        return self._model_supports_tools
    
    def supports_vision(self) -> bool:
        """Check if the current model supports vision.
        
        Returns:
            True if model supports vision
        """
        return self._model_supports_vision
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model.
        
        Returns:
            Dictionary with model metadata
        """
        model_info = {
            "provider": "anthropic",
            "model": self.config.model,
            "supports_functions": self._model_supports_tools,
            "supports_vision": self._model_supports_vision,
        }
        
        context_windows = {
            "claude-3-5-sonnet-20241022": 200000,
            "claude-3-5-sonnet-20240620": 200000,
            "claude-3-opus-20240229": 200000,
            "claude-3-sonnet-20240229": 200000,
            "claude-3-haiku-20240307": 200000,
            "claude-2.1": 200000,
            "claude-2.0": 100000,
        }
        
        model_info["max_context_tokens"] = context_windows.get(
            self.config.model, 100000
        )
        
        return model_info
    
    @property
    def provider_name(self) -> str:
        """Get the provider name.
        
        Returns:
            "anthropic"
        """
        return "anthropic"
    
    def _check_tool_support(self) -> bool:
        """Check if the configured model supports tool use."""
        tool_models = {
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
        }
        
        for model in tool_models:
            if self.config.model.startswith(model):
                return True
        
        return False
    
    def _check_vision_support(self) -> bool:
        """Check if the configured model supports vision."""
        vision_models = {
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku",
        }
        
        for model in vision_models:
            if self.config.model.startswith(model):
                return True
        
        return False
    
    def _approximate_token_count(self, text: str) -> int:
        """Approximate token count when SDK method unavailable.
        
        Uses a simple heuristic: ~4 characters per token.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Approximate token count
        """
        return len(text) // 4
