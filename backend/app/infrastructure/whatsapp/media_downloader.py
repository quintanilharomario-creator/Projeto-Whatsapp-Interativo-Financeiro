import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_GRAPH_BASE = "https://graph.facebook.com"


async def download_audio(media_id: str) -> bytes:
    """Fetch audio bytes from Meta Cloud API.

    Step 1: resolve media_id → download URL via Graph API.
    Step 2: download the actual audio file using the URL.
    """
    access_token = settings.WHATSAPP_ACCESS_TOKEN
    version = settings.WHATSAPP_API_VERSION

    async with httpx.AsyncClient(timeout=30.0) as client:
        meta_resp = await client.get(
            f"{_GRAPH_BASE}/{version}/{media_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("url", "")
        if not download_url:
            raise ValueError(f"No download URL returned for media_id={media_id}")

        logger.info("audio_url_resolved", media_id=media_id)

        audio_resp = await client.get(
            download_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        audio_resp.raise_for_status()

    logger.info("audio_downloaded", media_id=media_id, bytes=len(audio_resp.content))
    return audio_resp.content
