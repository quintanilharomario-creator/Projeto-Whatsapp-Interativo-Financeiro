# backend/app/infrastructure/database/models/user.py
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    """Model de usuário — representa a tabela 'users' no PostgreSQL."""

    __tablename__ = "users"

    # Dados de acesso
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # índice para buscas rápidas por email
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Dados pessoais
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,  # opcional no cadastro
    )

    # Controle de conta
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,  # False até verificar o email
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
