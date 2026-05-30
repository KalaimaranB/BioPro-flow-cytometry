"""Disk-based caching for API responses to avoid rate limits and offline usage."""

import json
import time
from pathlib import Path
from typing import Any

from biopro_sdk.plugin import get_logger

logger = get_logger(__name__, "flow_cytometry")


class CacheManager:
    """Manages local JSON caching for API responses.

    Adheres to SRP by handling only storage, retrieval, and expiration logic.
    """

    def __init__(self, cache_dir: Path, ttl_seconds: int = 86400 * 7):
        """Initialize the cache manager.

        Args:
            cache_dir: Directory where cache files are stored.
            ttl_seconds: Default time-to-live in seconds (default 7 days).
        """
        self._cache_dir = cache_dir
        self._ttl_seconds = ttl_seconds

        # Ensure directory exists
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve a dictionary from cache if it exists and is not expired."""
        file_path = self._get_path(key)

        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = json.load(f)

            timestamp = data.get("_cache_timestamp", 0)
            if time.time() - timestamp > self._ttl_seconds:
                logger.debug(f"Cache expired for {key}")
                return None

            return data.get("payload")

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read cache for {key}: {e}")
            return None

    def set(self, key: str, payload: dict[str, Any]) -> None:
        """Store a dictionary in the cache."""
        file_path = self._get_path(key)

        data = {"_cache_timestamp": time.time(), "payload": payload}

        try:
            # Write to a temporary file first, then replace for atomicity
            temp_path = file_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f)
            temp_path.replace(file_path)
            logger.debug(f"Cached {key}")
        except OSError as e:
            logger.error(f"Failed to write cache for {key}: {e}")

    def _get_path(self, key: str) -> Path:
        """Sanitize key and return the full file path."""
        # Replace non-alphanumeric characters with underscores
        safe_key = "".join([c if c.isalnum() else "_" for c in key])
        return self._cache_dir / f"{safe_key}.json"
