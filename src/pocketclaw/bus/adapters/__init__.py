"""
Channel adapter protocol for pluggable communication channels.
Created: 2026-02-02
"""

from abc import ABC, abstractmethod
from typing import Protocol

from pocketclaw.bus.events import InboundMessage, OutboundMessage, Channel
from pocketclaw.bus.queue import MessageBus


class ChannelAdapter(Protocol):
    """Protocol for channel adapters (Telegram, WebSocket, etc.)."""

    @property
    def channel(self) -> Channel:
        """The channel type this adapter handles."""
        ...

    async def start(self, bus: MessageBus) -> None:
        """Start the adapter, subscribing to the bus."""
        ...

    async def stop(self) -> None:
        """Stop the adapter gracefully."""
        ...

    async def send(self, message: OutboundMessage) -> None:
        """Send a message through this channel."""
        ...


class BaseChannelAdapter(ABC):
    """Base class for channel adapters with common functionality."""

    def __init__(self):
        self._bus: MessageBus | None = None
        self._running = False

    @property
    @abstractmethod
    def channel(self) -> Channel:
        """The channel type."""
        ...

    async def start(self, bus: MessageBus) -> None:
        """Start and subscribe to the bus."""
        self._bus = bus
        self._running = True
        bus.subscribe_outbound(self.channel, self.send)
        await self._on_start()

    async def stop(self) -> None:
        """Stop the adapter."""
        self._running = False
        if self._bus:
            self._bus.unsubscribe_outbound(self.channel, self.send)
        await self._on_stop()

    async def _on_start(self) -> None:
        """Override for custom start logic."""
        pass

    async def _on_stop(self) -> None:
        """Override for custom stop logic."""
        pass

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        """Send a message through this channel."""
        ...

    async def _publish_inbound(self, message: InboundMessage) -> None:
        """Helper to publish inbound messages."""
        if self._bus:
            await self._bus.publish_inbound(message)
