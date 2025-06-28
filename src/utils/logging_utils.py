"""
Logging utilities for convenient logger access and management.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import inspect
import os
import logging
from typing import Optional

from src.logging_config import LoggerManager, get_logger as _get_logger


def get_module_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a properly configured logger for the current module.
    
    This function automatically determines the calling module's name
    and ensures logging is properly configured.
    
    Args:
        name: Optional logger name (defaults to caller's module name)
        
    Returns:
        Configured logger instance
        
    Example:
        # At the top of your module:
        logger = get_module_logger(__name__)
        
        # Or let it auto-detect:
        logger = get_module_logger()
    """
    if name is None:
        # Get caller's module name
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get('__name__', 'unknown')
        else:
            name = 'unknown'
    
    # Ensure LoggerManager is initialized
    manager = LoggerManager.get_instance()
    if not manager.is_setup():
        # Use defaults from environment
        manager.setup_logging(
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            structured=os.getenv('LOG_FORMAT') == 'json'
        )
    
    return manager.get_logger(name)


def auto_configure_logging():
    """
    Automatically configure logging based on environment variables.
    
    This function can be called at module import time to ensure
    basic logging is available.
    
    Environment variables:
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        LOG_FORMAT: 'json' for structured logging, otherwise standard format
        LOG_DISABLE_CONSOLE: Set to 'true' to disable console output
        LOG_DISABLE_FILE: Set to 'true' to disable file output
    """
    manager = LoggerManager.get_instance()
    if not manager.is_setup():
        manager.setup_logging(
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            structured=os.getenv('LOG_FORMAT') == 'json',
            enable_console=os.getenv('LOG_DISABLE_CONSOLE', '').lower() != 'true',
            enable_file=os.getenv('LOG_DISABLE_FILE', '').lower() != 'true'
        )


# Re-export from logging_config for convenience
from src.logging_config import LogContext, MetricsLogger, OperationLogger


# Export public functions and classes
__all__ = [
    'get_module_logger',
    'auto_configure_logging',
    'LogContext',
    'MetricsLogger', 
    'OperationLogger',
]