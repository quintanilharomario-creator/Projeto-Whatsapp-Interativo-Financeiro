import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base, TimestampMixin, UUIDMixin


class MessageType(str, enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    QUERY = "QUERY"
    OTHER = "OTHER"


class WhatsappMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_messages"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="messagetype"), nullable=False, default=MessageType.OTHER
    )
    extracted_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
