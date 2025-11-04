"""Abstract base class for LLM providers.

This module defines the interface that all LLM providers must implement,
enabling consistent interaction with different LLM services (OpenAI, Anthropic, etc.)
while abstracting provider-specific details.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMConfigurationError(LLMProviderError):
    """Raised when provider is misconfigured (e.g., missing API keys)."""
    pass


class LLMGenerationError(LLMProviderError):
    """Raised when generation fails (e.g., API errors, invalid parameters)."""
    pass


class Message(BaseModel):
    """Standard message format for LLM interactions."""
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List['ToolCall']] = None
    tool_call_id: Optional[str] = None
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is one of the allowed values."""
        allowed_roles = {"system", "user", "assistant", "function", "tool"}
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}, got: {v}")
        return v


class ToolCall(BaseModel):
    """Represents a tool/function call request from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    """Standardized response from LLM generation."""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    raw_response: Optional[Any] = None
    
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


class ToolDefinition(BaseModel):
    """Definition of a tool/function available to the LLM."""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters is a valid JSON schema."""
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a dictionary")
        return v


class LLMProviderConfig(BaseModel):
    """Base configuration for LLM providers."""
    api_key: str
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    timeout: float = Field(default=60.0, gt=0)
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key is not empty."""
        if not v or not v.strip():
            raise ValueError("API key cannot be empty")
        return v.strip()


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    All concrete provider implementations must implement this interface
    to ensure consistent behavior and easy provider swapping.
    """
    
    def __init__(self, config: LLMProviderConfig):
        """Initialize the provider with configuration.
        
        Args:
            config: Provider-specific configuration
            
        Raises:
            LLMConfigurationError: If configuration is invalid
        """
        self.config = config
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> GenerationResponse:
        """Generate a response from the LLM.
        
        Args:
            messages: List of conversation messages
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional provider-specific parameters
            
        Returns:
            GenerationResponse with the LLM's output
            
        Raises:
            LLMGenerationError: If generation fails
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens in the given text.
        
        Args:
            text: Text to count tokens for
            model: Optional model name to use for counting (defaults to config.model)
            
        Returns:
            Number of tokens in the text
            
        Raises:
            LLMProviderError: If token counting fails
        """
        pass
    
    @abstractmethod
    def count_messages_tokens(
        self,
        messages: List[Message],
        model: Optional[str] = None
    ) -> int:
        """Count tokens in a list of messages.
        
        Args:
            messages: List of messages to count tokens for
            model: Optional model name to use for counting (defaults to config.model)
            
        Returns:
            Total number of tokens in all messages
            
        Raises:
            LLMProviderError: If token counting fails
        """
        pass
    
    @abstractmethod
    def supports_functions(self) -> bool:
        """Check if provider supports function/tool calling.
        
        Returns:
            True if provider supports function calling, False otherwise
        """
        pass
    
    @abstractmethod
    def supports_vision(self) -> bool:
        """Check if provider supports vision/image inputs.
        
        Returns:
            True if provider supports vision, False otherwise
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model.
        
        Returns:
            Dictionary with model metadata (max_tokens, cost, etc.)
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of the provider.
        
        Returns:
            Provider name (e.g., "openai", "anthropic")
        """
        pass
