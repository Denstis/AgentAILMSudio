"""
Utils module for LM Agent.

Provides logging, caching, and other utility functions.
"""

from .logging import (
    setup_logging,
    ColoredFormatter,
    JSONFormatter,
    handle_exception,
    log_calls,
    TimerContext,
)

from .cache import (
    LRUCache,
    ExecutionCache,
    lru_cache,
    cached_import,
    clear_import_cache,
)

__all__ = [
    # Logging
    "setup_logging",
    "ColoredFormatter",
    "JSONFormatter",
    "handle_exception",
    "log_calls",
    "TimerContext",
    
    # Cache
    "LRUCache",
    "ExecutionCache",
    "lru_cache",
    "cached_import",
    "clear_import_cache",
]