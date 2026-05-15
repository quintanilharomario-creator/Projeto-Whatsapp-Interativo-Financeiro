from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthorizationError
from app.infrastructure.database.session import get_db
from app.schemas.whatsapp import MetaWebhookPayload, WhatsappMessageResponse
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


@router.post("/webhook", status_code=200)
async def receive_webhook(
    payload: MetaWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """Receives Meta Cloud API webhook events. Always returns 200 as required by Meta."""
    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            for meta_msg in change.value.messages or []:
                if meta_msg.type != "text" or not meta_msg.text:
                    continue
                await WhatsappService.receive_message(
                    phone_number=meta_msg.from_,
                    message_text=meta_msg.text.body,
                    db=db,
                )
    return {"status": "ok"}


@router.post("/webhook/async", status_code=202)
async def receive_webhook_async(payload: MetaWebhookPayload):
    """Enqueue Meta webhook processing in Celery and return immediately."""
    from app.workers.tasks.whatsapp_tasks import process_whatsapp_message_task

    queued = []
    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            for meta_msg in change.value.messages or []:
                if meta_msg.type != "text" or not meta_msg.text:
                    continue
                task = process_whatsapp_message_task.delay(
                    meta_msg.from_, meta_msg.text.body
                )
                queued.append(task.id)
    return {"status": "queued", "tasks": queued}


@router.get("/messages", response_model=list[WhatsappMessageResponse])
async def list_messages(
    phone_number: str = Query(..., min_length=5, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await WhatsappService.list_messages(
        phone_number=phone_number, db=db, limit=limit
    )
