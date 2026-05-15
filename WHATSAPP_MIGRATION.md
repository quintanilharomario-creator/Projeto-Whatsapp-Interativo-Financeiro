# WhatsApp Provider Migration Guide

## Current State

**Active provider:** Evolution API (`WHATSAPP_PROVIDER=evolution`)
**Reason:** Meta Cloud API blocks sends to Brazilian numbers (+55) with error 130497.

---

## Why Evolution API (Temporary)

### Meta Error 130497

```
{
  "error": {
    "message": "Message failed to send because there are restrictions on how many messages can be sent from this phone number.",
    "type": "OAuthException",
    "code": 130497,
    "error_subcode": 2494097,
    "fbtrace_id": "..."
  }
}
```

**Root cause:** Meta test phone numbers (+1 555 xxx-xxxx) have geographic restrictions.
They can only send to pre-approved recipient numbers via **Templates**. Free-text
messages to Brazilian numbers (+55) are blocked on unverified test accounts.

### Evolution API as Bridge

Evolution API connects a real WhatsApp number via Baileys (WhatsApp Web protocol),
bypassing Meta's API entirely. It works immediately without verification, at the cost of:

- No official SLA from Meta
- Risk of WhatsApp account ban if used at high volume
- Requires a real WhatsApp SIM card connected 24/7

**Suitable for:** development, proof-of-concept, low-volume MVP.

---

## Architecture

```
User (WhatsApp)
      │
      ▼
Evolution API (Baileys) ─── POST /api/v1/evolution/webhook ──► FastAPI
      │                                                              │
      │  sends reply                                                 ▼
      └────────────────────────────────────────────── WhatsappService
                                                           │
                                          WHATSAPP_PROVIDER=evolution
                                                   EvolutionProvider
```

---

## How to Set Up Evolution API

```bash
# 1. Start the container (already in docker-compose.yml)
docker compose up -d evolution

# 2. Create the Baileys instance (once)
curl -X POST http://localhost:8000/api/v1/evolution/instance/create

# 3. Get QR code
curl http://localhost:8000/api/v1/evolution/instance/qrcode

# 4. Scan the base64 QR code with WhatsApp on your phone

# 5. Verify connection
curl http://localhost:8000/api/v1/evolution/instance/status
# Expected: {"state": "open", "connected": true}

# 6. Configure Evolution to send webhooks to your API
# In Evolution dashboard (http://localhost:8080/manager) or via API:
# Webhook URL: https://your-ngrok-url/api/v1/evolution/webhook
# Events: messages.upsert
```

---

## Migrating Back to Meta Cloud API

### Prerequisites

1. Complete **Meta Business Verification** (Etapa 3 in Meta Business Manager).
2. Add a **real phone number** as WhatsApp sender (not the +1 555 test number).
3. Create at least one approved message template for proactive sends.

### Steps

```bash
# 1. Update .env
WHATSAPP_PROVIDER=cloud_api
WHATSAPP_ACCESS_TOKEN=<real token from Meta Business>
WHATSAPP_PHONE_NUMBER_ID=<real phone number ID>
WHATSAPP_BUSINESS_ACCOUNT_ID=<account ID>

# 2. Register your webhook in Meta Business Manager:
# URL: https://your-domain/api/v1/whatsapp/webhook
# Verify token: value of WHATSAPP_VERIFY_TOKEN in .env
# Subscribe to: messages

# 3. Restart the API
uvicorn app.main:app --reload --port 8000
```

### Notes on 24-hour Window

After verification, text replies work only within 24 hours of the user's last message.
For proactive sends (reports, alerts), use approved templates:

```python
from app.infrastructure.whatsapp.cloud_api_provider import CloudAPIProvider

provider = CloudAPIProvider()
await provider.send_template(
    phone="5533999469497",
    template_name="monthly_report",   # must be pre-approved by Meta
    language_code="pt_BR",
)
```

---

## Alternative Providers

| Provider | Free trial | BR support | Notes |
|---|---|---|---|
| Twilio WhatsApp | Yes (sandbox) | Yes | Easy setup, usage-based pricing |
| 360dialog | No | Yes | Official BSP, best for scale |
| MessageBird | No | Yes | European pricing |
| Meta Cloud API | Yes (test) | After verification | Free up to 1000 conv/month |
| Evolution API | Self-hosted | Yes | Unofficial, dev/MVP only |

---

## Config Reference

```env
# Active provider
WHATSAPP_PROVIDER=evolution         # or cloud_api

# Evolution API
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=minha-chave-evolution-123
EVOLUTION_INSTANCE=saas-financeiro

# Meta Cloud API (for future migration)
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_BUSINESS_ACCOUNT_ID=
WHATSAPP_VERIFY_TOKEN=meu_token_secreto_de_verificacao
WHATSAPP_API_VERSION=v21.0
```
