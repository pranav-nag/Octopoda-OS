"""
Synrix Runtime — Structured Logging
=====================================
Centralized logging configuration for all Synrix components.
"""

import logging
import sys

_configured = False


def get_logger(name: str) -> logging.Logger:
    """Get a Synrix logger with consistent formatting."""
    global _configured
    logger = logging.getLogger(f"synrix.{name}")

    if not _configured:
        _configure_root()
        _configured = True

    return logger


def _configure_root():
    """Configure the root synrix logger once."""
    root = logging.getLogger("synrix")
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
