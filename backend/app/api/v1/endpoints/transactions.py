import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.infrastructure.database.models.transaction import TransactionType
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transações"])


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TransactionService.create(
        user_id=current_user.id,
        type=body.type,
        amount=body.amount,
        description=body.description,
        category=body.category,
        date=body.date,
        db=db,
    )


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    type: Optional[TransactionType] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TransactionService.list_by_user(
        user_id=current_user.id,
        db=db,
        type=type,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TransactionService.get_by_id(transaction_id, current_user.id, db)


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await TransactionService.update(
        transaction_id=transaction_id,
        user_id=current_user.id,
        db=db,
        **body.model_dump(exclude_unset=True),
    )


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await TransactionService.delete(transaction_id, current_user.id, db)
