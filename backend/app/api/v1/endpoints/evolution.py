from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.infrastructure.database.session import get_db
from app.infrastructure.whatsapp.evolution_provider import EvolutionProvider
from app.services.whatsapp_service import WhatsappService

logger = get_logger(__name__)
router = APIRouter(prefix="/evolution", tags=["evolution"])


# ── Instance endpoints ─────────────────────────────────────────────────────


@router.post("/instance/create", status_code=201)
async def create_instance():
    """Create the Evolution API Baileys instance (run once at setup)."""
    try:
        provider = EvolutionProvider()
        data = await provider.create_instance()
        return {"status": "created", "instance": data.get("instance", {})}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/instance/qrcode")
async def get_qr_code():
    """Return QR code for scanning with WhatsApp. Scan within 60 seconds."""
    try:
        provider = EvolutionProvider()
        data = await provider.get_qr_code()
        if not data.get("base64"):
            return {
                "status": "waiting",
                "message": "QR code not yet available — instance may be connecting or already open.",
                "raw": data,
            }
        return {"status": "ok", "base64": data["base64"], "count": data.get("count")}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/instance/status")
async def get_instance_status():
    """Check if the WhatsApp instance is open (connected), connecting, or closed."""
    try:
        provider = EvolutionProvider()
        data = await provider.get_instance_status()
        instance = data.get("instance", {})
        return {
            "instance": instance.get("instanceName"),
            "state": instance.get("state"),
            "connected": instance.get("state") == "open",
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ── Webhook ────────────────────────────────────────────────────────────────


class _EvolutionMessageKey(BaseModel):
    remoteJid: str = ""
    fromMe: bool = False
    id: str = ""


class _EvolutionMessageContent(BaseModel):
    conversation: str | None = None
    extendedTextMessage: dict | None = None


class _EvolutionMessageData(BaseModel):
    key: _EvolutionMessageKey = Field(default_factory=_EvolutionMessageKey)
    message: _EvolutionMessageContent | None = None
    messageType: str = ""
    pushName: str = ""


class EvolutionWebhookPayload(BaseModel):
    event: str = ""
    instance: str = ""
    data: _EvolutionMessageData = Field(default_factory=_EvolutionMessageData)


def _extract_text(data: _EvolutionMessageData) -> str | None:
    if not data.message:
        return None
    if data.message.conversation:
        return data.message.conversation
    ext = data.message.extendedTextMessage
    if isinstance(ext, dict):
        return ext.get("text")
    return None


@router.post("/webhook", status_code=200)
async def evolution_webhook(
    payload: EvolutionWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """Receive inbound messages from Evolution API. Always returns 200."""
    if payload.event != "messages.upsert":
        return {"status": "ignored", "event": payload.event}

    data = payload.data
    if data.key.fromMe:
        return {"status": "ignored", "reason": "outbound"}

    text = _extract_text(data)
    if not text:
        return {"status": "ignored", "reason": "non-text message"}

    # Strip @s.whatsapp.net suffix that Evolution appends to JIDs
    phone = data.key.remoteJid.split("@")[0]

    logger.info("evolution_webhook_received", phone=phone, text=text[:50])
    await WhatsappService.receive_message(
        phone_number=phone,
        message_text=text,
        db=db,
    )
    return {"status": "ok"}
