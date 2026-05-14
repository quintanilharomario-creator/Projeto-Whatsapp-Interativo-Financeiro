from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthorizationError
from app.infrastructure.database.session import get_db
from app.schemas.whatsapp import InboundWebhookPayload, WhatsappMessageResponse
from app.services.whatsapp_service import WhatsappService

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise AuthorizationError(detail="Token de verificação inválido")


@router.post("/webhook", response_model=WhatsappMessageResponse, status_code=201)
async def receive_webhook(
    payload: InboundWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    msg = await WhatsappService.receive_message(
        phone_number=payload.phone_number,
        message_text=payload.message_text,
        db=db,
    )
    return msg


@router.get("/messages", response_model=list[WhatsappMessageResponse])
async def list_messages(
    phone_number: str = Query(..., min_length=5, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await WhatsappService.list_messages(phone_number=phone_number, db=db, limit=limit)
