import uuid
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EmailAlreadyExistsError,
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.infrastructure.database.models.user import User


class AuthService:
    @staticmethod
    async def register(
        email: str,
        password: str,
        db: AsyncSession,
        full_name: str | None = None,
        phone: str | None = None,
    ) -> User:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            raise EmailAlreadyExistsError(email)
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            phone=phone,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def login(email: str, password: str, db: AsyncSession) -> str:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        return create_access_token(str(user.id))

    @staticmethod
    async def get_current_user(token: str, db: AsyncSession) -> User:
        try:
            payload = decode_token(token)
        except ExpiredSignatureError:
            raise ExpiredTokenError()
        except JWTError:
            raise InvalidTokenError()
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise InvalidTokenError()
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError(user_id)
        return user
