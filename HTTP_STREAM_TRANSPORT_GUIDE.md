# HTTP-Stream Transport Mode Guide

## Quick Facts

🎯 **Problem Solved:** Tool endpoints now work in http-stream mode at both `/tools/*` and `/stream/tools/*` paths

📚 **Key Documentation:**
- [Quick Fix Guide](HTTP_STREAM_404_FIX_README.md) - Start here for immediate solutions
- [Full Investigation](INVESTIGATION_404_HTTP_STREAM.md) - Complete technical analysis
- [API Documentation](HTTP_ENDPOINTS_DOCUMENTATION.md) - All endpoints with transport modes
- [Changes Summary](CHANGES_SUMMARY.md) - What changed and why

## Transport Modes at a Glance

| Mode | Command | Tool Paths | Chat Paths | Use Case |
|---|---|---|---|---|
| **http** | `--transport http` | `/tools/*` | `/chat/*` | Default, simple REST API |
| **http-stream** | `--transport http-stream` | `/stream/tools/*` OR `/tools/*` | `/stream/chat/*` | REST + NDJSON streaming |
| **sse** | `--transport sse` | MCP protocol | MCP protocol | Server-Sent Events |
| **stdio** | `--transport stdio` | MCP protocol | MCP protocol | Command-line integration |

## Quick Start

### Using HTTP Mode
```bash
# Start server
uv run mcp-bigquery --transport http --port 8000

# Access tools
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets
```

### Using HTTP-Stream Mode
```bash
# Start server
uv run mcp-bigquery --transport http-stream --port 8000

# Both of these work (backwards compatible):
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/stream/tools/datasets
```

## Path Reference

### HTTP Mode
- ✅ `/tools/datasets`
- ✅ `/tools/execute_bigquery_sql`
- ✅ `/chat/sessions`
- ❌ `/stream/tools/*` → 404

### HTTP-Stream Mode (Both Work!)
Primary paths (recommended):
- ✅ `/stream/tools/datasets`
- ✅ `/stream/tools/execute_bigquery_sql`
- ✅ `/stream/chat/sessions`

Backwards compatible paths:
- ✅ `/tools/datasets`
- ✅ `/tools/execute_bigquery_sql`
- ⚠️  `/chat/sessions` → Use `/stream/chat/sessions` instead

## Code Examples

### Python - HTTP Mode
```python
import httpx

BASE_URL = "http://localhost:8000"

async with httpx.AsyncClient() as client:
    response = await client.get(
        f"{BASE_URL}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
```

### Python - HTTP-Stream Mode (Recommended)
```python
import httpx

BASE_URL = "http://localhost:8000/stream"  # Note the /stream base

async with httpx.AsyncClient() as client:
    # Tools
    response = await client.get(
        f"{BASE_URL}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Chat
    response = await client.get(
        f"{BASE_URL}/chat/sessions",
        headers={"Authorization": f"Bearer {token}"}
    )
```

### Python - HTTP-Stream Mode (Backwards Compatible)
```python
import httpx

BASE_URL = "http://localhost:8000"

async with httpx.AsyncClient() as client:
    # This also works for backwards compatibility
    response = await client.get(
        f"{BASE_URL}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
```

### Transport-Agnostic Code
```python
import httpx
import os

# Auto-detect transport mode
transport = os.getenv("MCP_TRANSPORT_MODE", "http")
base_url = os.getenv("MCP_BASE_URL", "http://localhost:8000")

# Add /stream prefix if in http-stream mode
if transport == "http-stream":
    base_url = f"{base_url}/stream"

async with httpx.AsyncClient() as client:
    response = await client.get(
        f"{base_url}/tools/datasets",
        headers={"Authorization": f"Bearer {token}"}
    )
```

## Troubleshooting

### Getting 404 errors?

**HTTP Mode:**
```bash
# Check you're NOT using /stream prefix
curl http://localhost:8000/tools/datasets  # ✅ Works
curl http://localhost:8000/stream/tools/datasets  # ❌ 404
```

**HTTP-Stream Mode:**
```bash
# Both work (as of latest version)
curl http://localhost:8000/tools/datasets  # ✅ Works
curl http://localhost:8000/stream/tools/datasets  # ✅ Works
```

### Check server mode
```bash
# Look for this in server logs:
"Starting server in HTTP mode..."        # → Use /tools/*
"Starting server in HTTP-STREAM mode..." # → Use /stream/tools/* or /tools/*
```

### Test connectivity
```bash
# HTTP mode
curl http://localhost:8000/

# HTTP-Stream mode
curl http://localhost:8000/stream/
# Returns: {"message": "MCP tools root", "mcp_base": "/stream", ...}
```

## Migration Guide

### From HTTP to HTTP-Stream

**Option 1: No changes required** ✅
Your existing code will continue to work thanks to backwards compatibility.

**Option 2: Update to recommended paths**
For consistency with other http-stream endpoints:
```python
# Before (HTTP mode)
url = f"{base_url}/tools/datasets"

# After (HTTP-Stream mode - recommended)
url = f"{base_url}/stream/tools/datasets"
```

### Environment Configuration

Add to your `.env`:
```bash
MCP_TRANSPORT_MODE=http-stream  # or "http"
MCP_BASE_URL=http://localhost:8000
```

Then in code:
```python
from streamlit_app.config import StreamlitConfig

config = StreamlitConfig.from_env()
transport = os.getenv("MCP_TRANSPORT_MODE", "http")
base_path = "/stream" if transport == "http-stream" else ""
full_url = f"{config.mcp_base_url}{base_path}/tools/datasets"
```

## Testing

### Manual Testing
```bash
# Start server
uv run mcp-bigquery --transport http-stream --port 8000

# Get a token (see authentication docs)
export TOKEN="your_jwt_token"

# Test both paths work
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tools/datasets
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/stream/tools/datasets

# Both should return 200 OK with datasets list
```

### Automated Testing
```bash
# Run verification script
uv run python test_http_stream_routes.py

# Should output:
# ✅ Both paths work in http-stream mode:
#   - GET /stream/tools/datasets (recommended)
#   - GET /tools/datasets (backwards compatible)
```

## Best Practices

### For New Projects
1. **Use `/stream/tools/*`** paths in http-stream mode for consistency
2. **Document transport mode** in your README/config
3. **Use environment variables** for transport configuration
4. **Test both modes** if you support multiple transports

### For Existing Projects
1. **No changes required** - backwards compatibility is enabled
2. **Optional:** Migrate to `/stream/tools/*` paths over time
3. **Document** which transport mode you're using
4. **Test** after upgrading to ensure no regressions

### For Libraries/SDKs
1. **Auto-detect** transport mode when possible
2. **Support both paths** in http-stream mode
3. **Provide config** for explicit transport mode setting
4. **Log warnings** if using deprecated paths (future)

## Documentation Index

📖 **Getting Started:**
- [HTTP Stream 404 Fix README](HTTP_STREAM_404_FIX_README.md) - Quick start guide

📊 **Technical Details:**
- [Full Investigation](INVESTIGATION_404_HTTP_STREAM.md) - Root cause analysis
- [Ticket Resolution](TICKET_RESOLUTION_HTTP_STREAM_404.md) - Official resolution
- [Changes Summary](CHANGES_SUMMARY.md) - All changes made

🔧 **Reference:**
- [API Documentation](HTTP_ENDPOINTS_DOCUMENTATION.md) - Complete endpoint reference
- [Test Script](test_http_stream_routes.py) - Verification test

## Support

### Still Having Issues?

1. **Check server logs** for transport mode confirmation
2. **Test with curl** to isolate the issue
3. **Verify authentication** token is valid
4. **Review documentation** for your specific transport mode
5. **Run test script** to verify routes are registered

### Common Issues

| Issue | Solution |
|---|---|
| 404 in http mode | Don't use `/stream` prefix |
| 404 in http-stream mode | Use `/stream/tools/*` or `/tools/*` |
| 401 Unauthorized | Check JWT token validity |
| 403 Forbidden | Check user permissions in Supabase |
| Connection refused | Verify server is running |

## Additional Resources

- **Main README:** [README.md](README.md)
- **Supabase Setup:** [docs/supabase_complete_schema.sql](docs/supabase_complete_schema.sql)
- **Environment Config:** [.env.example](.env.example)
- **Streamlit Guide:** [docs/STREAMLIT_QUICKSTART.md](docs/STREAMLIT_QUICKSTART.md)

---

**Last Updated:** Investigation completed and fix implemented
**Status:** ✅ Fully functional with backwards compatibility
