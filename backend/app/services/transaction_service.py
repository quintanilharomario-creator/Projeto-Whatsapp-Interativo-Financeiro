import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, InvalidAmountError, TransactionNotFoundError
from app.infrastructure.database.models.transaction import Transaction, TransactionType


class TransactionService:
    @staticmethod
    async def create(
        user_id: uuid.UUID,
        type: TransactionType,
        amount: Decimal,
        description: str,
        category: str,
        date: datetime,
        db: AsyncSession,
    ) -> Transaction:
        if amount <= 0:
            raise InvalidAmountError()

        transaction = Transaction(
            user_id=user_id,
            type=type,
            amount=amount,
            description=description,
            category=category,
            date=date,
        )
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return transaction

    @staticmethod
    async def list_by_user(
        user_id: uuid.UUID,
        db: AsyncSession,
        type: TransactionType | None = None,
        category: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Transaction]:
        query = select(Transaction).where(Transaction.user_id == user_id)
        if type is not None:
            query = query.where(Transaction.type == type)
        if category is not None:
            query = query.where(Transaction.category == category)
        if date_from is not None:
            query = query.where(Transaction.date >= date_from)
        if date_to is not None:
            query = query.where(Transaction.date <= date_to)
        query = query.order_by(Transaction.date.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        transaction_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Transaction:
        result = await db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise TransactionNotFoundError(transaction_id)
        if transaction.user_id != user_id:
            raise AuthorizationError()
        return transaction

    @staticmethod
    async def update(
        transaction_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
        type: TransactionType | None = None,
        amount: Decimal | None = None,
        description: str | None = None,
        category: str | None = None,
        date: datetime | None = None,
    ) -> Transaction:
        transaction = await TransactionService.get_by_id(transaction_id, user_id, db)

        if amount is not None and amount <= 0:
            raise InvalidAmountError()

        if type is not None:
            transaction.type = type
        if amount is not None:
            transaction.amount = amount
        if description is not None:
            transaction.description = description
        if category is not None:
            transaction.category = category
        if date is not None:
            transaction.date = date

        await db.commit()
        await db.refresh(transaction)
        return transaction

    @staticmethod
    async def delete(
        transaction_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        transaction = await TransactionService.get_by_id(transaction_id, user_id, db)
        await db.delete(transaction)
        await db.commit()
