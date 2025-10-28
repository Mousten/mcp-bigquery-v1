"""Factory for instantiating LLM providers based on configuration.

This module provides a factory function and dependency injection helper
for creating the appropriate LLM provider based on runtime configuration
(environment variables, user preferences, etc.).
"""

import os
from typing import Literal, Optional, Union

from .providers import (
    LLMProvider,
    LLMProviderConfig,
    LLMConfigurationError,
    OpenAIProvider,
    OpenAIProviderConfig,
    AnthropicProvider,
    AnthropicProviderConfig,
)


ProviderType = Literal["openai", "anthropic"]


def create_provider(
    provider_type: ProviderType,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    **kwargs,
) -> LLMProvider:
    """Create an LLM provider instance based on provider type.
    
    Args:
        provider_type: Type of provider to create ("openai" or "anthropic")
        api_key: API key for the provider (defaults to env var)
        model: Model name to use (defaults to provider's default)
        temperature: Sampling temperature (0-2, default varies by provider)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        **kwargs: Additional provider-specific configuration
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        LLMConfigurationError: If provider type is invalid or configuration fails
        
    Examples:
        >>> provider = create_provider("openai", api_key="sk-...")
        >>> provider = create_provider("anthropic", model="claude-3-opus-20240229")
    """
    provider_type_lower = provider_type.lower()
    
    if provider_type_lower == "openai":
        return _create_openai_provider(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
    elif provider_type_lower == "anthropic":
        return _create_anthropic_provider(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
    else:
        raise LLMConfigurationError(
            f"Unknown provider type: {provider_type}. "
            f"Supported providers: openai, anthropic"
        )


def _create_openai_provider(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    base_url: Optional[str] = None,
    organization: Optional[str] = None,
) -> OpenAIProvider:
    """Create an OpenAI provider instance.
    
    Args:
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        model: Model name (defaults to gpt-4o)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        timeout: Request timeout
        base_url: Custom base URL for API
        organization: OpenAI organization ID
        
    Returns:
        Configured OpenAI provider
        
    Raises:
        LLMConfigurationError: If API key is missing or invalid
    """
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise LLMConfigurationError(
            "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
            "or pass api_key parameter."
        )
    
    config_params = {
        "api_key": resolved_api_key,
    }
    
    if model:
        config_params["model"] = model
    if temperature is not None:
        config_params["temperature"] = temperature
    if max_tokens is not None:
        config_params["max_tokens"] = max_tokens
    if timeout is not None:
        config_params["timeout"] = timeout
    if base_url:
        config_params["base_url"] = base_url
    if organization:
        config_params["organization"] = organization
    
    config = OpenAIProviderConfig(**config_params)
    return OpenAIProvider(config)


def _create_anthropic_provider(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    base_url: Optional[str] = None,
) -> AnthropicProvider:
    """Create an Anthropic provider instance.
    
    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Model name (defaults to claude-3-5-sonnet-20241022)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        timeout: Request timeout
        base_url: Custom base URL for API
        
    Returns:
        Configured Anthropic provider
        
    Raises:
        LLMConfigurationError: If API key is missing or invalid
    """
    resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not resolved_api_key:
        raise LLMConfigurationError(
            "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable "
            "or pass api_key parameter."
        )
    
    config_params = {
        "api_key": resolved_api_key,
    }
    
    if model:
        config_params["model"] = model
    if temperature is not None:
        config_params["temperature"] = temperature
    if max_tokens is not None:
        config_params["max_tokens"] = max_tokens
    if timeout is not None:
        config_params["timeout"] = timeout
    if base_url:
        config_params["base_url"] = base_url
    
    config = AnthropicProviderConfig(**config_params)
    return AnthropicProvider(config)


def create_provider_from_env(
    provider_env_var: str = "LLM_PROVIDER",
    default_provider: ProviderType = "openai",
) -> LLMProvider:
    """Create a provider based on environment variable configuration.
    
    Args:
        provider_env_var: Name of environment variable for provider type
        default_provider: Default provider if env var not set
        
    Returns:
        Configured LLM provider instance
        
    Raises:
        LLMConfigurationError: If provider configuration fails
        
    Environment Variables:
        LLM_PROVIDER: Provider type ("openai" or "anthropic")
        OPENAI_API_KEY: OpenAI API key
        ANTHROPIC_API_KEY: Anthropic API key
        LLM_MODEL: Optional model name override
        LLM_TEMPERATURE: Optional temperature override
        LLM_MAX_TOKENS: Optional max tokens override
        
    Examples:
        >>> os.environ["LLM_PROVIDER"] = "anthropic"
        >>> provider = create_provider_from_env()
    """
    provider_type_str = os.getenv(provider_env_var, default_provider)
    
    if provider_type_str not in ("openai", "anthropic"):
        raise LLMConfigurationError(
            f"Invalid provider type in {provider_env_var}: {provider_type_str}"
        )
    
    provider_type = provider_type_str  # type: ignore
    
    model = os.getenv("LLM_MODEL")
    temperature_str = os.getenv("LLM_TEMPERATURE")
    max_tokens_str = os.getenv("LLM_MAX_TOKENS")
    
    temperature = float(temperature_str) if temperature_str else None
    max_tokens = int(max_tokens_str) if max_tokens_str else None
    
    return create_provider(
        provider_type=provider_type,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
