"""FastAPI routes for health checks."""
import time
import asyncio
from fastapi import APIRouter


def create_health_router(event_manager) -> APIRouter:
    """Create router for health check endpoints."""
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health_check():
        """Health check endpoint."""
        from ..api.fastapi_app import active_connections
        
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "connections": {
                "total": len(active_connections),
                "by_channel": {
                    channel: len(clients)
                    for channel, clients in event_manager.channels.items()
                },
            },
        }
        # Broadcast health status to system channel
        asyncio.create_task(
            event_manager.broadcast("system", "health_check", health_data)
        )
        return health_data

    return router