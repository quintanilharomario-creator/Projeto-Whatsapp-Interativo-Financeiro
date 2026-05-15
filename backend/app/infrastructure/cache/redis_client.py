import asyncio
import json
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: redis.Redis | None = None
_TIMEOUT = 1.0


def _get_client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=_TIMEOUT,
            socket_connect_timeout=_TIMEOUT,
        )
    return _redis


async def cache_get(key: str) -> Any | None:
    try:
        raw = await asyncio.wait_for(_get_client().get(key), timeout=_TIMEOUT)
        return json.loads(raw) if raw is not None else None
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("cache_get_error", key=key, error=str(exc))
        return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        serialized = json.dumps(value, default=str)
        effective_ttl = ttl if ttl is not None else settings.CACHE_TTL
        await asyncio.wait_for(
            _get_client().setex(key, effective_ttl, serialized), timeout=_TIMEOUT
        )
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("cache_set_error", key=key, error=str(exc))


async def cache_delete(key: str) -> None:
    try:
        await asyncio.wait_for(_get_client().delete(key), timeout=_TIMEOUT)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("cache_delete_error", key=key, error=str(exc))


async def cache_clear_pattern(pattern: str) -> int:
    try:
        client = _get_client()
        keys = await asyncio.wait_for(client.keys(pattern), timeout=_TIMEOUT)
        if keys:
            await asyncio.wait_for(client.delete(*keys), timeout=_TIMEOUT)
        return len(keys)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("cache_clear_pattern_error", pattern=pattern, error=str(exc))
        return 0
