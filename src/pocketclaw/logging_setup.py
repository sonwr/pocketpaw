"""
Beautiful logging setup using Rich.

Created: 2026-02-02
Changes:
  - Initial setup with Rich console handler for beautiful logs.
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure beautiful logging with Rich.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    try:
        from rich.logging import RichHandler
        from rich.console import Console

        # Create console for rich output
        console = Console(stderr=True)

        # Configure root logger with Rich handler
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    console=console,
                    show_time=True,
                    show_path=False,  # Cleaner output
                    rich_tracebacks=True,
                    tracebacks_show_locals=False,
                    markup=True,
                )
            ],
        )

        # Reduce noise from third-party libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)

    except ImportError:
        # Fallback to basic logging if rich not installed
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )
        logging.warning("Rich not installed, using basic logging")
