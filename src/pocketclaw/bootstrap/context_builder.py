"""
Builder for assembling the full agent context.
Created: 2026-02-02
"""

from pocketclaw.bootstrap.protocol import BootstrapProviderProtocol
from pocketclaw.memory.manager import MemoryManager, get_memory_manager
from pocketclaw.bootstrap.default_provider import DefaultBootstrapProvider


class AgentContextBuilder:
    """
    Assembles the final system prompt by combining:
    1. Static Identity (Bootstrap)
    2. Dynamic Memory (MemoryManager)
    3. Current State (e.g., date/time, active tasks)
    """

    def __init__(
        self,
        bootstrap_provider: BootstrapProviderProtocol | None = None,
        memory_manager: MemoryManager | None = None,
    ):
        self.bootstrap = bootstrap_provider or DefaultBootstrapProvider()
        self.memory = memory_manager or get_memory_manager()

    async def build_system_prompt(self, include_memory: bool = True) -> str:
        """Build the complete system prompt."""
        # 1. Load static identity
        context = await self.bootstrap.get_context()
        base_prompt = context.to_system_prompt()

        parts = [base_prompt]

        # 2. Inject memory context
        if include_memory:
            memory_context = await self.memory.get_context_for_agent()
            if memory_context:
                parts.append("\n# Memory Context\n" + memory_context)

        return "\n\n".join(parts)
