from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    InvalidAmountError,
    TransactionNotFoundError,
)
from app.infrastructure.database.models.transaction import TransactionType
from app.services.auth_service import AuthService
from app.services.transaction_service import TransactionService

NOW = datetime.now(timezone.utc)


@pytest.fixture
async def test_user2(db: AsyncSession):
    return await AuthService.register(
        email="user2@test.com",
        password="TestPass123!",
        db=db,
    )


@pytest.fixture
async def test_txn(db: AsyncSession, test_user):
    return await TransactionService.create(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("50.00"),
        description="Compra no mercado",
        category="Alimentação",
        date=NOW,
        db=db,
    )


async def test_create_transaction_success(db: AsyncSession, test_user):
    txn = await TransactionService.create(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("1000.00"),
        description="Salário",
        category="Salário",
        date=NOW,
        db=db,
    )
    assert txn.id is not None
    assert txn.amount == Decimal("1000.00")
    assert txn.type == TransactionType.INCOME
    assert txn.user_id == test_user.id


async def test_create_transaction_invalid_amount(db: AsyncSession, test_user):
    with pytest.raises(InvalidAmountError):
        await TransactionService.create(
            user_id=test_user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("0.00"),
            description="Teste",
            category="Outros",
            date=NOW,
            db=db,
        )


async def test_list_transactions_by_user(db: AsyncSession, test_user, test_txn):
    txns = await TransactionService.list_by_user(test_user.id, db)
    assert len(txns) >= 1
    assert any(t.id == test_txn.id for t in txns)


async def test_update_transaction_success(db: AsyncSession, test_user, test_txn):
    updated = await TransactionService.update(
        transaction_id=test_txn.id,
        user_id=test_user.id,
        db=db,
        description="Compra no supermercado",
        amount=Decimal("75.00"),
    )
    assert updated.description == "Compra no supermercado"
    assert updated.amount == Decimal("75.00")


async def test_update_transaction_unauthorized(db: AsyncSession, test_txn, test_user2):
    with pytest.raises(AuthorizationError):
        await TransactionService.update(
            transaction_id=test_txn.id,
            user_id=test_user2.id,
            db=db,
            description="Tentativa",
        )


async def test_delete_transaction_success(db: AsyncSession, test_user, test_txn):
    await TransactionService.delete(test_txn.id, test_user.id, db)
    with pytest.raises(TransactionNotFoundError):
        await TransactionService.get_by_id(test_txn.id, test_user.id, db)


async def test_delete_transaction_unauthorized(db: AsyncSession, test_txn, test_user2):
    with pytest.raises(AuthorizationError):
        await TransactionService.delete(test_txn.id, test_user2.id, db)
