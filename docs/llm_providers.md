# LLM Provider Layer

The LLM provider layer provides an extensible abstraction for interacting with different Large Language Model (LLM) services through a unified interface. Currently supports OpenAI and Anthropic providers.

## Features

- **Unified Interface**: Interact with different LLM providers through a consistent API
- **Provider Selection**: Choose providers at runtime via configuration or environment variables
- **Function/Tool Calling**: Support for structured function calling across providers
- **Token Counting**: Accurate token counting for cost estimation and limit management
- **Type Safety**: Full Pydantic validation and type hints throughout
- **Async/Await**: Fully asynchronous API for efficient I/O operations

## Installation

The required dependencies are already included in the project:

```bash
uv sync
```

Dependencies:
- `openai>=1.30.0` - OpenAI SDK
- `anthropic>=0.32.0` - Anthropic SDK  
- `tiktoken>=0.5.0` - Token counting for OpenAI
- `pydantic>=2.0.0` - Data validation

## Quick Start

### Basic Usage

```python
from mcp_bigquery.llm import create_provider, Message

# Create a provider
provider = create_provider("openai", api_key="sk-...")

# Generate a response
messages = [Message(role="user", content="Hello!")]
response = await provider.generate(messages)
print(response.content)
```

### Using Environment Variables

```python
import os
from mcp_bigquery.llm import create_provider_from_env

# Set environment variables
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
os.environ["LLM_MODEL"] = "claude-3-opus-20240229"
os.environ["LLM_TEMPERATURE"] = "0.7"

# Create provider from environment
provider = create_provider_from_env()
```

## Provider Configuration

### OpenAI Provider

```python
from mcp_bigquery.llm import OpenAIProvider, OpenAIProviderConfig

config = OpenAIProviderConfig(
    api_key="sk-...",
    model="gpt-4o",
    temperature=0.7,
    max_tokens=1000,
    timeout=60.0,
    base_url=None,  # Optional custom base URL
    organization=None,  # Optional organization ID
)

provider = OpenAIProvider(config)
```

Supported models:
- `gpt-4o` (default)
- `gpt-4o-mini`
- `gpt-4-turbo`
- `gpt-4`
- `gpt-3.5-turbo`

### Anthropic Provider

```python
from mcp_bigquery.llm import AnthropicProvider, AnthropicProviderConfig

config = AnthropicProviderConfig(
    api_key="sk-ant-...",
    model="claude-3-5-sonnet-20241022",
    temperature=0.7,
    max_tokens=4096,
    timeout=60.0,
    base_url=None,  # Optional custom base URL
)

provider = AnthropicProvider(config)
```

Supported models:
- `claude-3-5-sonnet-20241022` (default)
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

## Advanced Usage

### Function/Tool Calling

```python
from mcp_bigquery.llm import Message, ToolDefinition

# Define a tool
weather_tool = ToolDefinition(
    name="get_weather",
    description="Get current weather for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"]
            }
        },
        "required": ["location"]
    }
)

# Generate with tools
messages = [Message(role="user", content="What's the weather in Paris?")]
response = await provider.generate(messages, tools=[weather_tool])

# Check for tool calls
if response.has_tool_calls():
    for tool_call in response.tool_calls:
        print(f"Tool: {tool_call.name}")
        print(f"Arguments: {tool_call.arguments}")
```

### Token Counting

```python
# Count tokens in text
count = provider.count_tokens("Hello, world!")
print(f"Tokens: {count}")

# Count tokens in messages
messages = [
    Message(role="system", content="You are a helpful assistant"),
    Message(role="user", content="Hello!"),
]
total_tokens = provider.count_messages_tokens(messages)
print(f"Total tokens: {total_tokens}")
```

### Checking Capabilities

```python
# Check if provider supports function calling
if provider.supports_functions():
    print("Provider supports function calling")

# Check if provider supports vision
if provider.supports_vision():
    print("Provider supports vision inputs")

# Get model information
info = provider.get_model_info()
print(f"Provider: {info['provider']}")
print(f"Model: {info['model']}")
print(f"Max context: {info['max_context_tokens']} tokens")
```

### Multi-turn Conversations

```python
from mcp_bigquery.llm import Message

conversation = [
    Message(role="system", content="You are a helpful SQL expert"),
    Message(role="user", content="How do I join two tables?"),
]

response = await provider.generate(conversation)
print(response.content)

# Continue the conversation
conversation.append(Message(role="assistant", content=response.content))
conversation.append(Message(role="user", content="Can you show me an example?"))

response = await provider.generate(conversation)
print(response.content)
```

## Factory Pattern

The factory provides flexible provider instantiation:

```python
from mcp_bigquery.llm import create_provider

# Explicit creation
provider = create_provider(
    "openai",
    api_key="sk-...",
    model="gpt-4o",
    temperature=0.5
)

# From environment variables
provider = create_provider_from_env()

# Custom environment variable names
provider = create_provider_from_env(
    provider_env_var="MY_PROVIDER",
    default_provider="anthropic"
)
```

## Error Handling

The module defines specific exceptions for different error cases:

```python
from mcp_bigquery.llm.providers import (
    LLMProviderError,
    LLMConfigurationError,
    LLMGenerationError,
)

try:
    provider = create_provider("openai", api_key="")
except LLMConfigurationError as e:
    print(f"Configuration error: {e}")

try:
    response = await provider.generate(messages)
except LLMGenerationError as e:
    print(f"Generation error: {e}")
```

## Provider Interface

All providers implement the `LLMProvider` abstract base class:

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> GenerationResponse:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens in text."""
        pass
    
    @abstractmethod
    def count_messages_tokens(
        self,
        messages: List[Message],
        model: Optional[str] = None
    ) -> int:
        """Count tokens in messages."""
        pass
    
    @abstractmethod
    def supports_functions(self) -> bool:
        """Check if provider supports function calling."""
        pass
    
    @abstractmethod
    def supports_vision(self) -> bool:
        """Check if provider supports vision."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Provider type (`openai` or `anthropic`) | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | None |
| `ANTHROPIC_API_KEY` | Anthropic API key | None |
| `LLM_MODEL` | Model name override | Provider default |
| `LLM_TEMPERATURE` | Temperature (0-2) | 0.7 |
| `LLM_MAX_TOKENS` | Max tokens to generate | None |

## Testing

The module includes comprehensive unit tests with mocked API calls:

```bash
# Run all LLM tests
uv run pytest tests/llm/ -v

# Run with coverage
uv run pytest tests/llm/ --cov=src/mcp_bigquery/llm --cov-report=term-missing
```

Test coverage:
- Provider instantiation and configuration
- Generation with and without tool calls
- Token counting accuracy
- Error handling for missing API keys
- Interface compliance across providers
- Factory routing and environment variable handling

## Architecture

```
mcp_bigquery/llm/
├── __init__.py              # Public API exports
├── factory.py               # Provider factory and DI helpers
└── providers/
    ├── __init__.py          # Provider exports
    ├── base.py              # Abstract base class and interfaces
    ├── openai_provider.py   # OpenAI implementation
    └── anthropic_provider.py # Anthropic implementation
```

## Best Practices

1. **Use Environment Variables**: Store API keys in environment variables, not in code
2. **Token Counting**: Always count tokens before making API calls to avoid exceeding limits
3. **Error Handling**: Catch specific exceptions for better error messages
4. **Async/Await**: Use async context for all generation calls
5. **Tool Definitions**: Use detailed descriptions in tool definitions for better results
6. **Temperature**: Lower temperature (0.0-0.3) for deterministic outputs, higher (0.7-1.0) for creative tasks

## Integration Example

```python
import os
from mcp_bigquery.llm import create_provider_from_env, Message, ToolDefinition

async def chat_with_llm(user_message: str) -> str:
    """Simple chat function using LLM provider."""
    # Create provider from environment
    provider = create_provider_from_env()
    
    # Create messages
    messages = [
        Message(role="system", content="You are a helpful BigQuery expert"),
        Message(role="user", content=user_message)
    ]
    
    # Count tokens first
    token_count = provider.count_messages_tokens(messages)
    print(f"Input tokens: {token_count}")
    
    # Generate response
    response = await provider.generate(messages)
    
    # Return content
    return response.content or ""

# Usage
result = await chat_with_llm("How do I optimize a BigQuery query?")
print(result)
```

## Extending with New Providers

To add a new provider:

1. Create a new config class extending `LLMProviderConfig`
2. Implement the `LLMProvider` interface
3. Add provider creation logic to `factory.py`
4. Write comprehensive unit tests with mocks
5. Update documentation

Example skeleton:

```python
from .base import LLMProvider, LLMProviderConfig

class MyProviderConfig(LLMProviderConfig):
    model: str = "default-model"
    # Add provider-specific fields

class MyProvider(LLMProvider):
    def __init__(self, config: MyProviderConfig):
        super().__init__(config)
        # Initialize SDK client
    
    async def generate(self, messages, tools=None, **kwargs):
        # Implement generation logic
        pass
    
    # Implement other abstract methods
    ...
```
