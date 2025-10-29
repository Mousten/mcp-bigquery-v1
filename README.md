# MCP BigQuery Server

A FastMCP server for securely accessing Google BigQuery with conversational AI capabilities, comprehensive authentication, and a business-friendly Streamlit UI.

## Features

### Core Capabilities
- **🔍 BigQuery Access**: Read-only access to datasets, tables, and query execution
- **🤖 Conversational AI**: Natural language queries powered by OpenAI, Anthropic, or Google Gemini
- **🔐 Authentication & RBAC**: JWT-based auth with role-based access control via Supabase
- **💬 Chat Persistence**: Multi-session conversations with history tracking
- **📊 Visualizations**: Auto-generated chart suggestions based on query results
- **⚡ Performance**: Query caching, result summarization, and rate limiting
- **🌐 Multiple Transports**: HTTP, SSE, stdio, and HTTP-stream modes

### Streamlit UI
- **🎨 User-Friendly Interface**: Chat-based UI for non-technical users
- **🔒 Secure Login**: Email/password and magic link authentication
- **💡 Interactive Insights**: Live charts, tables, and data exports
- **🗂️ Session Management**: Create, rename, and manage conversation sessions
- **📈 Real-time Updates**: Streaming responses with progress indicators

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

Required variables:
```bash
# BigQuery
PROJECT_ID=your-gcp-project-id
KEY_FILE=path/to/service-account-key.json

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

See [docs/streamlit.md](docs/streamlit.md) for complete configuration guide.

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

1. **Sign In**: Use email/password or magic link
2. **Start Chatting**: Ask questions in natural language
3. **View Results**: See tables, charts, and insights
4. **Manage Sessions**: Create, rename, and organize conversations

Example questions:
- "What are the top 10 products by revenue?"
- "Show me daily sales trends for the last 30 days"
- "Which customers have the highest lifetime value?"
- "Compare revenue across different regions"

See [docs/streamlit.md](docs/streamlit.md) for detailed UI documentation.

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

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI                         │
│              (Business User Interface)                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  MCP BigQuery Server                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   FastAPI    │  │     MCP      │  │   Handler    │ │
│  │   Routes     │  │     App      │  │   Logic      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Conversation │  │     LLM      │  │   BigQuery   │ │
│  │   Manager    │  │  Providers   │  │    Client    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                     Supabase                            │
│  - Authentication (JWT)                                 │
│  - RBAC (Roles, Permissions, Dataset Access)           │
│  - Chat Persistence (Sessions, Messages)               │
│  - Knowledge Base (Metadata, Preferences)              │
└─────────────────────────────────────────────────────────┘
```

### Key Modules

- **`streamlit_app/`**: Streamlit UI application
- **`src/mcp_bigquery/`**: Core server implementation
  - **`api/`**: FastAPI and MCP app setup
  - **`routes/`**: REST API endpoints
  - **`agent/`**: Conversational AI and orchestration
  - **`llm/`**: LLM provider integrations
  - **`client/`**: Python client library
  - **`core/`**: BigQuery, Supabase, and auth modules
  - **`handlers/`**: Business logic for operations
  - **`events/`**: Event management and logging

## Documentation

- **[Streamlit Quick Start](docs/STREAMLIT_QUICKSTART.md)**: Get started with the UI in minutes ⚡
- **[Streamlit UI Guide](docs/streamlit.md)**: Complete UI documentation with setup, usage, and deployment
- **[Client Library](src/mcp_bigquery/client/README.md)**: Python client API reference
- **[Authentication](docs/AUTH.md)**: JWT validation and RBAC setup
- **[Chat Persistence](docs/CHAT_PERSISTENCE.md)**: Session and message management
- **[LLM Providers](LLM_PROVIDER_IMPLEMENTATION.md)**: LLM integration details
- **[Conversation Manager](CONVERSATION_MANAGER_IMPLEMENTATION.md)**: Agent orchestration

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

## Troubleshooting

### Common Issues

**Server won't start:**
- Check environment variables in `.env`
- Verify BigQuery service account key is valid
- Ensure Supabase credentials are correct

**Authentication fails:**
- Verify JWT secret matches Supabase project
- Check token expiration settings
- Ensure user exists in Supabase Auth

**Queries fail:**
- Check BigQuery permissions
- Verify dataset/table access in RBAC
- Review SQL syntax in generated queries

**Streamlit UI errors:**
- Ensure MCP server is running
- Check `MCP_BASE_URL` configuration
- Verify all required environment variables are set

See [docs/streamlit.md](docs/streamlit.md#troubleshooting) for detailed troubleshooting.

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
