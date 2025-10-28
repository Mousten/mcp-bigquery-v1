"""LLM provider abstraction layer.

This package provides an extensible interface for interacting with different
LLM providers (OpenAI, Anthropic, etc.) through a unified API. It enables
provider selection at runtime and abstracts provider-specific implementation
details.

Usage:
    from mcp_bigquery.llm import create_provider, Message
    
    # Create a provider explicitly
    provider = create_provider("openai", api_key="sk-...")
    
    # Or use environment variables
    provider = create_provider_from_env()
    
    # Generate a response
    messages = [Message(role="user", content="Hello!")]
    response = await provider.generate(messages)
    print(response.content)
"""

from .factory import (
    create_provider,
    create_provider_from_env,
    ProviderType,
)
from .providers import (
    LLMProvider,
    LLMProviderConfig,
    LLMProviderError,
    LLMConfigurationError,
    LLMGenerationError,
    Message,
    GenerationResponse,
    ToolCall,
    ToolDefinition,
    OpenAIProvider,
    OpenAIProviderConfig,
    AnthropicProvider,
    AnthropicProviderConfig,
)

__all__ = [
    "create_provider",
    "create_provider_from_env",
    "ProviderType",
    "LLMProvider",
    "LLMProviderConfig",
    "LLMProviderError",
    "LLMConfigurationError",
    "LLMGenerationError",
    "Message",
    "GenerationResponse",
    "ToolCall",
    "ToolDefinition",
    "OpenAIProvider",
    "OpenAIProviderConfig",
    "AnthropicProvider",
    "AnthropicProviderConfig",
]
