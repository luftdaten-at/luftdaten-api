"""
Configuration for luftdaten-api.

Resolves paths and settings from environment variables.
"""
import os
from pathlib import Path

# Default path: config/station_blacklist.json relative to project root.
# Project root is parent of code/ directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BLACKLIST_PATH = _PROJECT_ROOT / "config" / "station_blacklist.json"


def get_blacklist_file_path() -> Path:
    """
    Get the path to the station blacklist config file.

    Uses STATION_BLACKLIST_FILE env var if set, otherwise defaults to
    config/station_blacklist.json in the project root.
    """
    env_path = os.getenv("STATION_BLACKLIST_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_BLACKLIST_PATH
