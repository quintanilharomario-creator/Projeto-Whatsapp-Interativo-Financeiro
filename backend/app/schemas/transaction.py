import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.infrastructure.database.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    type: TransactionType
    amount: Decimal
    description: str
    category: str
    date: datetime

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("O valor deve ser maior que zero")
        return v


class TransactionUpdate(BaseModel):
    type: TransactionType | None = None
    amount: Decimal | None = None
    description: str | None = None
    category: str | None = None
    date: datetime | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("O valor deve ser maior que zero")
        return v


class TransactionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: TransactionType
    amount: Decimal
    description: str
    category: str
    date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
