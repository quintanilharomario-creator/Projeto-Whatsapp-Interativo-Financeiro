# backend/app/infrastructure/database/models/base.py
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base para todos os models do projeto."""
    pass


class TimestampMixin:
    """Adiciona created_at e updated_at em qualquer model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Usa UUID como chave primária (mais seguro que int sequencial)."""
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),  # armazena como string no Python
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
