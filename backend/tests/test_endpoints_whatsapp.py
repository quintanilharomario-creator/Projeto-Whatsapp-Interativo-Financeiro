import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


@pytest_asyncio.fixture
async def user_with_phone(db: AsyncSession):
    from app.services.auth_service import AuthService

    user = await AuthService.register(
        email="waendpoint@test.com",
        password="TestPass123!",
        full_name="WA Endpoint User",
        db=db,
    )
    user.phone = "+5511888888888"
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _meta(phone: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": phone,
                        "id": "wamid.test",
                        "timestamp": "1234567890",
                        "type": "text",
                        "text": {"body": text},
                    }]
                },
                "field": "messages",
            }]
        }],
    }


async def test_verify_webhook_valid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "abc123",
        },
    )
    assert response.status_code == 200
    assert response.text == "abc123"


async def test_verify_webhook_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "abc123",
        },
    )
    assert response.status_code == 403


async def test_receive_webhook_expense(client: AsyncClient, user_with_phone):
    response = await client.post(
        "/api/v1/whatsapp/webhook",
        json=_meta("+5511888888888", "Gastei R$50 no mercado"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511888888888"}
    )
    data = msgs.json()
    assert data[0]["message_type"] == "EXPENSE"
    assert data[0]["extracted_amount"] == "50.00"
    assert data[0]["transaction_id"] is not None


async def test_receive_webhook_income(client: AsyncClient, user_with_phone):
    response = await client.post(
        "/api/v1/whatsapp/webhook",
        json=_meta("+5511888888888", "Recebi R$2000 de salário"),
    )
    assert response.status_code == 200

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511888888888"}
    )
    data = msgs.json()
    assert data[0]["message_type"] == "INCOME"
    assert data[0]["transaction_id"] is not None


async def test_receive_webhook_query(client: AsyncClient, user_with_phone):
    response = await client.post(
        "/api/v1/whatsapp/webhook",
        json=_meta("+5511888888888", "Qual é meu saldo?"),
    )
    assert response.status_code == 200

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511888888888"}
    )
    data = msgs.json()
    assert data[0]["message_type"] == "QUERY"
    assert data[0]["transaction_id"] is None


async def test_receive_webhook_unknown_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/whatsapp/webhook",
        json=_meta("+5500000000001", "Gastei R$30 no bar"),
    )
    assert response.status_code == 200

    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5500000000001"}
    )
    data = msgs.json()
    assert data[0]["user_id"] is None
    assert data[0]["transaction_id"] is None


async def test_receive_webhook_ignores_non_text(client: AsyncClient):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "+5511777777777",
                        "id": "wamid.audio",
                        "timestamp": "1234567890",
                        "type": "audio",
                    }]
                },
                "field": "messages",
            }]
        }],
    }
    response = await client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    msgs = await client.get(
        "/api/v1/whatsapp/messages", params={"phone_number": "+5511777777777"}
    )
    assert msgs.json() == []


async def test_receive_webhook_ignores_status_update(client: AsyncClient):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {"messaging_product": "whatsapp"},
                "field": "messages",
            }]
        }],
    }
    response = await client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_list_messages_endpoint(client: AsyncClient, user_with_phone):
    await client.post("/api/v1/whatsapp/webhook", json=_meta("+5511888888888", "Gastei R$10 no café"))
    await client.post("/api/v1/whatsapp/webhook", json=_meta("+5511888888888", "Gastei R$20 no almoço"))

    response = await client.get(
        "/api/v1/whatsapp/messages",
        params={"phone_number": "+5511888888888"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


async def test_list_messages_empty(client: AsyncClient):
    response = await client.get(
        "/api/v1/whatsapp/messages",
        params={"phone_number": "+5599999999998"},
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_receive_webhook_empty_payload_returns_200(client: AsyncClient):
    response = await client.post("/api/v1/whatsapp/webhook", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
