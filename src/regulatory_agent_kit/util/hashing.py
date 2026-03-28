"""Hashing utilities for file analysis caching."""

from __future__ import annotations

import hashlib


def compute_cache_key(content: str, plugin_version: str, agent_version: str) -> str:
    """Compute a deterministic SHA-256 cache key.

    Args:
        content: File content (or any string payload).
        plugin_version: Regulation plugin version string.
        agent_version: Agent/tool version string.

    Returns:
        64-character lowercase hex SHA-256 digest.
    """
    hasher = hashlib.sha256()
    hasher.update(content.encode("utf-8"))
    hasher.update(plugin_version.encode("utf-8"))
    hasher.update(agent_version.encode("utf-8"))
    return hasher.hexdigest()
