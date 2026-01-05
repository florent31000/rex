"""
Logging utilities for Rex-Brain.
"""

import logging
import sys
from datetime import datetime
from typing import Callable, Optional

# Global log callback for UI
_log_callback: Optional[Callable[[str, str], None]] = None


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """Setup the main logger."""
    logger = logging.getLogger("rex")
    logger.setLevel(level)
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Format
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger


def set_log_callback(callback: Callable[[str, str], None]):
    """Set a callback function for log messages (used by UI)."""
    global _log_callback
    _log_callback = callback


def log(message: str, level: str = "INFO"):
    """
    Log a message with the specified level.
    
    Levels: DEBUG, INFO, WARNING, ERROR, SUCCESS, SPEECH, ROBOT
    """
    logger = logging.getLogger("rex")
    
    # Map custom levels to standard levels
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "SUCCESS": logging.INFO,
        "SPEECH": logging.INFO,
        "ROBOT": logging.INFO,
    }
    
    std_level = level_map.get(level, logging.INFO)
    logger.log(std_level, message)
    
    # Call UI callback if set
    if _log_callback:
        try:
            _log_callback(message, level)
        except Exception:
            pass  # Don't let logging errors crash the app


def debug(message: str):
    """Log a debug message."""
    log(message, "DEBUG")


def info(message: str):
    """Log an info message."""
    log(message, "INFO")


def warning(message: str):
    """Log a warning message."""
    log(message, "WARNING")


def error(message: str):
    """Log an error message."""
    log(message, "ERROR")


def success(message: str):
    """Log a success message."""
    log(message, "SUCCESS")


def speech(message: str):
    """Log a speech/TTS message."""
    log(message, "SPEECH")


def robot(message: str):
    """Log a robot action message."""
    log(message, "ROBOT")

