# Tests for Message Bus System
# Created: 2026-02-02
# Part of Nanobot Pattern Adoption

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from pocketclaw.bus.events import InboundMessage, OutboundMessage, Channel
from pocketclaw.bus.queue import MessageBus
from pocketclaw.bus.adapters import BaseChannelAdapter


class MockAdapter(BaseChannelAdapter):
    """Mock adapter for testing."""
    @property
    def channel(self) -> Channel:
        return Channel.CLI

    async def send(self, message: OutboundMessage) -> None:
        pass


@pytest.mark.asyncio
async def test_inbound_flow():
    bus = MessageBus()
    
    msg = InboundMessage(
        channel=Channel.CLI,
        sender_id="user1",
        chat_id="chat1",
        content="Hello",
    )
    
    await bus.publish_inbound(msg)
    assert bus.inbound_pending() == 1
    
    consumed = await bus.consume_inbound()
    assert consumed == msg
    assert bus.inbound_pending() == 0


@pytest.mark.asyncio
async def test_outbound_pubsub():
    bus = MessageBus()
    
    # Create mock subscriber
    subscriber = AsyncMock()
    
    bus.subscribe_outbound(Channel.CLI, subscriber)
    
    msg = OutboundMessage(
        channel=Channel.CLI,
        chat_id="chat1",
        content="Response",
    )
    
    await bus.publish_outbound(msg)
    
    subscriber.assert_called_once_with(msg)


@pytest.mark.asyncio
async def test_outbound_multiple_subscribers():
    bus = MessageBus()
    
    sub1 = AsyncMock()
    sub2 = AsyncMock()
    
    bus.subscribe_outbound(Channel.CLI, sub1)
    bus.subscribe_outbound(Channel.CLI, sub2)
    
    msg = OutboundMessage(
        channel=Channel.CLI,
        chat_id="chat1",
        content="Response",
    )
    
    await bus.publish_outbound(msg)
    
    sub1.assert_called_once_with(msg)
    sub2.assert_called_once_with(msg)


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = MessageBus()
    subscriber = AsyncMock()
    
    bus.subscribe_outbound(Channel.CLI, subscriber)
    bus.unsubscribe_outbound(Channel.CLI, subscriber)
    
    msg = OutboundMessage(
        channel=Channel.CLI,
        chat_id="chat1",
        content="Response",
    )
    
    await bus.publish_outbound(msg)
    
    subscriber.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_integration():
    bus = MessageBus()
    adapter = MockAdapter()
    
    # Mock send method BEFORE starting
    adapter.send = AsyncMock()
    
    # Start adapter (subscribes to bus)
    await adapter.start(bus)
    
    # Publish outbound to this channel
    msg = OutboundMessage(
        channel=Channel.CLI,
        chat_id="chat1",
        content="Response",
    )
    await bus.publish_outbound(msg)
    
    adapter.send.assert_called_once_with(msg)
    
    # Stop adapter
    await adapter.stop()
    
    # Reset mock
    adapter.send.reset_mock()
    
    # Publish again - should not be called
    await bus.publish_outbound(msg)
    adapter.send.assert_not_called()


@pytest.mark.asyncio
async def test_broadcast():
    bus = MessageBus()
    sub_cli = AsyncMock()
    sub_tg = AsyncMock()
    
    bus.subscribe_outbound(Channel.CLI, sub_cli)
    bus.subscribe_outbound(Channel.TELEGRAM, sub_tg)
    
    msg = OutboundMessage(
        channel=Channel.CLI, # Origin channel doesn't matter for broadcast call except for exclude
        chat_id="chat1",
        content="Broadcast",
    )
    
    await bus.broadcast_outbound(msg, exclude=Channel.TELEGRAM)
    
    assert sub_cli.call_count == 1
    assert sub_tg.call_count == 0  # Excluded
