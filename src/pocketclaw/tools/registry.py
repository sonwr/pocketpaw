# Tool registry for managing available tools.
# Created: 2026-02-02
# Part of Nanobot Pattern Adoption

from typing import Any, List
import logging

logger = logging.getLogger(__name__)

from pocketclaw.tools.protocol import ToolProtocol
from pocketclaw.security import get_audit_logger, AuditSeverity


class ToolRegistry:
    """
    Registry for managing tools.

    Usage:
        registry = ToolRegistry()
        registry.register(ShellTool())
        registry.register(ReadFileTool())

        # Get definitions for LLM
        definitions = registry.get_definitions()

        # Execute a tool
        result = await registry.execute("shell", command="ls -la")
    """

    def __init__(self):
        self._tools: dict[str, ToolProtocol] = {}

    def register(self, tool: ToolProtocol) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"🔧 Registered tool: {tool.name}")

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.debug(f"🔧 Unregistered tool: {name}")

    def get(self, name: str) -> ToolProtocol | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools

    def get_definitions(self, format: str = "openai") -> List[dict[str, Any]]:
        """Get all tool definitions.

        Args:
            format: "openai" or "anthropic"

        Returns:
            List of tool definitions in the specified format.
        """
        definitions = []
        for tool in self._tools.values():
            defn = tool.definition
            if format == "anthropic":
                definitions.append(defn.to_anthropic_schema())
            else:
                definitions.append(defn.to_openai_schema())
        return definitions

    async def execute(self, name: str, **params: Any) -> str:
        """Execute a tool by name.

        Args:
            name: Tool name.
            **params: Tool parameters.

        Returns:
            Tool result as string.
        """
        tool = self._tools.get(name)

        if not tool:
            return f"Error: Tool '{name}' not found. Available: {list(self._tools.keys())}"

        # Audit Log: Attempt
        audit = get_audit_logger()
        
        # Map trust_level to severity
        t_level = getattr(tool, "trust_level", "standard")
        if t_level == "critical":
            severity = AuditSeverity.CRITICAL
        elif t_level == "high":
            severity = AuditSeverity.WARNING
        else:
            severity = AuditSeverity.INFO
            
        audit_id = audit.log_tool_use(name, params, severity=severity, status="attempt")

        try:
            logger.debug(f"🔧 Executing {name} with {params}")
            result = await tool.execute(**params)
            
            # Audit Log: Success
            # We don't log full result content in audit to avoid PII, usually
            # But we might log "success" with generic context
            audit.log_tool_use(name, params, severity=severity, status="success")

            # Log truncation to avoid massive log files
            log_result = result[:200] + "..." if len(result) > 200 else result
            logger.debug(f"🔧 {name} result: {log_result}")
            return result
        except Exception as e:
            # Audit Log: Error
            from pocketclaw.security.audit import AuditEvent, AuditSeverity as AS
            audit.log(AuditEvent.create(
                severity=AS.WARNING,
                actor="agent",
                action="tool_error",
                target=name,
                status="error",
                error=str(e),
                params=params
            ))
            logger.error(f"🔧 {name} failed: {e}")
            return f"Error executing {name}: {str(e)}"

    @property
    def tool_names(self) -> List[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)
