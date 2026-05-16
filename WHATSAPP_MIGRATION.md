# WhatsApp — Meta Cloud API

## Provider atual

**Provider:** Meta Cloud API (`WHATSAPP_PROVIDER=cloud_api`)

O projeto usa exclusivamente a [API oficial do WhatsApp Business (Meta Cloud API)](https://developers.facebook.com/docs/whatsapp/cloud-api).

---

## Configuração

```env
WHATSAPP_PROVIDER=cloud_api
WHATSAPP_ACCESS_TOKEN=<token do Meta Business Manager>
WHATSAPP_PHONE_NUMBER_ID=<ID do número registrado>
WHATSAPP_BUSINESS_ACCOUNT_ID=<ID da conta de negócios>
WHATSAPP_VERIFY_TOKEN=<token de verificação do webhook>
WHATSAPP_API_VERSION=v21.0
```

### Configurar o webhook no Meta Business Manager

1. Acesse **Meta Business Manager → WhatsApp → Configuração → Webhooks**.
2. URL do webhook: `https://your-domain/api/v1/whatsapp/webhook`
3. Token de verificação: valor de `WHATSAPP_VERIFY_TOKEN` no `.env`
4. Assinar o evento: `messages`

---

## Janela de 24 horas

Respostas de texto livre funcionam apenas dentro de 24 h após a última mensagem
do usuário. Para envios proativos (relatórios, alertas), use templates aprovados:

```python
from app.infrastructure.whatsapp.cloud_api_provider import CloudAPIProvider

provider = CloudAPIProvider()
await provider.send_template(
    phone="5533999469497",
    template_name="monthly_report",   # deve ser pré-aprovado pela Meta
    language_code="pt_BR",
)
```

---

## Arquitetura

```
User (WhatsApp)
      │
      ▼
Meta Cloud API ── POST /api/v1/whatsapp/webhook ──► FastAPI
                                                        │
                                                        ▼
                                               WhatsappService
                                                        │
                                               CloudAPIProvider
                                          (WHATSAPP_PROVIDER=cloud_api)
```

---

## Referência de variáveis

| Variável | Descrição |
|---|---|
| `WHATSAPP_PROVIDER` | Sempre `cloud_api` |
| `WHATSAPP_ACCESS_TOKEN` | Token do Meta Business Manager |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número remetente registrado na Meta |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | ID da conta de negócios Meta |
| `WHATSAPP_VERIFY_TOKEN` | Token para verificação do webhook |
| `WHATSAPP_API_VERSION` | Versão da API Meta (padrão: `v21.0`) |
