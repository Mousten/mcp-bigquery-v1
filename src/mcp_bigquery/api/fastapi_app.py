"""FastAPI application setup and middleware."""
import asyncio
from typing import Dict
from fastapi import FastAPI, Request
from ..routes.preferences import create_preferences_router
from ..core.supabase_client import SupabaseKnowledgeBase
from ..routes.tools import create_tools_router

# Store active connections with their message queues
active_connections: Dict[str, asyncio.Queue] = {}


def create_fastapi_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MCP BigQuery Server",
        description="A server for securely accessing BigQuery datasets with support for HTTP and Stdio transport.",
        version="0.1.0",
    )

    # Add logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        print(f"Received request: {request.method} {request.url}")
        try:
            response = await call_next(request)
            print(f"Response status: {response.status_code}")
            return response
        except Exception as e:
            print(f"Error processing request: {e}")
            raise

    # Initialize your knowledge base (replace with your actual initialization)
    knowledge_base = SupabaseKnowledgeBase()

    # Register the preferences router
    app.include_router(create_preferences_router(knowledge_base))

    # Register the tools router (if not already)
    # app.include_router(create_tools_router())

    return app