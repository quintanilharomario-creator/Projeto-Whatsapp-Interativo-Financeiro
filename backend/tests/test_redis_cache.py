"""Unit tests for Redis cache module — Redis client is mocked."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_redis_singleton():
    import app.infrastructure.cache.redis_client as m
    original = m._redis
    m._redis = None
    yield
    m._redis = original


@pytest.fixture
def mock_redis():
    with patch("app.infrastructure.cache.redis_client.redis.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_cache_set_and_get(mock_redis):
    from app.infrastructure.cache.redis_client import cache_get, cache_set

    mock_redis.get = AsyncMock(return_value='{"key": "value"}')
    mock_redis.setex = AsyncMock()

    await cache_set("test_key", {"key": "value"})
    result = await cache_get("test_key")

    assert result == {"key": "value"}
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_cache_get_miss(mock_redis):
    from app.infrastructure.cache.redis_client import cache_get

    mock_redis.get = AsyncMock(return_value=None)

    result = await cache_get("missing_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete(mock_redis):
    from app.infrastructure.cache.redis_client import cache_delete

    mock_redis.delete = AsyncMock()
    await cache_delete("some_key")
    mock_redis.delete.assert_called_once_with("some_key")


@pytest.mark.asyncio
async def test_cache_clear_pattern(mock_redis):
    from app.infrastructure.cache.redis_client import cache_clear_pattern

    mock_redis.keys = AsyncMock(return_value=["report:balance:abc", "report:monthly:abc"])
    mock_redis.delete = AsyncMock()

    count = await cache_clear_pattern("report:*:abc")

    assert count == 2
    mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_cache_get_returns_none_on_redis_error(mock_redis):
    from app.infrastructure.cache.redis_client import cache_get

    mock_redis.get = AsyncMock(side_effect=Exception("connection refused"))

    result = await cache_get("any_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_silently_fails_on_error(mock_redis):
    from app.infrastructure.cache.redis_client import cache_set

    mock_redis.setex = AsyncMock(side_effect=Exception("connection refused"))

    await cache_set("any_key", {"data": 1})


@pytest.mark.asyncio
async def test_cache_clear_pattern_empty(mock_redis):
    from app.infrastructure.cache.redis_client import cache_clear_pattern

    mock_redis.keys = AsyncMock(return_value=[])

    count = await cache_clear_pattern("report:*:nonexistent")
    assert count == 0
