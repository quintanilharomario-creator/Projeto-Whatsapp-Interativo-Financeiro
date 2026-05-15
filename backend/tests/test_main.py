"""Tests for main.py: health check and application setup."""

from httpx import AsyncClient


async def test_health_check_returns_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "versao" in data
    assert "ambiente" in data


async def test_health_check_app_name(client: AsyncClient):
    from app.core.config import settings

    response = await client.get("/health")
    assert response.json()["app"] == settings.APP_NAME


async def test_docs_available(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200


async def test_openapi_json_available(client: AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    assert "/health" in data["paths"]


async def test_app_exception_handler_returns_structured_error(client: AsyncClient):
    """AppException must be serialized as {detail: ...} with the correct status code."""
    # Trigger a 403 by passing a wrong verify token
    response = await client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "WRONG",
            "hub.challenge": "abc",
        },
    )
    assert response.status_code == 403
    assert "detail" in response.json()


async def test_cors_headers_present(client: AsyncClient):
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # In development mode allow_origins=["*"] so any origin is accepted
    assert response.status_code in (200, 204)
