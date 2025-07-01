"""
Logging configuration for BoxedBot
"""

import logging
import sys
from typing import Any, Dict
from datetime import datetime


class BoxedBotFormatter(logging.Formatter):
    """Custom formatter for BoxedBot logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Add timestamp
        record.timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Add service name
        record.service = "boxedbot"
        
        # Format the message
        if hasattr(record, 'repo_name'):
            record.context = f"repo={record.repo_name}"
        elif hasattr(record, 'pr_number'):
            record.context = f"pr={record.pr_number}"
        else:
            record.context = ""
        
        return super().format(record)


def setup_logging() -> logging.Logger:
    """Setup logging configuration"""
    
    # Create logger
    logger = logging.getLogger("boxedbot")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = BoxedBotFormatter(
        fmt="%(timestamp)s - %(service)s - %(levelname)s - %(name)s - %(context)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    # Prevent duplicate logs
    logger.propagate = False
    
    return logger


def get_logger(name: str = "boxedbot") -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin to add logging capabilities to classes"""
    
    @property
    def logger(self) -> logging.Logger:
        return get_logger(f"boxedbot.{self.__class__.__name__.lower()}")
    
    def log_operation(self, operation: str, **kwargs) -> None:
        """Log an operation with context"""
        context = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.info(f"{operation} - {context}")
    
    def log_error(self, operation: str, error: Exception, **kwargs) -> None:
        """Log an error with context"""
        context = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.error(f"{operation} failed - {context} - error: {error}", exc_info=True)


# Create default logger instance
logger = setup_logging()