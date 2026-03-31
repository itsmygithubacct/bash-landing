"""Path utilities for locating project directories."""

import os

# Project root is the parent of this file's directory (utils/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
INPUT_BACKENDS_DIR = os.path.join(PROJECT_ROOT, "input_backends")


def asset_path(*parts: str) -> str:
    """Get absolute path to an asset file."""
    return os.path.join(ASSETS_DIR, *parts)


def config_path(*parts: str) -> str:
    """Get absolute path to a config file."""
    return os.path.join(CONFIG_DIR, *parts)
