from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.infrastructure.database.models.transaction import TransactionType
from app.services.transaction_service import TransactionService

TXN_PAYLOAD = {
    "type": "EXPENSE",
    "amount": "50.00",
    "description": "Almoço",
    "category": "Alimentação",
    "date": datetime.now(timezone.utc).isoformat(),
}


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_txn(db: AsyncSession, test_user):
    return await TransactionService.create(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("50.00"),
        description="Almoço",
        category="Alimentação",
        date=datetime.now(timezone.utc),
        db=db,
    )


async def test_create_transaction_endpoint(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/transactions", json=TXN_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "EXPENSE"
    assert "id" in data


async def test_list_transactions_endpoint(client: AsyncClient, auth_headers, test_txn):
    response = await client.get("/api/v1/transactions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_transaction_endpoint(client: AsyncClient, auth_headers, test_txn):
    response = await client.get(f"/api/v1/transactions/{test_txn.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(test_txn.id)


async def test_update_transaction_endpoint(client: AsyncClient, auth_headers, test_txn):
    response = await client.put(
        f"/api/v1/transactions/{test_txn.id}",
        json={"description": "Jantar", "amount": "80.00"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Jantar"


async def test_delete_transaction_endpoint(client: AsyncClient, auth_headers, test_txn):
    response = await client.delete(
        f"/api/v1/transactions/{test_txn.id}", headers=auth_headers
    )
    assert response.status_code == 204


async def test_create_transaction_no_auth(client: AsyncClient):
    response = await client.post("/api/v1/transactions", json=TXN_PAYLOAD)
    assert response.status_code == 403
