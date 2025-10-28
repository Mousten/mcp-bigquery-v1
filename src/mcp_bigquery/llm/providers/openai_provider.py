"""OpenAI LLM provider implementation.

This module provides an implementation of the LLMProvider interface
for OpenAI's API using the official OpenAI SDK (v1.x).
"""

import tiktoken
from typing import Any, Dict, List, Optional
from pydantic import Field

from openai import AsyncOpenAI, OpenAIError

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


class OpenAIProviderConfig(LLMProviderConfig):
    """Configuration for OpenAI provider."""
    model: str = Field(default="gpt-4o")
    base_url: Optional[str] = None
    organization: Optional[str] = None


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of the LLM provider interface.
    
    Supports:
    - Text generation with various GPT models
    - Function/tool calling
    - Vision (for GPT-4 Vision models)
    - Accurate token counting via tiktoken
    """
    
    def __init__(self, config: OpenAIProviderConfig):
        """Initialize OpenAI provider.
        
        Args:
            config: OpenAI-specific configuration
            
        Raises:
            LLMConfigurationError: If configuration is invalid
        """
        super().__init__(config)
        
        try:
            self.client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                organization=config.organization,
                timeout=config.timeout,
            )
        except Exception as e:
            raise LLMConfigurationError(f"Failed to initialize OpenAI client: {e}")
        
        self._model_supports_functions = self._check_function_support()
        self._model_supports_vision = self._check_vision_support()
    
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> GenerationResponse:
        """Generate a response using OpenAI's API.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional OpenAI-specific parameters
            
        Returns:
            GenerationResponse with the LLM's output
            
        Raises:
            LLMGenerationError: If generation fails
        """
        try:
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            request_params: Dict[str, Any] = {
                "model": self.config.model,
                "messages": openai_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
            }
            
            if self.config.max_tokens:
                request_params["max_tokens"] = self.config.max_tokens
            
            if tools and self._model_supports_functions:
                request_params["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        }
                    }
                    for tool in tools
                ]
                if kwargs.get("tool_choice"):
                    request_params["tool_choice"] = kwargs["tool_choice"]
            
            response = await self.client.chat.completions.create(**request_params)
            
            choice = response.choices[0]
            message = choice.message
            
            tool_calls_list = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    import json
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    tool_calls_list.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=arguments,
                        )
                    )
            
            usage_dict = {}
            if response.usage:
                usage_dict = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            
            return GenerationResponse(
                content=message.content,
                tool_calls=tool_calls_list,
                finish_reason=choice.finish_reason,
                usage=usage_dict,
                raw_response=response,
            )
            
        except OpenAIError as e:
            raise LLMGenerationError(f"OpenAI generation failed: {e}")
        except Exception as e:
            raise LLMGenerationError(f"Unexpected error during generation: {e}")
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens using tiktoken.
        
        Args:
            text: Text to count tokens for
            model: Optional model name (defaults to config.model)
            
        Returns:
            Number of tokens in the text
            
        Raises:
            LLMProviderError: If token counting fails
        """
        try:
            model_name = model or self.config.model
            encoding = tiktoken.encoding_for_model(model_name)
            return len(encoding.encode(text))
        except Exception as e:
            raise LLMProviderError(f"Token counting failed: {e}")
    
    def count_messages_tokens(
        self,
        messages: List[Message],
        model: Optional[str] = None
    ) -> int:
        """Count tokens in messages following OpenAI's token counting rules.
        
        Args:
            messages: List of messages to count tokens for
            model: Optional model name (defaults to config.model)
            
        Returns:
            Total number of tokens
            
        Raises:
            LLMProviderError: If token counting fails
        """
        try:
            model_name = model or self.config.model
            encoding = tiktoken.encoding_for_model(model_name)
            
            tokens_per_message = 3
            tokens_per_name = 1
            
            num_tokens = 0
            for message in messages:
                num_tokens += tokens_per_message
                num_tokens += len(encoding.encode(message.role))
                num_tokens += len(encoding.encode(message.content))
                if message.name:
                    num_tokens += tokens_per_name
                    num_tokens += len(encoding.encode(message.name))
            
            num_tokens += 3
            
            return num_tokens
            
        except Exception as e:
            raise LLMProviderError(f"Message token counting failed: {e}")
    
    def supports_functions(self) -> bool:
        """Check if the current model supports function calling.
        
        Returns:
            True if model supports function calling
        """
        return self._model_supports_functions
    
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
            "provider": "openai",
            "model": self.config.model,
            "supports_functions": self._model_supports_functions,
            "supports_vision": self._model_supports_vision,
        }
        
        context_windows = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4-turbo": 128000,
            "gpt-4-turbo-preview": 128000,
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-3.5-turbo": 16385,
            "gpt-3.5-turbo-16k": 16385,
        }
        
        model_info["max_context_tokens"] = context_windows.get(
            self.config.model, 8192
        )
        
        return model_info
    
    @property
    def provider_name(self) -> str:
        """Get the provider name.
        
        Returns:
            "openai"
        """
        return "openai"
    
    def _check_function_support(self) -> bool:
        """Check if the configured model supports function calling."""
        function_models = {
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4-turbo-preview",
            "gpt-4",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
        }
        
        for model in function_models:
            if self.config.model.startswith(model):
                return True
        
        return False
    
    def _check_vision_support(self) -> bool:
        """Check if the configured model supports vision."""
        vision_models = {
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4-vision-preview",
        }
        
        for model in vision_models:
            if self.config.model.startswith(model):
                return True
        
        return False
