"""
Station blacklist utilities.

Loads station device IDs to exclude from API responses from a JSON config file.
"""

import json
import logging
from pathlib import Path

from config import get_blacklist_file_path

logger = logging.getLogger(__name__)


def load_blacklist_from_file(path: Path | None = None) -> frozenset[str]:
    """
    Load blacklisted station device IDs from a JSON file.

    Supports two formats:
    - Simple array: ["12345", "67890"]
    - Extended: {"devices": ["12345", "67890"]}

    Returns:
        Frozenset of device ID strings. Empty if file is missing or invalid.
    """
    file_path = path or get_blacklist_file_path()
    if file_path is None or not file_path.exists():
        logger.warning("Blacklist file not found at %s; using empty blacklist", file_path)
        return frozenset()

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            ids = data
        elif isinstance(data, dict) and "devices" in data:
            ids = data["devices"]
        else:
            logger.warning("Invalid blacklist format; using empty blacklist")
            return frozenset()

        result = frozenset(
            str(s).strip()
            for s in ids
            if isinstance(s, (str, int)) and str(s).strip()
        )
        logger.info("Loaded %d station IDs from blacklist", len(result))
        return result
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in blacklist file %s: %s", file_path, e)
        raise
