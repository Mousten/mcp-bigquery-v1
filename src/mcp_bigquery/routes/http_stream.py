from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse
import json
import asyncio
from typing import AsyncIterator
import uuid

def create_http_stream_router(event_manager) -> APIRouter:
    # changed prefix to avoid colliding with the MCP tools root
    router = APIRouter(prefix="/stream/ndjson", tags=["stream"])

    async def event_generator(request: Request, client_id: str, channel: str) -> AsyncIterator[bytes]:
        """
        Stream newline-delimited JSON (NDJSON) by creating a per-client queue,
        registering the client with the EventManager (same pattern as SSE),
        and yielding JSON lines from that queue until the client disconnects.

        This adapts to EventManager.broadcast which puts SSE-formatted strings
        like: "data: {...}\n\n" into the per-client asyncio.Queue.
        """
        # create per-client queue and register it in active_connections so
        # other parts of the app (event_manager.broadcast) can put messages here.
        from ..api.fastapi_app import active_connections

        queue = asyncio.Queue()
        active_connections[client_id] = queue

        # Register client with event manager so broadcasts route messages to this queue
        await event_manager.register_client(client_id, channel)

        try:
            # Optional initial message (NDJSON line)
            initial = {"type": "connection_established", "client_id": client_id, "channel": channel}
            yield (json.dumps(initial) + "\n").encode("utf-8")

            while True:
                if await request.is_disconnected():
                    break
                try:
                    raw_msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    # heartbeat to keep connection alive (send an empty line)
                    yield b"\n"
                    continue

                # EventManager places SSE-style strings like: "data: <json>\n\n"
                if isinstance(raw_msg, bytes):
                    try:
                        raw_msg = raw_msg.decode("utf-8")
                    except Exception:
                        # can't decode; skip
                        queue.task_done()
                        continue

                if not raw_msg:
                    queue.task_done()
                    continue

                # Extract JSON payload if present
                payload = None
                if isinstance(raw_msg, str) and raw_msg.strip().startswith("data:"):
                    # Remove leading "data:" and trailing whitespace/newlines
                    payload_text = raw_msg.split("data:", 1)[1].strip()
                    try:
                        payload = json.loads(payload_text)
                    except Exception:
                        # If not JSON, send as raw string
                        payload = payload_text
                else:
                    # If message isn't SSE formatted, try to interpret as JSON directly
                    try:
                        payload = json.loads(raw_msg)
                    except Exception:
                        payload = raw_msg

                # Yield as NDJSON (one JSON object per line)
                try:
                    yield (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
                except Exception:
                    # Fallback: yield raw string
                    yield (str(payload) + "\n").encode("utf-8")
                finally:
                    queue.task_done()
        finally:
            # cleanup
            await event_manager.unregister_client(client_id)
            if client_id in active_connections:
                del active_connections[client_id]

    @router.get("/")
    async def stream(request: Request, channel: str = "system"):
        """
        GET /stream/ndjson/?channel=... starts an NDJSON stream for the given channel.
        """
        client_id = str(uuid.uuid4())
        return StreamingResponse(event_generator(request, client_id, channel), media_type="application/x-ndjson")

    return router