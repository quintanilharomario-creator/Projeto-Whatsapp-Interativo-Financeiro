import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyExistsError,
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import create_access_token
from app.services.auth_service import AuthService
from datetime import timedelta


async def test_register_user_success(db: AsyncSession):
    user = await AuthService.register(
        email="new@test.com",
        password="Secure123!",
        full_name="New User",
        db=db,
    )
    assert user.id is not None
    assert user.email == "new@test.com"
    assert user.full_name == "New User"
    assert user.hashed_password != "Secure123!"
    assert user.is_active is True
    assert user.is_verified is False


async def test_register_duplicate_email(db: AsyncSession, test_user):
    with pytest.raises(EmailAlreadyExistsError):
        await AuthService.register(
            email=test_user.email,
            password="AnotherPass123!",
            db=db,
        )


async def test_login_success(db: AsyncSession, test_user):
    token = await AuthService.login("existing@test.com", "TestPass123!", db)
    assert token is not None
    assert len(token) > 0


async def test_login_invalid_email(db: AsyncSession):
    with pytest.raises(InvalidCredentialsError):
        await AuthService.login("notfound@test.com", "AnyPass123!", db)


async def test_login_invalid_password(db: AsyncSession, test_user):
    with pytest.raises(InvalidCredentialsError):
        await AuthService.login(test_user.email, "WrongPass123!", db)


async def test_get_current_user_valid_token(db: AsyncSession, test_user):
    token = create_access_token(str(test_user.id))
    user = await AuthService.get_current_user(token, db)
    assert user.id == test_user.id
    assert user.email == test_user.email


async def test_get_current_user_invalid_token(db: AsyncSession):
    with pytest.raises(InvalidTokenError):
        await AuthService.get_current_user("invalid.token.here", db)


async def test_get_current_user_expired_token(db: AsyncSession, test_user):
    token = create_access_token(str(test_user.id), expires_delta=timedelta(seconds=-1))
    with pytest.raises(ExpiredTokenError):
        await AuthService.get_current_user(token, db)
