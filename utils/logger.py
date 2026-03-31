"""Centralized logging for the game engine and game modules."""

import os
import sys
import logging
import traceback
from datetime import datetime
from typing import Optional
from functools import wraps

from utils.paths import LOGS_DIR


def _ensure_logs_dir():
    """Ensure the logs directory exists."""
    os.makedirs(LOGS_DIR, exist_ok=True)


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically module name).
        level: Logging level.
    """
    _ensure_logs_dir()

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(LOGS_DIR, f"{name}_{timestamp}.log")

    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    return logger


class GameLogger:
    """Game-specific logger with convenience methods for common events."""

    def __init__(self, game_name: str):
        self.game_name = game_name
        self.logger = get_logger(game_name)
        self.frame_count = 0
        self.last_state = {}
        self._log_session_start()

    def _log_session_start(self):
        self.logger.info("=" * 60)
        self.logger.info(f"Game session started: {self.game_name}")
        self.logger.info(f"Python version: {sys.version}")
        self.logger.info("=" * 60)

    def log_scene_change(self, from_scene: Optional[str], to_scene: str):
        self.logger.info(f"Scene change: {from_scene} -> {to_scene}")

    def log_frame(self, frame_num: int, dt: float):
        self.frame_count = frame_num
        if frame_num % 60 == 0:
            self.logger.debug(f"Frame {frame_num}, dt={dt:.4f}s")

    def log_event(self, event_type: str, details: str = ""):
        self.logger.info(f"Event [{event_type}]: {details}")

    def log_warning(self, message: str):
        self.logger.warning(message)

    def log_error(self, message: str, exc: Optional[Exception] = None):
        self.logger.error(message)
        if exc:
            self.logger.error(traceback.format_exc())

    def log_debug(self, message: str):
        self.logger.debug(message)

    def log_info(self, message: str):
        self.logger.info(message)

    def log_exception(self, message: str = "Exception occurred"):
        self.logger.exception(message)


def create_game_logger(game_name: str) -> GameLogger:
    """Create a GameLogger instance."""
    return GameLogger(game_name)


def log_exceptions(logger: GameLogger):
    """Decorator to log exceptions in methods."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log_error(f"Exception in {func.__name__}: {e}", e)
                raise
        return wrapper
    return decorator
