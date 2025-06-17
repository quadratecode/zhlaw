"""
Centralized logging configuration for ZHLaw processing system.

This module provides a consistent logging setup across all modules,
with features like log rotation, formatting, and multiple handlers.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from src.config import LogConfig, BASE_DIR


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log output for terminal display."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to level name for terminal output
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        # Format the message
        result = super().format(record)
        
        # Reset levelname to original
        record.levelname = record.levelname.replace(self.RESET, '').split('\033[')[-1].split('m')[-1]
        
        return result


class LoggerManager:
    """Manages logger configuration and setup for the application."""
    
    _loggers: Dict[str, logging.Logger] = {}
    _initialized: bool = False
    
    @classmethod
    def setup_logging(
        cls,
        log_level: str = None,
        log_file: Path = None,
        enable_console: bool = True,
        enable_file: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        format_string: str = None,
        date_format: str = None
    ) -> None:
        """
        Set up the logging configuration for the entire application.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file
            enable_console: Whether to enable console output
            enable_file: Whether to enable file output
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            format_string: Custom format string for log messages
            date_format: Custom date format for log messages
        """
        if cls._initialized:
            return
            
        # Use defaults from config if not provided
        log_level = log_level or LogConfig.DEFAULT_LEVEL
        log_file = log_file or LogConfig.LOG_FILE
        format_string = format_string or LogConfig.LOG_FORMAT
        date_format = date_format or LogConfig.LOG_DATE_FORMAT
        
        # Create root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Console handler with colored output
        if enable_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_formatter = ColoredFormatter(format_string, date_format)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if enable_file:
            # Ensure log directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_formatter = logging.Formatter(format_string, date_format)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        # Set up specific loggers for third-party libraries
        # Reduce verbosity of some libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('adobe').setLevel(logging.WARNING)
        
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance with the given name.
        
        Args:
            name: Logger name (typically __name__ of the module)
            
        Returns:
            Configured logger instance
        """
        if not cls._initialized:
            cls.setup_logging()
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]
    
    @classmethod
    def add_file_handler(
        cls,
        logger_name: str,
        log_file: Path,
        level: str = 'INFO',
        format_string: str = None
    ) -> None:
        """
        Add an additional file handler to a specific logger.
        
        Args:
            logger_name: Name of the logger
            log_file: Path to the log file
            level: Logging level for this handler
            format_string: Custom format string
        """
        logger = cls.get_logger(logger_name)
        
        # Create file handler
        handler = logging.FileHandler(str(log_file), encoding='utf-8')
        handler.setLevel(getattr(logging, level.upper()))
        
        # Set formatter
        formatter = logging.Formatter(
            format_string or LogConfig.LOG_FORMAT,
            LogConfig.LOG_DATE_FORMAT
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
    
    @classmethod
    def log_exception(
        cls,
        logger: logging.Logger,
        exception: Exception,
        message: str = None,
        include_traceback: bool = True
    ) -> None:
        """
        Log an exception with consistent formatting.
        
        Args:
            logger: Logger instance
            exception: The exception to log
            message: Optional custom message
            include_traceback: Whether to include full traceback
        """
        error_msg = message or f"Exception occurred: {type(exception).__name__}"
        
        if include_traceback:
            logger.error(error_msg, exc_info=True)
        else:
            logger.error(f"{error_msg}: {str(exception)}")
    
    @classmethod
    def create_operation_logger(
        cls,
        operation_name: str,
        log_file: Optional[Path] = None
    ) -> 'OperationLogger':
        """
        Create a logger for a specific operation with timing and success tracking.
        
        Args:
            operation_name: Name of the operation
            log_file: Optional specific log file for this operation
            
        Returns:
            OperationLogger instance
        """
        return OperationLogger(operation_name, log_file)


class OperationLogger:
    """Context manager for logging operations with timing and success tracking."""
    
    def __init__(self, operation_name: str, log_file: Optional[Path] = None):
        self.operation_name = operation_name
        self.logger = LoggerManager.get_logger(__name__)
        self.start_time = None
        self.success = False
        self.error_count = 0
        
        # Add specific file handler if requested
        if log_file:
            LoggerManager.add_file_handler(__name__, log_file)
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting operation: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time
        
        if exc_type is None:
            self.success = True
            self.logger.info(
                f"Completed operation: {self.operation_name} "
                f"(Duration: {duration}, Errors: {self.error_count})"
            )
        else:
            self.logger.error(
                f"Failed operation: {self.operation_name} "
                f"(Duration: {duration}, Error: {exc_type.__name__}: {exc_val})"
            )
        
        # Don't suppress exceptions
        return False
    
    def log_error(self, message: str):
        """Log an error and increment error counter."""
        self.error_count += 1
        self.logger.error(message)
    
    def log_warning(self, message: str):
        """Log a warning."""
        self.logger.warning(message)
    
    def log_info(self, message: str):
        """Log an info message."""
        self.logger.info(message)
    
    def log_progress(self, current: int, total: int, item: str = "items"):
        """Log progress information."""
        percentage = (current / total * 100) if total > 0 else 0
        self.logger.info(f"Progress: {current}/{total} {item} ({percentage:.1f}%)")


# Convenience function for quick setup
def setup_logging(**kwargs):
    """Convenience function to set up logging with custom parameters."""
    LoggerManager.setup_logging(**kwargs)


# Convenience function to get logger
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name."""
    return LoggerManager.get_logger(name)