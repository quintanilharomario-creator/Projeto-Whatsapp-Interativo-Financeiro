import json
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def cache_get(key: str) -> Any | None:
    try:
        raw = await _get_client().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("cache_get_error", key=key, error=str(exc))
        return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        serialized = json.dumps(value, default=str)
        effective_ttl = ttl if ttl is not None else settings.CACHE_TTL
        await _get_client().setex(key, effective_ttl, serialized)
    except Exception as exc:
        logger.warning("cache_set_error", key=key, error=str(exc))


async def cache_delete(key: str) -> None:
    try:
        await _get_client().delete(key)
    except Exception as exc:
        logger.warning("cache_delete_error", key=key, error=str(exc))


async def cache_clear_pattern(pattern: str) -> int:
    try:
        client = _get_client()
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
        return len(keys)
    except Exception as exc:
        logger.warning("cache_clear_pattern_error", pattern=pattern, error=str(exc))
        return 0
