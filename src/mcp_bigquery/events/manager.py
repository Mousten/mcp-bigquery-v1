"""Event management system for broadcasting events to multiple clients."""
import json
import time
import asyncio
import datetime
from typing import Any, Dict, Set, Optional
from ..core.json_encoder import CustomJSONEncoder


class EventManager:
    """Event manager for broadcasting events to multiple clients."""

    def __init__(self):
        self.channels: Dict[str, Set[str]] = {
            "queries": set(),  # For query-related events
            "system": set(),   # For system status events
        }
        self.client_channels: Dict[str, Set[str]] = {}  # Maps client_id to channels
        self.keep_alive_task: Optional[asyncio.Task] = None

    async def register_client(self, client_id: str, channel: str) -> None:
        """Register a client to a specific event channel."""
        if channel not in self.channels:
            self.channels[channel] = set()

        self.channels[channel].add(client_id)

        if client_id not in self.client_channels:
            self.client_channels[client_id] = set()

        self.client_channels[client_id].add(channel)

        print(f"Client {client_id} registered to channel '{channel}'")

        # Start keep-alive task if not already running
        if self.keep_alive_task is None or self.keep_alive_task.done():
            self.keep_alive_task = asyncio.create_task(self._keep_alive_ping())

    async def unregister_client(self, client_id: str) -> None:
        """Remove a client from all subscribed channels."""
        if client_id in self.client_channels:
            channels = list(self.client_channels[client_id])
            for channel in channels:
                if channel in self.channels and client_id in self.channels[channel]:
                    self.channels[channel].remove(client_id)

            del self.client_channels[client_id]
            print(f"Client {client_id} unregistered from all channels")

            # Check if we need to stop the keep-alive task
            if not any(self.channels.values()):
                if self.keep_alive_task and not self.keep_alive_task.done():
                    self.keep_alive_task.cancel()
                    self.keep_alive_task = None

    async def broadcast(self, channel: str, event_type: str, data: Any) -> None:
        """Broadcast an event to all clients on a specific channel."""
        if channel not in self.channels:
            return

        event_data = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        message = f"data: {json.dumps(event_data, cls=CustomJSONEncoder)}\n\n"

        # Import here to avoid circular imports
        from ..api.fastapi_app import active_connections

        # Store the message in the respective queues
        for client_id in self.channels[channel]:
            if client_id in active_connections:
                await active_connections[client_id].put(message)

    async def _keep_alive_ping(self) -> None:
        """Send keep-alive pings to all connected clients every 25 seconds."""
        try:
            while any(self.channels.values()):
                # Send ping to all connected clients
                ping_data = {"type": "ping", "timestamp": time.time()}
                ping_message = f"data: {json.dumps(ping_data)}\n\n"

                # Import here to avoid circular imports
                from ..api.fastapi_app import active_connections

                for client_id in list(self.client_channels.keys()):
                    if client_id in active_connections:
                        await active_connections[client_id].put(ping_message)

                await asyncio.sleep(25)  # Send keep-alive every 25 seconds
        except asyncio.CancelledError:
            print("Keep-alive task cancelled")
        except Exception as e:
            print(f"Error in keep-alive task: {str(e)}")