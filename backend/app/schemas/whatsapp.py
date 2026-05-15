import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.infrastructure.database.models.whatsapp_message import MessageType


class InboundWebhookPayload(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=20)
    message_text: str = Field(..., min_length=1, max_length=4096)


# ── Meta Cloud API webhook payload ───────────────────────────────────────────


class MetaTextContent(BaseModel):
    body: str = ""


class MetaMessage(BaseModel):
    from_: str = Field(alias="from", default="")
    id: str = ""
    timestamp: str = ""
    type: str = ""
    text: MetaTextContent | None = None

    model_config = {"populate_by_name": True}


class MetaValue(BaseModel):
    messaging_product: str = ""
    messages: list[MetaMessage] | None = None


class MetaChange(BaseModel):
    value: MetaValue = Field(default_factory=MetaValue)
    field: str = ""


class MetaEntry(BaseModel):
    id: str = ""
    changes: list[MetaChange] = []


class MetaWebhookPayload(BaseModel):
    object: str = ""
    entry: list[MetaEntry] = []


class WhatsappMessageResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    phone_number: str
    message_text: str
    message_type: MessageType
    extracted_amount: Decimal | None
    category: str | None
    confidence: float | None
    response_text: str | None
    transaction_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookVerifyParams(BaseModel):
    hub_mode: str = Field(alias="hub.mode")
    hub_verify_token: str = Field(alias="hub.verify_token")
    hub_challenge: str = Field(alias="hub.challenge")

    model_config = {"populate_by_name": True}


# Alias used by external audits / tooling
WhatsappMessageReceive = InboundWebhookPayload
