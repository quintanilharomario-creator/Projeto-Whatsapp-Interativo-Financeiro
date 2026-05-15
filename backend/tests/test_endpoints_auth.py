from httpx import AsyncClient

from app.core.security import create_access_token


async def test_register_endpoint_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@test.com",
            "password": "Secure123!",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@test.com"
    assert data["full_name"] == "New User"
    assert "id" in data
    assert "hashed_password" not in data


async def test_register_endpoint_duplicate_email(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": test_user.email, "password": "AnotherPass!", "full_name": "Dup"},
    )
    assert response.status_code == 409


async def test_login_endpoint_success(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "existing@test.com", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_endpoint_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "WrongPass!"},
    )
    assert response.status_code == 401


async def test_get_me_endpoint_success(client: AsyncClient, test_user):
    token = create_access_token(str(test_user.id))
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["id"] == str(test_user.id)


async def test_get_me_endpoint_no_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


async def test_get_me_endpoint_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401
