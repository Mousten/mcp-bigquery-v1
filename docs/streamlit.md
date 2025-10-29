# Streamlit UI for BigQuery Insights

A business-friendly Streamlit application that provides a conversational interface for querying BigQuery data with natural language.

## Features

- **🔐 Authentication**: Secure login with email/password or magic link via Supabase
- **💬 Chat Interface**: Natural language queries with conversation history
- **📊 Visualizations**: Auto-generated charts and graphs based on query results
- **📋 Results Display**: Tabular data with download options
- **🔄 Session Management**: Create, rename, and delete chat sessions
- **🔒 RBAC**: Role-based access control with dataset/table permissions
- **⏱️ Rate Limiting**: Token tracking and quota enforcement
- **🚀 Real-time**: Streaming responses with progress indicators

## Prerequisites

1. **MCP BigQuery Server**: Must be running and accessible
2. **Supabase Project**: With authentication and required tables set up
3. **LLM Provider API Key**: OpenAI, Anthropic, or Google API key
4. **BigQuery Access**: Service account with appropriate permissions

## Installation

The Streamlit app uses the same dependencies as the main project:

```bash
# Install with uv
uv sync

# Or with pip
pip install -e .
```

## Configuration

The Streamlit app is configured via environment variables. Create a `.env` file in the project root:

```bash
# MCP Server
MCP_BASE_URL=http://localhost:8000

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# BigQuery Configuration
PROJECT_ID=your-gcp-project-id

# LLM Provider (choose one)
LLM_PROVIDER=openai  # or "anthropic", "gemini"
LLM_MODEL=gpt-4o     # optional, uses provider default if not set

# API Keys (based on provider)
OPENAI_API_KEY=sk-...           # if using OpenAI
ANTHROPIC_API_KEY=sk-ant-...    # if using Anthropic
GOOGLE_API_KEY=...              # if using Gemini

# Feature Flags (optional)
ENABLE_RATE_LIMITING=true       # default: true
ENABLE_CACHING=true             # default: true
MAX_CONTEXT_TURNS=5             # default: 5

# UI Customization (optional)
APP_TITLE="BigQuery Insights"   # default: BigQuery Insights
APP_ICON=📊                     # default: 📊
```

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MCP_BASE_URL` | Base URL of the MCP server | `http://localhost:8000` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase anonymous key | `eyJhbGc...` |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation | `your-jwt-secret` |
| `PROJECT_ID` | Google Cloud project ID | `my-project-123` |
| `LLM_PROVIDER` | LLM provider type | `openai`, `anthropic`, or `gemini` |

### LLM Provider Configuration

**OpenAI:**
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o  # optional
```

**Anthropic:**
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-sonnet-20241022  # optional
```

**Google Gemini:**
```bash
LLM_PROVIDER=gemini
GOOGLE_API_KEY=...
LLM_MODEL=gemini-1.5-pro  # optional
```

## Running the Application

### Start the MCP Server

First, ensure the MCP BigQuery server is running:

```bash
# Start in HTTP stream mode (recommended for Streamlit)
uv run mcp-bigquery --transport http-stream --port 8000

# Or in regular HTTP mode
uv run mcp-bigquery --transport http --port 8000
```

### Launch Streamlit

```bash
# Run with streamlit
streamlit run streamlit_app/app.py

# Or with uv
uv run streamlit run streamlit_app/app.py

# Specify port (optional)
streamlit run streamlit_app/app.py --server.port 8501

# Enable development mode with auto-reload
streamlit run streamlit_app/app.py --server.runOnSave true
```

The app will open in your browser at `http://localhost:8501`.

## Usage

### 1. Sign In

Choose your authentication method:

- **Email & Password**: Standard username/password authentication
- **Magic Link**: Passwordless authentication via email link

### 2. Start a Conversation

- Click "➕ New Chat" in the sidebar to create a session
- Type your question in the chat input at the bottom
- Press Enter to submit

### 3. View Results

The assistant will:
- Generate and execute SQL queries
- Display results in tabular format
- Suggest relevant visualizations
- Provide insights and explanations

### 4. Explore Visualizations

When the assistant suggests charts:
- View multiple chart options in tabs
- Interact with Plotly visualizations
- Download charts as images

### 5. Manage Sessions

- **Switch Sessions**: Click session names in sidebar
- **Rename Session**: Click "✏️ Rename" button
- **Delete Session**: Click "🗑️ Delete" button
- **View History**: Previous messages load automatically

### 6. Download Data

- Click "⬇️ Download CSV" to export query results
- Data is formatted and ready for analysis

## User Interface

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ 📊 BigQuery Insights                      👤 Account    │
├─────────┬───────────────────────────────────────────────┤
│         │  Chat Title                    ✏️ Rename 🗑️  │
│ 💬 Chat │ ─────────────────────────────────────────────│
│ Sessions│                                               │
│         │  🧑 User: What are the top products?         │
│ ➕ New  │                                               │
│   Chat  │  🤖 Assistant: Here are the top products... │
│         │     📋 Results Table                          │
│ ▶️ Chat │     📊 Suggested Visualizations             │
│   #1    │                                               │
│         │ ─────────────────────────────────────────────│
│ 💬 Chat │                                               │
│   #2    │  Ask a question about your data...           │
│         │ [                                          ] ▶│
└─────────┴───────────────────────────────────────────────┘
```

### Components

#### Sidebar
- **New Chat**: Create fresh conversation
- **Session List**: All your chat sessions
- **Session Status**: Current session highlighted

#### Chat Area
- **Message History**: Scrollable conversation
- **User Messages**: Your questions
- **Assistant Responses**: Answers with insights
- **SQL Queries**: Expandable code blocks
- **Results**: Tables and visualizations
- **Metadata**: Tokens used, processing time

#### Chat Input
- **Text Input**: Type your question
- **Enter to Send**: Submit with Enter key
- **Processing State**: Visual feedback during execution

## Features in Detail

### Authentication & Security

- JWT-based authentication via Supabase
- Automatic token refresh
- Secure session management
- RBAC enforcement at query time

### Conversation Management

- Multi-turn conversations with context
- Automatic context summarization
- Message persistence in Supabase
- Session isolation per user

### Query Results

- Automatic type inference
- Sortable, filterable tables
- CSV export functionality
- Large dataset handling

### Visualizations

- Bar charts for categorical comparisons
- Line charts for time series
- Pie charts for distributions
- Scatter plots for correlations
- Metrics for key numbers
- Auto-generated based on data

### Error Handling

- User-friendly error messages
- Error type classification
- Retry suggestions
- Rate limit notifications

## Troubleshooting

### Authentication Issues

**Problem**: "Configuration Error" on startup

**Solution**:
- Verify `.env` file exists and has all required variables
- Check Supabase credentials are correct
- Ensure JWT secret matches your Supabase project

**Problem**: "Sign in failed"

**Solution**:
- Verify email and password are correct
- Check Supabase Auth is enabled
- Ensure user exists in Supabase Auth

### Connection Issues

**Problem**: "Failed to create session" or API errors

**Solution**:
- Verify MCP server is running (`http://localhost:8000`)
- Check `MCP_BASE_URL` matches server address
- Test server health: `curl http://localhost:8000/stream/health`

**Problem**: Token expired errors

**Solution**:
- Sign out and sign back in
- Check token expiration settings in Supabase
- Automatic refresh should handle this

### Query Issues

**Problem**: "No valid columns found" in charts

**Solution**:
- SQL query may not return expected columns
- Check data types in results
- Try a different chart type

**Problem**: Rate limit exceeded

**Solution**:
- Wait for quota to reset
- Check usage in Supabase `token_usage_daily` table
- Adjust quota limits if needed

### Performance Issues

**Problem**: Slow query responses

**Solution**:
- BigQuery query may be complex
- Enable caching with `ENABLE_CACHING=true`
- Limit result rows with SQL `LIMIT` clause
- Check BigQuery job in GCP console

## Development

### Project Structure

```
streamlit_app/
├── app.py                 # Main application entry point
├── auth.py                # Authentication UI and logic
├── chat_ui.py            # Chat interface components
├── config.py             # Configuration management
├── insights_ui.py        # Results and visualization rendering
├── session_manager.py    # Session persistence logic
└── utils.py              # Helper functions
```

### Adding Custom Charts

To add a new chart type:

1. Add chart type to `insights_ui.py`:

```python
def render_custom_chart(df, x_column, y_columns, title, config):
    """Render your custom chart."""
    fig = px.custom_chart(df, x=x_column, y=y_columns, title=title)
    st.plotly_chart(fig, use_container_width=True)
```

2. Update `render_single_chart()` to handle new type:

```python
elif chart_type == "custom":
    render_custom_chart(df, x_column, y_columns, title, config)
```

### Customizing UI

Modify `config.py` to add new settings:

```python
class StreamlitConfig(BaseSettings):
    # Add new field
    custom_setting: str = Field(default="value", description="My setting")
```

Update `.env`:
```bash
CUSTOM_SETTING=my-value
```

## Testing

### Manual Testing Checklist

- [ ] Login with email/password works
- [ ] Magic link email is sent
- [ ] Create new chat session
- [ ] Ask a question and get results
- [ ] View query results in table
- [ ] See chart suggestions
- [ ] Download results as CSV
- [ ] Rename session
- [ ] Delete session
- [ ] Switch between sessions
- [ ] History persists across page reloads
- [ ] Sign out clears session
- [ ] Unauthorized access blocked
- [ ] Rate limit triggers correctly
- [ ] Token refresh works

### Testing with Multiple Users

1. Create users in Supabase Auth
2. Assign different roles and permissions
3. Sign in with each user
4. Verify data access is correctly restricted
5. Check session isolation

## Deployment

### Local Development

```bash
# Start MCP server
uv run mcp-bigquery --transport http-stream

# In another terminal, start Streamlit
streamlit run streamlit_app/app.py
```

### Production Deployment

#### Option 1: Streamlit Cloud

1. Push to GitHub repository
2. Connect to Streamlit Cloud
3. Add secrets in Streamlit Cloud dashboard
4. Deploy

#### Option 2: Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

Build and run:
```bash
docker build -t bigquery-insights-ui .
docker run -p 8501:8501 --env-file .env bigquery-insights-ui
```

#### Option 3: Cloud Run / App Engine

Deploy both MCP server and Streamlit app as separate services with internal networking.

## Best Practices

### Security

- Never commit `.env` file
- Use environment-specific configurations
- Rotate API keys regularly
- Enable RLS in Supabase
- Use HTTPS in production

### Performance

- Enable caching for LLM responses
- Limit context turns to manage token usage
- Use BigQuery query cache
- Implement pagination for large result sets
- Monitor token usage and costs

### User Experience

- Provide clear error messages
- Show loading indicators
- Validate user input
- Enable conversation context
- Suggest example queries

## Support

For issues or questions:

1. Check this documentation
2. Review MCP server logs
3. Check Streamlit logs in terminal
4. Inspect browser console for errors
5. Verify Supabase table schemas

## License

Same as the main project.
