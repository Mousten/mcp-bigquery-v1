# LLM Provider Layer Implementation Summary

## Overview

This implementation adds a comprehensive LLM provider abstraction layer to the mcp-bigquery project, enabling runtime selection between OpenAI and Anthropic providers through a unified interface.

## Implementation Details

### Package Structure

```
src/mcp_bigquery/llm/
├── __init__.py                      # Public API exports
├── factory.py                       # Provider factory and dependency injection
└── providers/
    ├── __init__.py                  # Provider exports
    ├── base.py                      # Abstract base class and interfaces
    ├── openai_provider.py           # OpenAI implementation
    └── anthropic_provider.py        # Anthropic implementation

tests/llm/
├── __init__.py
├── test_factory.py                  # Factory tests
└── providers/
    ├── __init__.py
    ├── test_base.py                 # Base models and interface tests
    ├── test_openai_provider.py      # OpenAI provider tests
    └── test_anthropic_provider.py   # Anthropic provider tests
```

### Core Components

#### 1. Base Abstractions (`providers/base.py`)

**Pydantic Models:**
- `Message`: Standard message format with role validation
- `ToolCall`: Represents tool/function call requests
- `ToolDefinition`: Defines available tools with JSON schema parameters
- `GenerationResponse`: Standardized LLM response with content, tool calls, and usage stats
- `LLMProviderConfig`: Base configuration with validation

**Abstract Interface (`LLMProvider`):**
- `async generate()`: Generate responses with optional tool calling
- `count_tokens()`: Count tokens in text
- `count_messages_tokens()`: Count tokens in message lists
- `supports_functions()`: Check function calling support
- `supports_vision()`: Check vision support
- `get_model_info()`: Get model metadata
- `provider_name`: Provider identifier property

**Custom Exceptions:**
- `LLMProviderError`: Base exception
- `LLMConfigurationError`: Configuration/initialization errors
- `LLMGenerationError`: Generation/API errors

#### 2. OpenAI Provider (`providers/openai_provider.py`)

**Features:**
- Uses official OpenAI SDK (v1.x) with AsyncOpenAI client
- Accurate token counting via `tiktoken` library
- Support for function calling with proper schema conversion
- Model capability detection (functions, vision)
- Context window information for various GPT models

**Configuration:**
- `OpenAIProviderConfig` extends base config
- Additional fields: `base_url`, `organization`
- Default model: `gpt-4o`

**Supported Models:**
- gpt-4o (128K context)
- gpt-4o-mini (128K context)
- gpt-4-turbo (128K context)
- gpt-4 (8K context)
- gpt-3.5-turbo (16K context)

#### 3. Anthropic Provider (`providers/anthropic_provider.py`)

**Features:**
- Uses official Anthropic SDK with AsyncAnthropic client
- Support for Claude's tool use feature
- System message handling (Anthropic-specific)
- Token counting with SDK utilities and fallback approximation
- Model capability detection

**Configuration:**
- `AnthropicProviderConfig` extends base config
- Additional field: `base_url`
- Default model: `claude-3-5-sonnet-20241022`
- Required field: `max_tokens` (must be set for Anthropic)

**Supported Models:**
- claude-3-5-sonnet-20241022 (200K context)
- claude-3-opus-20240229 (200K context)
- claude-3-sonnet-20240229 (200K context)
- claude-3-haiku-20240307 (200K context)

#### 4. Factory (`factory.py`)

**Functions:**
- `create_provider()`: Explicit provider creation with parameters
- `create_provider_from_env()`: Create from environment variables
- Private helpers: `_create_openai_provider()`, `_create_anthropic_provider()`

**Environment Variables:**
- `LLM_PROVIDER`: Provider type (default: "openai")
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `LLM_MODEL`: Model name override
- `LLM_TEMPERATURE`: Temperature (0-2)
- `LLM_MAX_TOKENS`: Max tokens to generate

## Test Coverage

### Statistics
- **Total Tests**: 71 (all passing)
- **Coverage**: 87-92% across all modules
  - `factory.py`: 88%
  - `anthropic_provider.py`: 92%
  - `base.py`: 90%
  - `openai_provider.py`: 87%

### Test Categories

1. **Base Models Tests** (`test_base.py`)
   - Pydantic model validation
   - Field validators
   - Exception hierarchy

2. **OpenAI Provider Tests** (`test_openai_provider.py`)
   - Configuration validation
   - Initialization success/failure
   - Generation with/without tool calls
   - Token counting (mocked tiktoken)
   - Capability checks
   - Error handling

3. **Anthropic Provider Tests** (`test_anthropic_provider.py`)
   - Configuration validation
   - Initialization success/failure
   - Generation with system messages
   - Tool use handling
   - Token counting with fallback
   - Capability checks

4. **Factory Tests** (`test_factory.py`)
   - Provider creation by type
   - Environment variable handling
   - API key validation
   - Interface consistency checks
   - Custom configuration

## Dependencies Added

Updated `pyproject.toml`:
```toml
"tiktoken>=0.5.0",  # Token counting for OpenAI
```

Existing dependencies used:
- `openai>=1.30.0`
- `anthropic>=0.32.0`
- `pydantic>=2.0.0`
- `pydantic-settings>=2.0.0`

## Usage Examples

### Basic Usage

```python
from mcp_bigquery.llm import create_provider, Message

# Create provider
provider = create_provider("openai", api_key="sk-...")

# Generate response
messages = [Message(role="user", content="Hello!")]
response = await provider.generate(messages)
print(response.content)
```

### Function Calling

```python
from mcp_bigquery.llm import ToolDefinition

tool = ToolDefinition(
    name="search",
    description="Search for information",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"]
    }
)

response = await provider.generate(messages, tools=[tool])
if response.has_tool_calls():
    for call in response.tool_calls:
        print(f"{call.name}({call.arguments})")
```

### Environment-Based Configuration

```python
from mcp_bigquery.llm import create_provider_from_env

# Reads LLM_PROVIDER, OPENAI_API_KEY, etc.
provider = create_provider_from_env()
```

## Acceptance Criteria Status

✅ **Provider Abstraction**: Consumers can request providers via factory and call `generate()` transparently

✅ **Structured Tool Calling**: Both providers support returning structured tool-call outputs

✅ **Token Counting**: Deterministic token counting validated in tests via mocks

✅ **Comprehensive Tests**: 71 unit tests covering instantiation, error handling, and feature parity

✅ **No Circular Dependencies**: Clean package structure with proper imports

✅ **Dependencies Updated**: `tiktoken` added to `pyproject.toml`

## Code Quality

- **Type Safety**: Full type hints with mypy compliance
- **Pydantic Validation**: All configs and models use Pydantic v2
- **Async/Await**: Fully asynchronous API
- **Error Handling**: Custom exceptions with informative messages
- **Documentation**: Comprehensive docstrings with Args/Returns/Raises
- **Testing**: Mock-based unit tests, no external API calls
- **Code Style**: Follows existing project conventions

## Known Issues

One pre-existing test failure in `tests/api/test_auth_endpoints.py::TestQueryAccessControl::test_query_with_authorized_table_proceeds` exists in the repository. This is unrelated to the LLM provider implementation:

```
RecursionError: maximum recursion depth exceeded while calling a Python object
```

This test was failing before any LLM provider code was added and is not affected by this implementation.

## Documentation

Created comprehensive documentation in `docs/llm_providers.md`:
- Feature overview
- Installation instructions
- Quick start guide
- Provider configuration details
- Advanced usage examples
- Function calling examples
- Token counting examples
- Error handling guide
- Provider interface specification
- Environment variables reference
- Testing guide
- Architecture overview
- Best practices
- Integration examples
- Extension guide for new providers

## Integration Points

The LLM provider layer is designed to be integrated with:
1. BigQuery query generation/optimization
2. SQL explanation and documentation
3. Agent orchestration for complex tasks
4. Natural language to SQL conversion
5. Schema understanding and recommendations

The abstraction allows easy switching between providers based on:
- Cost considerations
- Performance requirements
- Feature availability
- User preferences
- Organizational policies

## Future Enhancements

Potential areas for expansion:
1. Additional providers (Google Gemini, Cohere, etc.)
2. Streaming response support
3. Rate limiting and retry logic
4. Cost tracking and budgeting
5. Response caching
6. Batch processing support
7. Fine-tuned model support
8. Provider-specific optimizations
