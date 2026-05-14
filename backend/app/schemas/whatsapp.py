import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.infrastructure.database.models.whatsapp_message import MessageType


class InboundWebhookPayload(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=20)
    message_text: str = Field(..., min_length=1, max_length=4096)


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
