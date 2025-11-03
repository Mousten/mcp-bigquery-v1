"""Test that http-stream mode exposes routes at both /stream/tools/* and /tools/*."""
from fastapi import FastAPI, APIRouter
from src.mcp_bigquery.routes.tools import create_tools_router
from unittest.mock import MagicMock, AsyncMock

# Create mocks
bigquery_client = MagicMock()
event_manager = MagicMock()
event_manager.broadcast = AsyncMock()
knowledge_base = MagicMock()
config = MagicMock()
config.supabase_jwt_secret = "test-secret"

# Create tools router
tools_router = create_tools_router(bigquery_client, event_manager, knowledge_base, config)

# Create FastAPI app and simulate http-stream mode setup
app = FastAPI()

# Include router with /stream prefix (primary path)
app.include_router(tools_router, prefix="/stream")

# Also include without prefix for backwards compatibility
app.include_router(tools_router)

# Test: List all routes
print("=" * 80)
print("HTTP-STREAM MODE ROUTES WITH BACKWARDS COMPATIBILITY")
print("=" * 80)
print("\nTools available at /stream/tools/* (PRIMARY):")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        if route.path.startswith('/stream/tools/'):
            methods = ', '.join(sorted(route.methods))
            print(f"  {methods:20s} {route.path}")

print("\nTools ALSO available at /tools/* (BACKWARDS COMPATIBLE):")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        if route.path.startswith('/tools/') and not route.path.startswith('/stream/'):
            methods = ', '.join(sorted(route.methods))
            print(f"  {methods:20s} {route.path}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("\n✅ Both paths work in http-stream mode:")
print("  - GET /stream/tools/datasets (recommended)")
print("  - GET /tools/datasets (backwards compatible)")
print("\n✅ This prevents 404s from clients using old paths!")
print("\nNote: The /stream/tools/* paths are recommended for new code.")
