# Deploy no Railway

## Pré-requisitos
- Conta no [Railway.app](https://railway.app)
- Repositório no GitHub conectado ao Railway

## Passos

### 1. Criar novo projeto
1. Acesse railway.app → **New Project**
2. Selecione **Deploy from GitHub repo**
3. Escolha este repositório

### 2. Adicionar serviços
No painel do projeto, clique em **+ New Service**:
- **PostgreSQL** → Add Plugin → PostgreSQL
- **Redis** → Add Plugin → Redis

### 3. Configurar variáveis de ambiente
No serviço principal (backend), vá em **Variables** e adicione:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}` |
| `SECRET_KEY` | *(gere com `openssl rand -hex 32`)* |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `WHATSAPP_ACCESS_TOKEN` | *(token da Meta)* |
| `WHATSAPP_PHONE_NUMBER_ID` | `1132740066586311` |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | `2094674678136582` |
| `WHATSAPP_VERIFY_TOKEN` | *(token secreto do webhook)* |
| `AI_PROVIDER` | `claude` |
| `ANTHROPIC_API_KEY` | *(chave Anthropic)* |
| `OPENAI_API_KEY` | *(chave OpenAI — para Whisper)* |
| `LOG_LEVEL` | `INFO` |

> As variáveis `${{Postgres.DATABASE_URL}}` e `${{Redis.REDIS_URL}}` são referências
> automáticas do Railway — copie exatamente assim.

### 4. Aguardar build
O Railway vai:
1. Detectar `railway.json` e usar Nixpacks com Python 3.12
2. Instalar dependências via `pip install -r backend/requirements.txt`
3. Iniciar o servidor com `uvicorn`
4. As **migrations do Alembic rodam automaticamente** na primeira inicialização

### 5. Obter URL pública
Após o deploy, vá em **Settings → Domains** e copie a URL gerada
(ex: `https://hermes-production.up.railway.app`).

### 6. Configurar webhook na Meta
1. Acesse [Meta for Developers](https://developers.facebook.com)
2. Vá em seu app → **WhatsApp → Configuration → Webhook**
3. **Callback URL**: `https://SUA-URL.up.railway.app/api/v1/whatsapp/webhook`
4. **Verify Token**: o mesmo valor de `WHATSAPP_VERIFY_TOKEN`
5. Assine os eventos: `messages`

### 7. Testar
```bash
curl https://SUA-URL.up.railway.app/health
# Esperado: {"status":"ok","app":"Hermes",...}
```

## Variáveis Obrigatórias

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | URL do PostgreSQL (auto via Railway) |
| `REDIS_URL` | URL do Redis (auto via Railway) |
| `SECRET_KEY` | Chave JWT — mín. 32 chars |
| `WHATSAPP_ACCESS_TOKEN` | Token permanente da Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número WhatsApp |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | ID da conta Business |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificação do webhook |
| `ANTHROPIC_API_KEY` | Chave da API Claude (ou `OPENAI_API_KEY`) |

## Observações

- **Migrations**: rodam automaticamente no startup via `app/main.py` (lifespan handler).
  Não é necessário rodá-las manualmente.
- **DATABASE_URL**: o Railway fornece no formato `postgresql://...` — o app normaliza
  automaticamente para o driver correto (psycopg3/asyncpg).
- **Redis**: usado para cache e fila Celery. Se não configurar, o app funciona mas sem
  cache e sem tarefas assíncronas.
- **Health check**: disponível em `/health` — Railway usa para monitorar o serviço.
