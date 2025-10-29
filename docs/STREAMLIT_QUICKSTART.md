# Streamlit UI Quick Start Guide

Get up and running with the BigQuery Insights Streamlit UI in minutes.

## 1. Prerequisites

Before you begin, ensure you have:

- ✅ Python 3.10 or higher installed
- ✅ Google Cloud project with BigQuery enabled
- ✅ BigQuery service account key file
- ✅ Supabase project set up with authentication
- ✅ OpenAI, Anthropic, or Google API key

## 2. Installation

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd mcp-bigquery-server

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## 3. Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# Required: BigQuery Configuration
PROJECT_ID=your-gcp-project-id
KEY_FILE=path/to/service-account-key.json

# Required: Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-role-key-here
SUPABASE_JWT_SECRET=your-jwt-secret-here

# Required: LLM Provider (choose one)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here

# Optional: Streamlit UI Settings
MCP_BASE_URL=http://localhost:8000
APP_TITLE=BigQuery Insights
```

### Getting Supabase Credentials

1. Go to your [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Navigate to **Settings → API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon/public** key → `SUPABASE_KEY`
   - **service_role** key → `SUPABASE_SERVICE_KEY`
5. Navigate to **Settings → API → JWT Settings**
6. Copy **JWT Secret** → `SUPABASE_JWT_SECRET`

### Setting up Authentication

1. In Supabase Dashboard, go to **Authentication → Providers**
2. Enable **Email** provider
3. Optionally configure **Magic Link** settings
4. Create a test user:
   - Go to **Authentication → Users**
   - Click **Add User**
   - Enter email and password

## 4. Start the MCP Server

Open a terminal and start the backend server:

```bash
uv run mcp-bigquery --transport http-stream --port 8000
```

You should see:
```
Starting MCP server in HTTP-stream mode on 0.0.0.0:8000...
```

Keep this terminal open.

## 5. Launch Streamlit UI

Open a **new terminal** and start the Streamlit app:

```bash
streamlit run streamlit_app/app.py
```

Or with uv:
```bash
uv run streamlit run streamlit_app/app.py
```

Your browser should automatically open to `http://localhost:8501`.

## 6. Sign In

1. You'll see the login screen
2. Choose **Email & Password** tab
3. Enter the credentials for the test user you created in Supabase
4. Click **Sign In**

Alternatively, use the **Magic Link** tab to receive a sign-in link via email.

## 7. Start Chatting

Once signed in:

1. Click **➕ New Chat** in the sidebar
2. Type a question like:
   - "What datasets are available?"
   - "Show me the top 10 rows from [your-dataset].[your-table]"
   - "What are the column names in [your-table]?"
3. Press **Enter** to submit
4. View the results, SQL query, and suggested visualizations

## Troubleshooting

### "Configuration Error" on startup

**Problem**: Missing or invalid environment variables

**Solution**:
1. Verify `.env` file exists in project root
2. Check all required variables are set
3. Ensure no typos in variable names
4. Restart Streamlit after changing `.env`

### "Sign in failed"

**Problem**: Authentication error

**Solution**:
1. Verify user exists in Supabase Auth
2. Check credentials are correct
3. Ensure `SUPABASE_URL`, `SUPABASE_KEY`, and `SUPABASE_JWT_SECRET` are correct
4. Try creating a new user in Supabase Dashboard

### "Failed to create session" or API errors

**Problem**: Cannot connect to MCP server

**Solution**:
1. Verify MCP server is running in another terminal
2. Check `MCP_BASE_URL` matches server address (default: `http://localhost:8000`)
3. Test server health: `curl http://localhost:8000/stream/health`
4. Check server terminal for errors

### "No datasets available"

**Problem**: No RBAC permissions set up

**Solution**:
1. Go to Supabase Dashboard → SQL Editor
2. Run the RBAC setup SQL (see `docs/supabase_rbac_schema.sql`)
3. Assign roles and dataset access to your user
4. Sign out and sign back in to refresh permissions

### Token/JWT errors

**Problem**: Invalid or expired token

**Solution**:
1. Sign out and sign back in
2. Verify `SUPABASE_JWT_SECRET` matches your Supabase project
3. Check token expiration settings in Supabase Auth settings

### Import errors

**Problem**: Missing dependencies

**Solution**:
```bash
# Reinstall dependencies
uv sync

# Or with pip
pip install -e .
```

## Next Steps

### Customize the UI

Edit `streamlit_app/config.py` to add custom settings, or modify `.env`:

```bash
APP_TITLE=My Custom Title
APP_ICON=🚀
MAX_CONTEXT_TURNS=10
```

### Add Sample Data

To test with sample data:

1. Create a test dataset in BigQuery
2. Load sample CSV data
3. Set up RBAC to grant access to your user
4. Ask questions about the sample data

### Set Up RBAC

For proper access control:

1. Run the RBAC schema SQL in Supabase
2. Create roles (e.g., "analyst", "viewer")
3. Assign permissions to roles
4. Grant dataset/table access
5. Assign roles to users

See [docs/AUTH.md](AUTH.md) for detailed RBAC setup.

### Deploy to Production

For production deployment:

1. **MCP Server**: Deploy to Cloud Run, App Engine, or Kubernetes
2. **Streamlit UI**: Deploy to Streamlit Cloud, Cloud Run, or Docker
3. **Environment**: Use secrets management for credentials
4. **Networking**: Configure internal networking between services
5. **SSL**: Enable HTTPS for both services

See [docs/streamlit.md](streamlit.md#deployment) for deployment guides.

## Example Usage

### Sample Questions

Once you have data accessible:

**General exploration:**
- "What datasets do I have access to?"
- "List all tables in the sales dataset"
- "Show me the schema for the customers table"

**Data queries:**
- "What are the top 10 products by revenue?"
- "Show me daily sales trends for the last 30 days"
- "Which customers have placed orders in the last week?"
- "Compare revenue across different regions"

**Aggregations:**
- "What's the total revenue this month?"
- "Count the number of active users"
- "Calculate average order value by category"

**Time series:**
- "Show me monthly revenue growth"
- "Plot daily active users over time"
- "What's the trend in customer acquisition?"

### Working with Results

When you get results:

1. **View Table**: Scroll through the data table
2. **Sort/Filter**: Click column headers to sort
3. **Download**: Click "⬇️ Download CSV" to export
4. **Visualize**: View auto-generated charts in tabs
5. **Interact**: Hover over charts for details

### Managing Sessions

- **Create**: Click "➕ New Chat" for fresh conversation
- **Switch**: Click session names in sidebar to switch
- **Rename**: Click "✏️ Rename" to change title
- **Delete**: Click "🗑️ Delete" to remove (cannot be undone)

## Support Resources

- **Full Documentation**: [docs/streamlit.md](streamlit.md)
- **API Reference**: [src/mcp_bigquery/client/README.md](../src/mcp_bigquery/client/README.md)
- **Authentication**: [docs/AUTH.md](AUTH.md)
- **Chat Persistence**: [docs/CHAT_PERSISTENCE.md](CHAT_PERSISTENCE.md)

## Tips

- **Context Matters**: The agent remembers previous messages in the session
- **Be Specific**: Mention table/dataset names when possible
- **Check SQL**: Expand the SQL query to see what was executed
- **Save Sessions**: Sessions persist across page reloads
- **Monitor Usage**: Check token usage shown below each response

Happy querying! 🚀
