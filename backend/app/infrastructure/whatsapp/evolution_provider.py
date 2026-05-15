"""
Evolution API provider — temporary WhatsApp integration.

CONTEXT: Meta Cloud API blocks sends to Brazilian numbers (+55) with error
130497 (geographic restriction on unverified test accounts). Evolution API
is used as a bridge until one of the following is completed:
  1. Meta business account verification (Meta Etapa 3)
  2. Migration to a verified provider: Twilio, 360dialog, MessageBird, or
     Meta Cloud API post-verification.

See WHATSAPP_MIGRATION.md at the project root for the full migration plan.
"""

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EvolutionProvider:
    def __init__(self) -> None:
        self._base_url = settings.EVOLUTION_API_URL.rstrip("/")
        self._headers = {
            "apikey": settings.EVOLUTION_API_KEY,
            "Content-Type": "application/json",
        }
        self._instance = settings.EVOLUTION_INSTANCE

    # ── Instance management ────────────────────────────────────────────────

    async def create_instance(self, instance_name: str | None = None) -> dict:
        """Create (or re-create) a Baileys instance in Evolution API."""
        name = instance_name or self._instance
        payload = {
            "instanceName": name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._base_url}/instance/create",
                headers=self._headers,
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        logger.info("evolution_instance_created", instance=name)
        return data

    async def get_qr_code(self, instance_name: str | None = None) -> dict:
        """Return QR code data for scanning. State: 'base64' key holds the image."""
        name = instance_name or self._instance
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/instance/connect/{name}",
                headers=self._headers,
            )
        response.raise_for_status()
        return response.json()

    async def get_instance_status(self, instance_name: str | None = None) -> dict:
        """Return connection state for the instance (open | connecting | close)."""
        name = instance_name or self._instance
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._base_url}/instance/connectionState/{name}",
                headers=self._headers,
            )
        response.raise_for_status()
        return response.json()

    # ── Messaging ──────────────────────────────────────────────────────────

    async def send_message(
        self,
        phone: str,
        message: str,
        instance_name: str | None = None,
    ) -> bool:
        """Send a free-text message via Baileys (no 24-hour window restriction)."""
        name = instance_name or self._instance
        # Evolution API expects bare number (no @s.whatsapp.net suffix)
        number = phone.replace("@s.whatsapp.net", "").replace("+", "")
        payload = {"number": number, "text": message}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._base_url}/message/sendText/{name}",
                    headers=self._headers,
                    json=payload,
                )
            if response.status_code == 201:
                logger.info("evolution_message_sent", phone=number, instance=name)
                return True
            logger.warning(
                "evolution_send_failed",
                phone=number,
                status=response.status_code,
                body=response.text[:200],
            )
            return False
        except httpx.HTTPError as exc:
            logger.error("evolution_http_error", phone=number, error=str(exc))
            return False
