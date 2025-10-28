"""FastAPI routes for Server-Sent Events (SSE)."""
import uuid
import asyncio
import datetime
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from ..core.json_encoder import CustomJSONEncoder
from ..handlers.resources import list_resources_handler


def create_events_router(event_manager) -> APIRouter:
    """Create router for SSE endpoints."""
    router = APIRouter(prefix="/events", tags=["events"])

    def get_client_id():
        """Dependency to generate client ID."""
        return str(uuid.uuid4())

    async def create_event_stream(
        request: Request, client_id: str, channel: str
    ) -> AsyncGenerator[str, None]:
        """Create an event stream for a specific client and channel."""
        try:
            # Import here to avoid circular imports
            from ..api.fastapi_app import active_connections

            # Create message queue for this client
            queue = asyncio.Queue()
            active_connections[client_id] = queue

            # Register client to the specific channel
            await event_manager.register_client(client_id, channel)

            # Initial connection established message
            connection_message = {
                "type": "connection_established",
                "client_id": client_id,
                "channel": channel,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            yield f"data: {json.dumps(connection_message, cls=CustomJSONEncoder)}\n\n"

            # Loop to process messages from the queue
            while True:
                # Check if client has disconnected
                if await request.is_disconnected():
                    print(f"Client {client_id} disconnected")
                    break

                # Try to get a message with timeout
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message
                    queue.task_done()
                except asyncio.TimeoutError:
                    # No message received in timeout period, send keep-alive ping
                    ping_data = {"type": "ping", "timestamp": datetime.time()}
                    yield f"data: {json.dumps(ping_data)}\n\n"

        except Exception as e:
            error_message = {"type": "error", "error": str(e)}
            yield f"data: {json.dumps(error_message)}\n\n"
            print(f"Error in event stream for client {client_id}: {str(e)}")
        finally:
            # Clean up when the client disconnects
            await event_manager.unregister_client(client_id)
            from ..api.fastapi_app import active_connections
            if client_id in active_connections:
                del active_connections[client_id]

    @router.get("")
    async def events(
        request: Request, client_id: str = Depends(get_client_id)
    ) -> StreamingResponse:
        """Legacy endpoint that now connects to the 'system' channel."""
        return await events_system(request, client_id)

    @router.get("/system")
    async def events_system(
        request: Request, client_id: str = Depends(get_client_id)
    ) -> StreamingResponse:
        """Event stream for system-related events."""
        import time
        from ..api.fastapi_app import active_connections  # <-- Add this import

        # Broadcast system startup event when a client connects
        asyncio.create_task(
            event_manager.broadcast(
                "system",
                "system_status",
                {
                    "status": "healthy",
                    "uptime": time.time(),
                    "connections": len(getattr(active_connections, "__dict__", {})),
                },
            )
        )

        return StreamingResponse(
            create_event_stream(request, client_id, "system"),
            media_type="text/event-stream",
        )

    @router.get("/queries")
    async def events_queries(
        request: Request, client_id: str = Depends(get_client_id)
    ) -> StreamingResponse:
        """Event stream for query-related events."""
        return StreamingResponse(
            create_event_stream(request, client_id, "queries"),
            media_type="text/event-stream",
        )

    @router.get("/resources")
    async def events_resources(
        request: Request, client_id: str = Depends(get_client_id)
    ) -> StreamingResponse:
        """SSE endpoint for streaming resource updates."""
        # This would need bigquery_client and config to be passed in
        # For now, we'll create a placeholder
        # TODO: Refactor to properly inject dependencies
        return StreamingResponse(
            create_event_stream(request, client_id, "resources"),
            media_type="text/event-stream",
        )

    return router