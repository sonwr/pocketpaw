"""
Unified Agent Loop.
Created: 2026-02-02
Part of Nanobot Pattern Adoption.
Changes: Added BrowserTool registration

This is the core "brain" of PocketPaw. It integrates:
1. MessageBus (Input/Output)
2. MemoryManager (Short-term & Long-term memory)
3. ToolRegistry (Capabilities)
4. AgentContextBuilder (Identity & System Prompt)
5. LLM Client (Anthropic/OpenAI/Ollama)

It replaces the old highly-coupled bot loops.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Any, AsyncIterator

try:
    from anthropic import AsyncAnthropic, APIError
except ImportError:
    AsyncAnthropic = None  # type: ignore

from pocketclaw.config import get_settings
from pocketclaw.bus import (
    get_message_bus,
    InboundMessage,
    OutboundMessage,
    Channel,
    SystemEvent
)
from pocketclaw.memory import get_memory_manager, MemoryType
from pocketclaw.tools import ToolRegistry
from pocketclaw.tools.builtin import ShellTool, ReadFileTool, WriteFileTool, ListDirTool, BrowserTool
from pocketclaw.tools.builtin.desktop import ScreenshotTool, StatusTool
from pocketclaw.bootstrap import AgentContextBuilder
from pocketclaw.agents.open_interpreter import OpenInterpreterAgent

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Main agent execution loop.
    
    Orchestrates the flow of data between Bus, Memory, and LLM.
    """

    def __init__(self):
        self.settings = get_settings()
        self.bus = get_message_bus()
        self.memory = get_memory_manager()
        self.tools = ToolRegistry()
        self.context_builder = AgentContextBuilder(memory_manager=self.memory)
        
        # LLM Client (Anthropic default for now)
        self.client: AsyncAnthropic | None = None
        
        # Open Interpreter Agent (Optional)
        self.oi_agent: OpenInterpreterAgent | None = None
        
        # Initialize selected backend
        if self.settings.agent_backend == "open_interpreter":
            self.oi_agent = OpenInterpreterAgent(self.settings)
            
        self._running = False
        
        # Register built-in tools
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the core toolset."""
        self.tools.register(ShellTool())
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(ListDirTool())
        self.tools.register(ScreenshotTool())
        self.tools.register(StatusTool())
        self.tools.register(BrowserTool())
        # TODO: Add more tools (WebSearch, etc.) as they are ported

    async def start(self) -> None:
        """Start the agent loop."""
        # Open Interpreter Backend
        if self.settings.agent_backend == "open_interpreter":
             if not self.oi_agent:
                 self.oi_agent = OpenInterpreterAgent(self.settings)
             self._running = True
             logger.info("🤖 Agent Loop started (Backend: Open Interpreter)")
             await self._loop()
             return

        # Default: Anthropic Backend
        if not AsyncAnthropic:
            logger.error("❌ Anthropic client not available. Install 'anthropic' package.")
            return

        api_key = self.settings.anthropic_api_key
        if not api_key:
            logger.error("❌ Anthropic API key not set.")
            return

        self.client = AsyncAnthropic(api_key=api_key)
        self._running = True
        logger.info("🤖 Agent Loop started (Backend: Anthropic)")
        
        await self._loop()

    async def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("🛑 Agent Loop stopped")

    async def _loop(self) -> None:
        """Main processing loop."""
        while self._running:
            # 1. Consume message from Bus
            message = await self.bus.consume_inbound(timeout=1.0)
            if not message:
                continue

            # 2. Process message in background task (to not block loop)
            asyncio.create_task(self._process_message(message))

    async def _process_message(self, message: InboundMessage) -> None:
        """Process a single message flow."""
        session_key = message.session_key
        logger.info(f"⚡ Processing message from {session_key}")

        try:
            # 1. Store User Message
            await self.memory.add_to_session(
                session_key=session_key,
                role="user",
                content=message.content,
                metadata=message.metadata
            )

            # 2. Build Context (System Prompt + Memory + Tools)
            system_prompt = await self.context_builder.build_system_prompt()
            tool_definitions = self.tools.get_definitions("anthropic")
            
            # 3. Load Session History
            history = await self.memory.get_session_history(session_key, limit=20)
            
            # Add current message if not yet in history (it should be, but just in case of race)
            # Actually get_session_history pulls what we just saved.
            
            # 4. Agent Execution with Backend Selection
            if self.settings.agent_backend == "open_interpreter" and self.oi_agent:
                await self._run_open_interpreter(message, system_prompt=system_prompt)
            else:
                # Default to Anthropic / Internal Tool Loop
                await self._llm_step(
                    message=message,
                    system_prompt=system_prompt,
                    messages=history,
                    tools=tool_definitions
                )

        except Exception as e:
            logger.exception(f"❌ Error processing message: {e}")
            await self.bus.publish_outbound(OutboundMessage(
                channel=message.channel,
                chat_id=message.chat_id,
                content=f"An error occurred: {str(e)}",
                reply_to=message.sender_id
            ))

    async def _llm_step(
        self,
        message: InboundMessage,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        depth: int = 0
    ) -> None:
        """Execute a single LLM step (generation -> [tool execution] -> response)."""
        if depth > 5:
            logger.warning("⚠️ Max recursion depth reached")
            await self._send_response(message, "I'm stuck in a loop. Stopping here.")
            return

        if not self.client:
            return

        try:
            current_response_text = ""
            current_tool_calls = []

            # Emit Thinking Event
            await self.bus.publish_system(SystemEvent(
                event_type="thinking",
                data={"session_key": message.session_key}
            ))

            # Streaming LLM response
            async with self.client.messages.stream(
                model=self.settings.anthropic_model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools,
            ) as stream:
                async for event in stream:
                    # Handle text delta
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        text_chunk = event.delta.text
                        current_response_text += text_chunk
                        # Stream to bus
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=message.channel,
                            chat_id=message.chat_id,
                            content=text_chunk,
                            is_stream_chunk=True
                        ))
                    
                    # Handle tool use
                    if event.type == "content_block_start" and event.content_block.type == "tool_use":
                        current_tool_calls.append(event.content_block)
                    
                    if event.type == "content_block_delta" and event.delta.type == "input_json_delta":
                        # Accumulate JSON delta for the last tool call
                        # Note: Simple accumulation, 'stream' helper usually handles state better.
                        # For robustness we might rely on final message, 
                        # but let's see if we can get the final message from stream object easily.
                        pass

            # Get final accumulated message
            final_message = await stream.get_final_message()
            
            # Send stream end marker
            await self.bus.publish_outbound(OutboundMessage(
                channel=message.channel,
                chat_id=message.chat_id,
                content="",
                is_stream_end=True
            ))

            # Store assistant response in memory
            # Note: We need to store the structure Anthropic expects (text + tool_uses)
            # For simplicity in 'file_store', we store text representation, 
            # but for 'messages' param in next call we need generic format.
            # MemoryStore currently flattens to string content.
            # ideally MemoryEntry should support 'blocks' or structured content.
            # For now, we'll store text content.
            
            assistant_content = ""
            if final_message.content:
                for block in final_message.content:
                    if block.type == "text":
                        assistant_content += block.text
                    elif block.type == "tool_use":
                        assistant_content += f"\n[Tool Use: {block.name}]"

            await self.memory.add_to_session(
                session_key=message.session_key,
                role="assistant",
                content=assistant_content
            )
            
            # Handle Tool Execution
            tool_results = []
            if final_message.content:
                for block in final_message.content:
                    if block.type == "tool_use":
                        # Execute Tool
                        result = await self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

            # Recurse if there were tools
            if tool_results:
                # Add tool results to messages
                # We need to construct the messages list carefully for Anthropic
                # 1. Provide the Assistant message (with tool_use)
                # 2. Provide the User message (with tool_result)
                
                # Since MemoryStore simplifies to string, we can't easily reconstruct 
                # exact block structure for history unless we upgrade MemoryStore.
                # For this Phase 1/2 transition, we might need to handle short-term 
                # conversation buffer in-memory within the Loop or upgrade MemoryEntry.
                
                # Let's try to append to `messages` locally for recursion
                # The `messages` list passed to _llm_step is from get_session_history.
                # We need to append the Assistant message we just got.
                
                # Convert final_message to dict format
                assistant_msg_dict = {
                    "role": "assistant",
                    "content": final_message.content
                }
                messages.append(assistant_msg_dict)
                
                # Create tool result message
                tool_msg_dict = {
                    "role": "user",
                    "content": tool_results
                }
                messages.append(tool_msg_dict)
                
                # Recursive call
                await self._llm_step(
                    message, system_prompt, messages, tools, depth + 1
                )

        except APIError as e:
            logger.error(f"Anthropic API Error: {e}")
            await self._send_response(message, "I encountered an API error.")
        except Exception as e:
            logger.exception(f"Unexpected error in LLM step: {e}")
            await self._send_response(message, "Something went wrong processing your request.")

    async def _execute_tool(self, name: str, params: dict) -> str:
        """Execute a tool via registry."""
        logger.info(f"🔧 Executing {name} with {params}")
        
        # Emit tool_start
        await self.bus.publish_system(SystemEvent(
            event_type="tool_start",
            data={"name": name, "params": params}
        ))
        
        try:
            result = await self.tools.execute(name, **params)
            
            # Emit tool_result
            await self.bus.publish_system(SystemEvent(
                event_type="tool_result",
                data={"name": name, "params": params, "result": result, "status": "success"}
            ))
            return result
        except Exception as e:
            error_msg = f"Error executing {name}: {str(e)}"
            
            # Emit tool_result (error)
            await self.bus.publish_system(SystemEvent(
                event_type="tool_result",
                data={"name": name, "params": params, "result": error_msg, "status": "error"}
            ))
            return error_msg

    async def _run_open_interpreter(self, message: InboundMessage, system_prompt: str = "") -> None:
        """Execute using Open Interpreter backend."""
        logger.info(f"🚀 Routing to Open Interpreter: {message.content[:50]}...")
        
        # Emit Thinking Event
        await self.bus.publish_system(SystemEvent(
            event_type="thinking",
            data={"session_key": message.session_key}
        ))
        
        try:
            full_response = ""
            async for chunk in self.oi_agent.run(message.content, system_message=system_prompt):
                chunk_type = chunk.get("type")
                content = chunk.get("content", "")
                
                if chunk_type == "message":
                    full_response += content
                    # Stream text
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=message.channel,
                        chat_id=message.chat_id,
                        content=content,
                        is_stream_chunk=True
                    ))
                
                elif chunk_type == "code":
                    # Emit code output as a distinct event or formatted block
                    code_block = f"\n```\n{content}\n```\n"
                    full_response += code_block
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=message.channel,
                        chat_id=message.chat_id,
                        content=code_block,
                        is_stream_chunk=True
                    ))
                    
                elif chunk_type == "error":
                    full_response += f"\n❌ {content}"
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=message.channel,
                        chat_id=message.chat_id,
                        content=f"\n❌ {content}",
                        is_stream_chunk=True
                    ))

            # Send stream end
            await self.bus.publish_outbound(OutboundMessage(
                channel=message.channel,
                chat_id=message.chat_id,
                content="",
                is_stream_end=True
            ))
            
            # Save to memory
            await self.memory.add_to_session(
                session_key=message.session_key,
                role="assistant",
                content=full_response
            )
            
        except Exception as e:
            logger.exception(f"Open Interpreter execution failed: {e}")
            await self._send_response(message, f"❌ Engine Failure: {str(e)}")

    async def _send_response(self, original: InboundMessage, content: str) -> None:
        """Helper to send a simple text response."""
        await self.bus.publish_outbound(OutboundMessage(
            channel=original.channel,
            chat_id=original.chat_id,
            content=content
        ))
