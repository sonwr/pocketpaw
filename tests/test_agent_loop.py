# Tests for Unified Agent Loop
# Created: 2026-02-02

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from pocketclaw.agents.loop import AgentLoop
from pocketclaw.bus import InboundMessage, Channel, OutboundMessage

@pytest.fixture
def mock_bus():
    bus = MagicMock()
    bus.consume_inbound = AsyncMock()
    bus.publish_outbound = AsyncMock()
    bus.publish_system = AsyncMock()
    return bus

@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.add_to_session = AsyncMock()
    mem.get_session_history = AsyncMock(return_value=[])
    return mem

@pytest.fixture
def mock_tools():
    tools = MagicMock()
    tools.get_definitions = MagicMock(return_value=[])
    tools.execute = AsyncMock(return_value="Tool Result")
    return tools

@pytest.fixture
def mock_anthropic():
    client = MagicMock()
    client.messages = MagicMock()
    
    # Define a custom class for the stream object to support async for AND methods
    class MockStream:
        def __init__(self):
            # Mock get_final_message
            final_msg = MagicMock()
            final_msg.content = [] # Simplified
            self.get_final_message = AsyncMock(return_value=final_msg)

        async def __aiter__(self):
            # Yield text delta
            delta = MagicMock()
            delta.type = "content_block_delta"
            delta.delta.type = "text_delta"
            delta.delta.text = "Hello world"
            yield delta
            
            # Yield tool use
            tool_use = MagicMock()
            tool_use.type = "content_block_start"
            tool_use.content_block.type = "tool_use"
            tool_use.content_block.name = "test_tool"
            tool_use.content_block.input = {}
            tool_use.content_block.id = "tool_1"
            yield tool_use

    # Mock stream context manager
    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=MockStream())
    stream_cm.__aexit__ = AsyncMock()
    
    client.messages.stream.return_value = stream_cm
    return client

@patch("pocketclaw.agents.loop.get_message_bus")
@patch("pocketclaw.agents.loop.get_memory_manager")
@patch("pocketclaw.agents.loop.AgentContextBuilder")
@patch("pocketclaw.agents.loop.AsyncAnthropic")
@pytest.mark.asyncio
async def test_agent_loop_process_message(
    mock_anthropic_cls, 
    mock_builder_cls, 
    mock_get_memory, 
    mock_get_bus,
    mock_bus,
    mock_memory,
    mock_anthropic
):
    # Setup mocks
    mock_get_bus.return_value = mock_bus
    mock_get_memory.return_value = mock_memory
    
    # Configure builder mock
    mock_builder_instance = mock_builder_cls.return_value
    mock_builder_instance.build_system_prompt = AsyncMock(return_value="System Prompt")

    
    # Mock settings
    with patch("pocketclaw.agents.loop.get_settings") as mock_settings:
        mock_settings.return_value.anthropic_api_key = "test_key"
        
        # Init loop
        loop = AgentLoop()
        loop.client = mock_anthropic
        
        # Create test message
        msg = InboundMessage(
            channel=Channel.CLI,
            sender_id="user1",
            chat_id="chat1",
            content="Hello",
        )
        
        # Test processing
        await loop._process_message(msg)
        
        # Verify interactions
        mock_memory.add_to_session.assert_called()
        mock_anthropic.messages.stream.assert_called()
        mock_bus.publish_outbound.assert_called()
