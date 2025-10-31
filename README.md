# MCP BigQuery Server

A FastMCP server for securely accessing Google BigQuery with conversational AI capabilities, comprehensive authentication, and a business-friendly Streamlit UI.

## Features

### Core Capabilities
- **🔍 BigQuery Access**: Read-only access to datasets, tables, and query execution
- **🤖 Conversational AI**: Natural language queries powered by OpenAI, Anthropic, or Google Gemini
- **🔐 Authentication & RBAC**: JWT-based auth with role-based access control via Supabase
- **💬 Chat Persistence**: Multi-session conversations with history tracking
- **📊 Visualizations**: Auto-generated chart suggestions based on query results
- **⚡ Performance**: Query caching, result summarization, and intelligent rate limiting
- **💰 Token Accounting**: Comprehensive token tracking with configurable quotas per user
- **🌐 Multiple Transports**: HTTP, SSE, stdio, and HTTP-stream modes

### Streamlit UI
- **🎨 User-Friendly Interface**: Chat-based UI for non-technical users
- **🔒 Secure Login**: Email/password and magic link authentication
- **💡 Interactive Insights**: Live charts, tables, and data exports
- **🗂️ Session Management**: Create, rename, and manage conversation sessions
- **📈 Real-time Updates**: Streaming responses with progress indicators
- **🎛️ Provider Selection**: Choose LLM provider at runtime (OpenAI, Anthropic, Gemini)

## Quick Start

### Prerequisites
- Python 3.10+
- Google Cloud project with BigQuery enabled
- Service account key with BigQuery read permissions
- Supabase project (for auth and persistence)
- OpenAI, Anthropic, or Google API key (for AI features)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mcp-bigquery-server

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:

```bash
# ========================================
# BigQuery Configuration (Required)
# ========================================
PROJECT_ID=your-gcp-project-id          # Google Cloud project ID
LOCATION=US                              # BigQuery location (default: US)
KEY_FILE=path/to/service-account-key.json  # Service account key file

# ========================================
# Supabase Configuration (Required)
# ========================================
SUPABASE_URL=https://your-project.supabase.co  # Supabase project URL
SUPABASE_KEY=your-anon-key                      # Supabase anonymous key
SUPABASE_SERVICE_KEY=your-service-role-key      # Service role key (for RBAC and RLS bypass)
SUPABASE_JWT_SECRET=your-jwt-secret             # JWT secret for token validation

# ========================================
# LLM Provider Configuration (Required)
# ========================================
LLM_PROVIDER=openai                      # Provider: "openai", "anthropic", or "gemini"
LLM_MODEL=gpt-4o                         # Optional: Override default model
LLM_TEMPERATURE=0.7                      # Optional: Temperature (0-2)
LLM_MAX_TOKENS=                          # Optional: Max tokens to generate

# API Keys (based on provider choice)
OPENAI_API_KEY=sk-...                    # Required if using OpenAI
ANTHROPIC_API_KEY=sk-ant-...             # Required if using Anthropic
GOOGLE_API_KEY=...                       # Required if using Gemini

# ========================================
# Streamlit App Configuration (Optional)
# ========================================
MCP_BASE_URL=http://localhost:8000       # MCP server base URL
STREAMLIT_APP_URL=http://localhost:8501  # Streamlit app URL for magic link redirects
ENABLE_RATE_LIMITING=true                # Enable rate limiting
ENABLE_CACHING=true                      # Enable response caching
MAX_CONTEXT_TURNS=5                      # Max conversation turns in context
APP_TITLE=BigQuery Insights              # Application title
APP_ICON=📊                              # Application icon emoji
```

See [Environment Variables Reference](#environment-variables-reference) below for complete details.

### Supabase Setup

The MCP BigQuery Server requires a Supabase project for authentication, RBAC, chat persistence, caching, and usage tracking.

#### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note your project URL and API keys from the Settings > API page
3. Find your JWT secret in Settings > API > JWT Settings

#### 2. Run Database Schema

Execute the complete schema SQL to create all required tables:

```bash
# Option 1: Using Supabase SQL Editor (recommended)
# - Go to SQL Editor in Supabase dashboard
# - Create new query and paste contents of docs/supabase_complete_schema.sql
# - Run the query

# Option 2: Using psql
psql -h db.your-project.supabase.co -U postgres -d postgres -f docs/supabase_complete_schema.sql
```

The schema creates the following tables:

**RBAC Tables:**
- `user_profiles` - Extended user profile data
- `app_roles` - Application roles (analyst, admin, viewer)
- `user_roles` - User-to-role assignments
- `role_permissions` - Role permissions (query:execute, cache:read, etc.)
- `role_dataset_access` - Dataset/table access control per role

**Chat Persistence Tables:**
- `chat_sessions` - Conversation sessions with titles
- `chat_messages` - Individual messages within sessions

**Caching Tables:**
- `query_cache` - Cached BigQuery query results (user-scoped)
- `metadata_cache` - Cached BigQuery metadata (schemas, datasets)

**Usage Tracking Tables:**
- `user_usage_stats` - Daily token consumption and request counts
- `user_preferences` - User preferences including token quotas

All tables include Row Level Security (RLS) policies for data isolation.

#### 3. Configure Initial Roles (Optional)

Uncomment and run the sample data section in `docs/supabase_complete_schema.sql` to create default roles:
- **analyst** - Full query execution and caching
- **viewer** - Read-only schema access
- **admin** - Full access with cache invalidation

#### 4. Assign User Roles

After users sign up, assign them roles:

```sql
-- Assign analyst role to a user
INSERT INTO user_roles (user_id, role_id, role_name) 
VALUES ('user-123-from-auth-users', 'role-analyst', 'analyst');

-- Set user token quotas (optional)
INSERT INTO user_preferences (user_id, preferences)
VALUES ('user-123-from-auth-users', '{"daily_token_quota": 10000, "monthly_token_quota": 100000}');
```

See [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md) for complete database setup guide with ERD and detailed table descriptions, and [docs/AUTH.md](docs/AUTH.md) for authentication and RBAC configuration.

### Running the MCP Server

```bash
# HTTP mode (for REST API access)
uv run mcp-bigquery --transport http --port 8000

# HTTP-stream mode (recommended for Streamlit)
uv run mcp-bigquery --transport http-stream --port 8000

# SSE mode (for event streaming)
uv run mcp-bigquery --transport sse --port 8000

# Stdio mode (for MCP protocol clients)
uv run mcp-bigquery --transport stdio
```

### Running the Streamlit UI

In a separate terminal:

```bash
# Start the Streamlit app
streamlit run streamlit_app/app.py

# Or with uv
uv run streamlit run streamlit_app/app.py
```

The UI will open at `http://localhost:8501`.

## Usage

### Streamlit UI (Recommended for Business Users)

1. **Sign In**: Use email/password or magic link authentication
2. **Start Chatting**: Ask questions in natural language
3. **View Results**: See tables, charts, and insights
4. **Manage Sessions**: Create, rename, and organize conversations

Example questions:
- "What are the top 10 products by revenue?"
- "Show me daily sales trends for the last 30 days"
- "Which customers have the highest lifetime value?"
- "Compare revenue across different regions"

**Authentication**:
- **Email/Password**: Traditional sign-in method
- **Magic Link**: Passwordless authentication via email link

See [docs/streamlit.md](docs/streamlit.md) for detailed UI documentation and [streamlit_app/MAGIC_LINK_SETUP.md](streamlit_app/MAGIC_LINK_SETUP.md) for magic link authentication setup.

### REST API

For programmatic access, use the REST API endpoints:

```bash
# Get health status
curl http://localhost:8000/stream/health

# List datasets (requires authentication)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/stream/datasets

# Execute SQL query
curl -X POST http://localhost:8000/stream/execute_sql \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM dataset.table LIMIT 10"}'

# List chat sessions
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/stream/chat/sessions
```

### Python Client

Use the included Python client for programmatic access:

```python
from mcp_bigquery.client import MCPClient, ClientConfig
from mcp_bigquery.agent import ConversationManager, AgentRequest

# Configure client
config = ClientConfig(
    base_url="http://localhost:8000",
    auth_token="your-jwt-token"
)

# Execute queries
async with MCPClient(config) as client:
    result = await client.execute_sql("SELECT * FROM dataset.table LIMIT 10")
    print(result)

# Use conversational agent
manager = ConversationManager(
    mcp_client=client,
    kb=knowledge_base,
    project_id="my-project",
    provider_type="openai"
)

request = AgentRequest(
    question="What are the top products?",
    session_id="session-123",
    user_id="user-456",
    allowed_datasets={"sales"}
)

response = await manager.process_conversation(request)
print(response.answer)
```

See [src/mcp_bigquery/client/README.md](src/mcp_bigquery/client/README.md) for full client documentation.

## Architecture

### System Overview

The MCP BigQuery Server follows a layered architecture with clear separation between the user interface, business logic, and data access:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI                             │
│              (Business User Interface Layer)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │     Auth     │  │  Chat UI     │  │  Insights & Charts   │ │
│  │   Component  │  │  Component   │  │     Component        │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP BigQuery Server                          │
│                    (Business Logic Layer)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Routes (HTTP/SSE/HTTP-stream endpoints)         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Conversation │  │     LLM      │  │   BigQuery Handler   │ │
│  │   Manager    │──│  Providers   │──│   (SQL Execution)    │ │
│  │ (Orchestrate)│  │ (Multi-LLM)  │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Rate Limiter │  │    Caching   │  │   Auth & RBAC        │ │
│  │ (Token Quota)│  │    Layer     │  │   (JWT + RLS)        │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌────────────────────┐                    ┌──────────────────────┐
│   Google BigQuery  │                    │      Supabase        │
│  (Data Warehouse)  │                    │  (Backend Services)  │
│  - Datasets        │                    │  - Authentication    │
│  - Tables          │                    │  - RBAC Tables       │
│  - SQL Execution   │                    │  - Chat History      │
└────────────────────┘                    │  - Query Cache       │
                                          │  - Usage Tracking    │
                                          │  - User Preferences  │
                                          └──────────────────────┘
```

### Key Components

**1. Streamlit UI (`streamlit_app/`)**
- User authentication (email/password, magic link)
- Chat interface with session management
- Real-time streaming responses
- Chart visualizations and data exports
- Provider selection dropdown (OpenAI, Anthropic, Gemini)

**2. MCP Server (`src/mcp_bigquery/`)**
- **`api/`**: FastAPI and MCP app setup with multiple transports
- **`routes/`**: REST API endpoints for datasets, queries, and chat
- **`agent/`**: Conversational AI orchestration
  - `conversation_manager.py` - Rate limiting, token tracking, context management
  - `conversation.py` - InsightsAgent for SQL generation and explanation
  - `mcp_client.py` - BigQuery operations client
  - `summarizer.py` - Result summarization for large datasets
- **`llm/`**: LLM provider integrations
  - `providers/openai_provider.py` - OpenAI GPT models
  - `providers/anthropic_provider.py` - Anthropic Claude models
  - `providers/gemini_provider.py` - Google Gemini models
  - `factory.py` - Provider selection and instantiation
- **`core/`**: Core infrastructure
  - `bigquery_client.py` - BigQuery SDK wrapper
  - `supabase_client.py` - Supabase operations (cache, chat, RBAC, usage)
  - `auth.py` - JWT validation and RBAC enforcement
  - `json_encoder.py` - Custom JSON encoding for BigQuery types
- **`handlers/`**: Business logic for BigQuery operations
- **`events/`**: Event management and logging

**3. Data Layer**
- **BigQuery**: Source of truth for analytics data
- **Supabase**: Backend services for auth, persistence, and control

## LLM Provider Selection

The server supports multiple LLM providers with runtime selection and a unified interface.

### Supported Providers

| Provider | Models | Function Calling | Vision | Token Counting |
|----------|--------|------------------|--------|----------------|
| **OpenAI** | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo | ✅ | ✅ | ✅ (tiktoken) |
| **Anthropic** | claude-3-5-sonnet, claude-3-opus, claude-3-sonnet, claude-3-haiku | ✅ | ✅ | ✅ (builtin) |
| **Google Gemini** | gemini-1.5-pro, gemini-1.5-flash | ✅ | ✅ | ✅ (builtin) |

### Configuration

Set the provider via environment variables:

```bash
# Choose provider
LLM_PROVIDER=openai  # or "anthropic", "gemini"

# Set corresponding API key
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Optional: Override default model
LLM_MODEL=gpt-4o  # or "claude-3-5-sonnet-20241022", "gemini-1.5-pro"
```

### Runtime Selection (Streamlit UI)

Users can select providers dynamically in the Streamlit UI:

1. Open the sidebar in the Streamlit app
2. Use the "LLM Provider" dropdown to select OpenAI, Anthropic, or Gemini
3. Optionally override the model using the "Model Override" input
4. Token usage is tracked per provider/model combination

### Adding New Providers

To add a new LLM provider:

1. Implement the `LLMProvider` interface in `src/mcp_bigquery/llm/providers/`
2. Add factory logic in `src/mcp_bigquery/llm/factory.py`
3. Update `create_provider()` function to handle the new provider type
4. Write unit tests with mocked API calls

See [docs/llm_providers.md](docs/llm_providers.md) for detailed implementation guide.

## Caching Strategy

The server implements multi-layer caching to reduce costs and improve performance.

### Cache Types

**1. Query Result Cache**
- Caches BigQuery query results in Supabase
- User-scoped for security (never shared across users)
- Configurable TTL (default: 24 hours)
- Tracks hit counts and last access time

**2. Metadata Cache**
- Caches dataset and table schemas
- Shared across users (read-only metadata)
- Longer TTL (default: 1 hour)
- Reduces BigQuery API calls

**3. LLM Response Cache**
- Caches LLM responses for identical prompts
- Cache key includes prompt, provider, model, temperature
- Reduces token consumption by 30-50%
- Automatic cache invalidation on context changes

### Configuration

```bash
# Enable/disable caching
ENABLE_CACHING=true

# In Streamlit UI
# Toggle caching in sidebar settings
```

### Monitoring Cache Performance

```python
# Get cache statistics (admin endpoint)
GET /admin/cache/stats

# Response:
{
  "query_cache": {
    "total_entries": 1234,
    "total_hits": 5678,
    "hit_rate": 0.82
  },
  "metadata_cache": {
    "total_entries": 45,
    "hit_rate": 0.95
  }
}
```

### Cache Invalidation

```bash
# Clear user's query cache
DELETE /cache/user/{user_id}

# Clear specific query cache
DELETE /cache/query/{query_hash}

# Admin: Clear all caches
DELETE /admin/cache/all
```

## Rate Limiting & Token Accounting

The server enforces token quotas to control costs and prevent abuse.

### Token Tracking

**Per-Request Tracking:**
- Input tokens (prompt + context)
- Output tokens (LLM response)
- Total tokens per conversation turn
- Provider and model used

**Aggregation:**
- Daily statistics per user
- Monthly rollups for billing
- Per-provider/model breakdown
- Success/failure tracking

### Quota Configuration

Set quotas per user in the `user_preferences` table:

```sql
-- Set daily and monthly quotas
INSERT INTO user_preferences (user_id, preferences)
VALUES ('user-id', '{
  "daily_token_quota": 10000,
  "monthly_token_quota": 100000
}');

-- View user's current usage
SELECT * FROM user_usage_stats 
WHERE user_id = 'user-id' 
ORDER BY period_start DESC;
```

### Rate Limit Enforcement

The `ConversationManager` checks quotas before processing:

1. User submits question
2. Check daily/monthly quota
3. If over quota, return error response
4. Otherwise, process request
5. Record token usage

**Error Response:**
```json
{
  "error": "Daily token quota exceeded",
  "error_type": "rate_limit",
  "metadata": {
    "quota_limit": 10000,
    "tokens_used": 10234,
    "remaining": 0,
    "quota_period": "daily"
  }
}
```

### Monitoring Usage

**User Dashboard:**
```python
# Get user's token usage statistics
GET /usage/stats?days=30

# Response:
{
  "total_tokens": 45678,
  "total_requests": 123,
  "daily_breakdown": [...],
  "provider_breakdown": {
    "openai": {
      "gpt-4o": {"tokens": 30000, "requests": 80},
      "gpt-4o-mini": {"tokens": 15678, "requests": 43}
    }
  }
}
```

**Admin Dashboard:**
```python
# Get aggregate usage across all users
GET /admin/usage/aggregate?days=30
```

### Cost Estimation

Typical token usage per conversation turn:
- **Input**: 500-2000 tokens (question + context + schema)
- **Output**: 200-800 tokens (answer + SQL + explanation)
- **Total**: ~700-2800 tokens per turn

With caching and summarization:
- **Cache hit rate**: 30-50%
- **Context reduction**: 70% (via summarization)
- **Result reduction**: 90% (for large datasets)
- **Effective cost**: ~30-40% of uncached cost

## Documentation

### User Guides
- **[Streamlit Quick Start](docs/STREAMLIT_QUICKSTART.md)**: Get started with the UI in minutes ⚡
- **[Streamlit UI Guide](docs/streamlit.md)**: Complete UI documentation with setup, usage, and deployment

### Setup & Configuration
- **[Database Setup](docs/DATABASE_SETUP.md)**: Comprehensive Supabase schema guide with ERD and table descriptions
- **[Authentication & RBAC](docs/AUTH.md)**: JWT validation, role-based access control, and user management

### API & Integration
- **[Python Client Library](src/mcp_bigquery/client/README.md)**: Client API reference for programmatic access
- **[Chat Persistence API](docs/CHAT_PERSISTENCE.md)**: Session and message management endpoints
- **[MCP Client](docs/MCP_CLIENT.md)**: MCP protocol client documentation

### Architecture & Implementation
- **[LLM Providers](docs/llm_providers.md)**: Multi-provider abstraction, configuration, and extension guide
- **[Conversation Manager](docs/conversation_manager.md)**: Agent orchestration, rate limiting, and context management
- **[Agent Implementation](AGENT_IMPLEMENTATION_SUMMARY.md)**: Insights agent implementation details
- **[Conversation Manager Implementation](CONVERSATION_MANAGER_IMPLEMENTATION.md)**: Deep dive into orchestration layer

## Development

### Project Structure

```
.
├── streamlit_app/           # Streamlit UI application
│   ├── app.py              # Main entry point
│   ├── auth.py             # Authentication UI
│   ├── chat_ui.py          # Chat interface
│   ├── config.py           # Configuration
│   ├── insights_ui.py      # Visualizations
│   ├── session_manager.py  # Session persistence
│   └── utils.py            # Utilities
├── src/mcp_bigquery/       # Core server
│   ├── agent/              # Conversational AI
│   ├── api/                # FastAPI/MCP apps
│   ├── client/             # Python client
│   ├── config/             # Configuration
│   ├── core/               # Core modules
│   ├── events/             # Event management
│   ├── handlers/           # Business logic
│   ├── llm/                # LLM providers
│   ├── routes/             # API routes
│   └── main.py             # Server entry point
├── tests/                  # Test suite
├── docs/                   # Documentation
├── examples/               # Usage examples
└── pyproject.toml          # Dependencies
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src/mcp_bigquery --cov-report=term-missing

# Run specific test file
uv run pytest tests/agent/test_conversation_manager.py -v

# Run integration tests
uv run pytest tests/ -v -m integration
```

### Code Quality

```bash
# Format code
uv run black src/ tests/ streamlit_app/

# Sort imports
uv run isort src/ tests/ streamlit_app/

# Type checking
uv run mypy src/ streamlit_app/

# Linting
uv run flake8 src/ tests/ streamlit_app/
```

## Deployment

### Streamlit Cloud

1. Push to GitHub
2. Connect to Streamlit Cloud
3. Add secrets (environment variables)
4. Deploy

### Docker

```bash
# Build image
docker build -t mcp-bigquery-server .

# Run server
docker run -p 8000:8000 --env-file .env mcp-bigquery-server

# Run Streamlit (separate container)
docker run -p 8501:8501 --env-file .env \
  mcp-bigquery-server streamlit run streamlit_app/app.py
```

### Cloud Run

Deploy as two services:
1. MCP BigQuery Server (backend)
2. Streamlit UI (frontend)

Configure internal networking for server-to-server communication.

## Security

- **Authentication**: JWT-based with automatic token refresh
- **Authorization**: Fine-grained RBAC with dataset/table access control
- **Read-Only**: BigQuery client has read-only permissions
- **Input Sanitization**: Prevents SQL injection and prompt injection
- **Rate Limiting**: Token-based quotas to prevent abuse
- **Audit Logging**: All queries and events logged to Supabase

## Performance

- **Query Caching**: BigQuery cache and response cache
- **Result Summarization**: Smart truncation for large datasets
- **Context Management**: Automatic summarization of old conversation turns
- **Token Optimization**: Efficient prompt construction and token counting
- **Connection Pooling**: Reusable HTTP connections

## Environment Variables Reference

Complete list of all environment variables with descriptions and defaults:

### BigQuery Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PROJECT_ID` | ✅ Yes | - | Google Cloud project ID with BigQuery enabled |
| `LOCATION` | No | `US` | BigQuery location/region for query execution |
| `KEY_FILE` | ✅ Yes | - | Path to service account JSON key file with BigQuery read permissions |

### Supabase Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | ✅ Yes | - | Supabase project URL (e.g., https://xxx.supabase.co) |
| `SUPABASE_KEY` | ✅ Yes | - | Supabase anonymous key for client authentication |
| `SUPABASE_SERVICE_KEY` | ✅ Yes | - | Supabase service role key (bypasses RLS for server operations) |
| `SUPABASE_JWT_SECRET` | ✅ Yes | - | JWT secret for token validation (from Supabase Settings > API) |

### LLM Provider Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `openai` | LLM provider: `openai`, `anthropic`, or `gemini` |
| `LLM_MODEL` | No | Provider default | Model name override (e.g., `gpt-4o`, `claude-3-5-sonnet-20241022`) |
| `LLM_TEMPERATURE` | No | `0.7` | Temperature for generation (0.0-2.0, lower = more deterministic) |
| `LLM_MAX_TOKENS` | No | Provider default | Maximum tokens to generate in response |
| `OPENAI_API_KEY` | Conditional | - | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | Conditional | - | Required if `LLM_PROVIDER=anthropic` |
| `GOOGLE_API_KEY` | Conditional | - | Required if `LLM_PROVIDER=gemini` |

### Streamlit App Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_BASE_URL` | No | `http://localhost:8000` | Base URL of the MCP server for Streamlit to connect to |
| `ENABLE_RATE_LIMITING` | No | `true` | Enable rate limiting enforcement |
| `ENABLE_CACHING` | No | `true` | Enable query and LLM response caching |
| `MAX_CONTEXT_TURNS` | No | `5` | Maximum conversation turns to include in LLM context |
| `APP_TITLE` | No | `BigQuery Insights` | Application title displayed in Streamlit UI |
| `APP_ICON` | No | `📊` | Application icon emoji for browser tab |

### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENABLE_CACHING` | No | `true` | Enable/disable all caching layers |
| `ENABLE_RATE_LIMITING` | No | `true` | Enable/disable rate limiting and quota checks |

## Troubleshooting

### Common Issues

**Server won't start:**
- Check all required environment variables are set in `.env`
- Verify BigQuery service account key file exists and is valid
- Ensure Supabase credentials are correct (URL, keys, JWT secret)
- Run `uv sync` to install all dependencies

**Authentication fails:**
- Verify `SUPABASE_JWT_SECRET` matches your Supabase project (Settings > API > JWT Settings)
- Check token expiration settings in Supabase Auth
- Ensure user exists in Supabase Auth and has been assigned a role
- Verify `SUPABASE_SERVICE_KEY` is the service role key, not the anon key

**Authorization/RBAC errors:**
- Check user has been assigned at least one role in `user_roles` table
- Verify role has necessary permissions in `role_permissions` table
- Check dataset access is configured in `role_dataset_access` table
- Use wildcard `*` for dataset_id to grant access to all datasets

**Queries fail:**
- Check BigQuery service account has `bigquery.dataViewer` and `bigquery.jobUser` roles
- Verify dataset/table exists and is in the correct project
- Review generated SQL in error messages for syntax issues
- Check user's role has access to the requested dataset

**Rate limiting errors:**
- Check user's token quotas in `user_preferences` table
- View current usage in `user_usage_stats` table
- Increase daily/monthly quota or wait for quota to reset
- Disable rate limiting temporarily with `ENABLE_RATE_LIMITING=false` for testing

**Caching issues:**
- Clear user's cache via `DELETE /cache/user/{user_id}`
- Check `query_cache` table for stale entries
- Verify cache expiration times are reasonable
- Disable caching temporarily with `ENABLE_CACHING=false` for debugging

**Streamlit UI errors:**
- Ensure MCP server is running and accessible at `MCP_BASE_URL`
- Check browser console for JavaScript errors
- Verify all required environment variables are set for Streamlit app
- Check Streamlit logs with `streamlit run streamlit_app/app.py --logger.level=debug`

**LLM provider errors:**
- Verify correct API key is set for the selected provider
- Check API key is valid and has sufficient credits
- Try switching providers to isolate provider-specific issues
- Review error messages for rate limits or quota issues from LLM provider

**Database connection errors:**
- Verify Supabase project is running and accessible
- Check RLS policies are correctly configured
- Ensure required tables exist (run `docs/supabase_complete_schema.sql`)
- Check Supabase logs in dashboard for detailed error messages

See [docs/streamlit.md](docs/streamlit.md#troubleshooting) for detailed troubleshooting.

## Bootstrap Guide for New Developers

Complete step-by-step guide to get the system running from scratch:

### Step 1: Prerequisites

Ensure you have the following installed:
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- Google Cloud account with BigQuery enabled
- Supabase account

### Step 2: Google Cloud Setup

1. Create or select a Google Cloud project
2. Enable BigQuery API
3. Create a service account with these roles:
   - `BigQuery Data Viewer`
   - `BigQuery Job User`
4. Generate and download a JSON key file
5. Note your project ID

### Step 3: Supabase Setup

1. Create a new Supabase project at [supabase.com](https://supabase.com)
2. Wait for provisioning to complete
3. Collect credentials from Settings > API:
   - Project URL
   - Anonymous Key
   - Service Role Key
   - JWT Secret (from JWT Settings)
4. Open SQL Editor and run [`docs/supabase_complete_schema.sql`](docs/supabase_complete_schema.sql)
5. Verify all 11 tables were created
6. Create sample roles by uncommenting and running the sample data section
7. Enable Email authentication in Authentication > Providers

### Step 4: LLM Provider Setup

Choose at least one LLM provider and obtain an API key:
- **OpenAI**: Get API key from [platform.openai.com](https://platform.openai.com)
- **Anthropic**: Get API key from [console.anthropic.com](https://console.anthropic.com)
- **Google Gemini**: Get API key from [makersuite.google.com](https://makersuite.google.com)

### Step 5: Clone and Install

```bash
# Clone repository
git clone <repository-url>
cd mcp-bigquery-server

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### Step 6: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and fill in your credentials
nano .env  # or use your preferred editor
```

Required variables to set:
- `PROJECT_ID` - Your Google Cloud project ID
- `KEY_FILE` - Path to your service account JSON key
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Supabase anonymous key
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `SUPABASE_JWT_SECRET` - Supabase JWT secret
- `LLM_PROVIDER` - Choose "openai", "anthropic", or "gemini"
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` - Based on provider

### Step 7: Create First User

1. Start the MCP server (see Step 8)
2. Start the Streamlit app (see Step 9)
3. Open http://localhost:8501 in your browser
4. Click "Sign Up" and create an account
5. Check your email for verification link (if enabled)
6. Note your user ID from Supabase dashboard (Authentication > Users)

### Step 8: Assign User Role

Using Supabase SQL Editor:

```sql
-- Get your user ID
SELECT id, email FROM auth.users;

-- Assign analyst role
INSERT INTO user_roles (user_id, role_id, role_name) 
VALUES ('<your-user-id>', 'role-analyst', 'analyst');

-- Set token quotas
INSERT INTO user_preferences (user_id, preferences)
VALUES ('<your-user-id>', '{
  "daily_token_quota": 10000,
  "monthly_token_quota": 100000
}');
```

### Step 9: Start the Servers

Terminal 1 - MCP Server:
```bash
uv run mcp-bigquery --transport http-stream --port 8000
```

Terminal 2 - Streamlit App:
```bash
streamlit run streamlit_app/app.py
```

### Step 10: Verify Everything Works

1. Open http://localhost:8501
2. Sign in with your credentials
3. You should see the chat interface
4. Try asking: "What datasets are available?"
5. If it works, you're all set! 🎉

### Step 11: Configure Dataset Access (Optional)

Grant your role access to specific BigQuery datasets:

```sql
-- Grant access to all datasets (admin-like access)
INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level)
VALUES ('role-analyst', '*', NULL, 'read');

-- Or grant access to specific datasets
INSERT INTO role_dataset_access (role_id, dataset_id, table_id, access_level)
VALUES ('role-analyst', 'your_dataset_name', NULL, 'read');
```

### Common Bootstrap Issues

**"Authentication failed"**
- Double-check `SUPABASE_JWT_SECRET` matches your Supabase project
- Verify user exists in Supabase Auth
- Ensure user has been assigned a role

**"No datasets found"**
- Check BigQuery service account has proper permissions
- Verify `PROJECT_ID` is correct
- Ensure user's role has dataset access configured

**"Rate limit exceeded"**
- Check user has preferences set with quotas
- Verify quotas are reasonable (10000 for daily is typical)
- Check `user_usage_stats` table for current usage

**"Connection refused to MCP server"**
- Ensure MCP server is running on port 8000
- Check `MCP_BASE_URL` in Streamlit configuration
- Verify firewall isn't blocking the connection

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks
5. Submit a pull request

## License

[Your License Here]

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check existing documentation
- Review implementation summaries in project root
