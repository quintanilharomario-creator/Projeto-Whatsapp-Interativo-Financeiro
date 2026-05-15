import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://graph.facebook.com"


class CloudAPIProvider:
    def __init__(self) -> None:
        self._phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self._url = f"{_BASE_URL}/{settings.WHATSAPP_API_VERSION}/{self._phone_number_id}/messages"
        self._headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    async def send_message(self, phone: str, message: str) -> bool:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self._url, headers=self._headers, json=payload)
            if response.status_code == 200:
                logger.info("whatsapp_message_sent", phone=phone)
                return True
            logger.warning(
                "whatsapp_send_failed",
                phone=phone,
                status=response.status_code,
                body=response.text[:200],
            )
            return False
        except httpx.HTTPError as exc:
            logger.error("whatsapp_http_error", phone=phone, error=str(exc))
            return False
