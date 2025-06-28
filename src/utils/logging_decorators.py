"""
Logging decorators for consistent logging setup across the application.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import sys
import os
from functools import wraps
from typing import Callable, Optional, Dict, Any, TypeVar, cast
from pathlib import Path

from src.logging_config import LoggerManager, LogContext, get_logger


F = TypeVar('F', bound=Callable[..., Any])


def configure_logging(
    log_level: Optional[str] = None,
    structured: bool = False,
    context_fields: Optional[Dict[str, Any]] = None,
    log_file: Optional[Path] = None
) -> Callable[[F], F]:
    """
    Decorator to configure logging for main entry points.
    
    This decorator should be used on main() functions to ensure
    consistent logging setup across all entry points.
    
    Args:
        log_level: Logging level (defaults to LOG_LEVEL env var or INFO)
        structured: Whether to use structured JSON logging
        context_fields: Additional context fields to add to all logs
        log_file: Optional custom log file path
        
    Returns:
        Decorated function
        
    Example:
        @configure_logging(log_level='DEBUG')
        def main():
            logger = get_logger(__name__)
            logger.info("Application started")
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine log level from env or parameter
            level = log_level or os.getenv('LOG_LEVEL', 'INFO')
            
            # Determine structured logging from env or parameter
            use_structured = structured or os.getenv('LOG_FORMAT') == 'json'
            
            # Get script name for context
            script_name = os.path.basename(sys.argv[0])
            if script_name.endswith('.py'):
                script_name = script_name[:-3]
            
            default_context = {
                'script': script_name,
                'pid': os.getpid()
            }
            
            # Merge contexts
            context = {**default_context, **(context_fields or {})}
            
            # Setup logging
            logger_manager = LoggerManager.get_instance()
            logger_manager.setup_logging(
                log_level=level,
                structured=use_structured,
                context_fields=context,
                log_file=log_file
            )
            
            logger = logger_manager.get_logger(func.__module__)
            
            # Log start
            with LogContext(operation=func.__name__):
                logger.info(f"Starting {script_name}")
                
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"Completed {script_name} successfully")
                    return result
                except KeyboardInterrupt:
                    logger.warning(f"Interrupted {script_name}")
                    raise
                except Exception as e:
                    logger.error(f"Failed {script_name}: {type(e).__name__}: {e}", exc_info=True)
                    raise
        
        return cast(F, wrapper)
    return decorator


def log_function_call(
    log_level: str = 'DEBUG',
    log_args: bool = True,
    log_result: bool = False,
    max_arg_length: int = 100
) -> Callable[[F], F]:
    """
    Decorator to log function calls for debugging.
    
    Args:
        log_level: Level to log at (default: DEBUG)
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        max_arg_length: Maximum length of argument strings
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        logger = get_logger(func.__module__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Format arguments
            if log_args:
                args_str = ', '.join(
                    repr(arg)[:max_arg_length] for arg in args
                )
                kwargs_str = ', '.join(
                    f"{k}={repr(v)[:max_arg_length]}" for k, v in kwargs.items()
                )
                all_args = ', '.join(filter(None, [args_str, kwargs_str]))
                
                getattr(logger, log_level.lower())(
                    f"Calling {func.__name__}({all_args})"
                )
            else:
                getattr(logger, log_level.lower())(
                    f"Calling {func.__name__}"
                )
            
            # Call function
            result = func(*args, **kwargs)
            
            # Log result if requested
            if log_result:
                result_str = repr(result)[:max_arg_length]
                getattr(logger, log_level.lower())(
                    f"{func.__name__} returned: {result_str}"
                )
            
            return result
        
        return cast(F, wrapper)
    return decorator


def with_operation_logging(
    operation_name: Optional[str] = None,
    log_file: Optional[Path] = None
) -> Callable[[F], F]:
    """
    Decorator that wraps a function with operation logging.
    
    This provides timing, success tracking, and error counting
    for the decorated function.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
        log_file: Optional specific log file for this operation
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        op_name = operation_name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with LoggerManager.create_operation_logger(op_name, log_file) as op_logger:
                return func(*args, **kwargs)
        
        return cast(F, wrapper)
    return decorator


# Export public decorators
__all__ = [
    'configure_logging',
    'log_function_call',
    'with_operation_logging',
]