# SaaS Financeiro com WhatsApp

Sistema de gestão financeira pessoal integrado ao WhatsApp com IA.
O usuário envia mensagens como "Gastei R$50 no mercado" e o sistema registra, categoriza e analisa automaticamente.

---

## Stack

| Camada | Tecnologia | Versão |
|---|---|---|
| Backend | Python + FastAPI | 3.12+ |
| Banco de dados | PostgreSQL | 16+ |
| Cache / Filas | Redis | 7+ |
| IA | OpenAI / Anthropic | - |
| Mensageria | Meta Cloud API (WhatsApp Business) | - |
| Armazenamento | MinIO / S3 | - |
| Containers | Docker Compose | - |

---

## Pré-requisitos

- Python 3.12+
- Docker e Docker Compose
- Chave de API OpenAI ou Anthropic

---

## Instalação

```bash
# 1. Clone e entre no backend
git clone <repo>
cd saas-financeiro/backend

# 2. Crie o ambiente virtual e instale dependências
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves e senhas reais

# 4. Suba a infraestrutura
cd ..
docker compose up -d

# 5. Crie o banco de teste (necessário apenas uma vez)
cd backend
createdb -U saas_user saas_financeiro_test  # ou via psql

# 6. Execute as migrações
alembic upgrade head

# 7. Suba o servidor de desenvolvimento
uvicorn app.main:app --reload --port 8000
```

API disponível em: `http://localhost:8000`
Docs (Swagger): `http://localhost:8000/docs`

---

## Testes

```bash
cd backend

# Todos os testes (178 testes, ~93% cobertura)
pytest

# Com relatório de cobertura
pytest --cov=app --cov-report=term-missing

# Arquivo específico
pytest tests/test_auth_service.py -v
```

---

## Linting e formatação

```bash
cd backend

ruff check app/          # lint
ruff format app/         # format
mypy app/                # type check
```

---

## Endpoints principais

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/auth/register` | Cadastro de usuário |
| `POST` | `/api/v1/auth/login` | Login / obtenção de token |
| `GET` | `/api/v1/auth/me` | Usuário autenticado |
| `POST` | `/api/v1/transactions` | Criar transação |
| `GET` | `/api/v1/transactions` | Listar transações |
| `GET` | `/api/v1/reports/balance` | Saldo atual |
| `GET` | `/api/v1/reports/summary` | Resumo mensal |
| `POST` | `/api/v1/whatsapp/webhook` | Webhook Meta Cloud API |
| `POST` | `/api/v1/ai/analyze` | Analisar transação com IA |

Documentação completa em `/docs` (Swagger) ou `/redoc`.

---

## Variáveis de ambiente obrigatórias

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave JWT — gerar com `openssl rand -hex 32` |
| `DATABASE_URL` | URL do PostgreSQL |
| `OPENAI_API_KEY` | Chave da API OpenAI (se `AI_PROVIDER=openai`) |
| `ANTHROPIC_API_KEY` | Chave da API Anthropic (se `AI_PROVIDER=claude`) |

Ver `.env.example` para a lista completa.

---

## WhatsApp

O sistema usa a **Meta Cloud API** (WhatsApp Business API oficial).

Configure as variáveis `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` e `WHATSAPP_BUSINESS_ACCOUNT_ID` no `.env`.
O webhook deve ser registrado no Meta Business Manager apontando para `/api/v1/whatsapp/webhook`.

Consulte [`WHATSAPP_MIGRATION.md`](WHATSAPP_MIGRATION.md) para documentação completa.

---

## Arquitetura

```
backend/app/
├── api/           # Endpoints FastAPI (rotas, middleware, deps)
├── core/          # Config, exceptions, logging, security
├── domain/        # Entidades e regras de negócio (sem framework)
├── infrastructure/ # DB, AI, cache, WhatsApp, áudio
├── schemas/       # Modelos Pydantic de request/response
├── services/      # Casos de uso (orquestram domain + infra)
└── workers/       # Tasks Celery (IA, áudio, WhatsApp)
```

Direção de dependências: `api → services → domain`; `infrastructure` implementa contratos de `domain/interfaces`.
