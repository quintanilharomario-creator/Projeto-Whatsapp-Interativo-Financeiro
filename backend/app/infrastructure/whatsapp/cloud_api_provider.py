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

    async def send_text(self, phone: str, message: str) -> bool:
        """Free-text message — only works inside a 24-hour user-initiated window."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        return await self._post(payload, phone, msg_type="text")

    async def send_template(
        self,
        phone: str,
        template_name: str = "hello_world",
        language_code: str = "en_US",
    ) -> bool:
        """Template message — works anytime, required outside the 24-hour window."""
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        return await self._post(payload, phone, msg_type=f"template:{template_name}")

    async def send_message(
        self,
        phone: str,
        message: str,
        within_window: bool = True,
    ) -> bool:
        """Smart dispatch: free text inside 24-hour window, template outside."""
        if within_window:
            return await self.send_text(phone, message)
        return await self.send_template(phone)

    async def _post(self, payload: dict, phone: str, msg_type: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._url, headers=self._headers, json=payload
                )
            if response.status_code == 200:
                logger.info("whatsapp_message_sent", phone=phone, type=msg_type)
                return True
            logger.warning(
                "whatsapp_send_failed",
                phone=phone,
                type=msg_type,
                status=response.status_code,
                body=response.text[:200],
            )
            return False
        except httpx.HTTPError as exc:
            logger.error("whatsapp_http_error", phone=phone, error=str(exc))
            return False
