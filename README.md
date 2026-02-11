# MoneyMaker-API — Backend-only SaaS Starter

Production-ready **API-as-a-Service** backend: FastAPI, PostgreSQL, Redis, Celery, Stripe. No public HTML — JSON API only.

## Features

- **FastAPI** — OpenAPI docs, async, JWT auth
- **PostgreSQL + SQLAlchemy 2.0 + Alembic** — Users, plans, subscriptions, usage, invoices
- **Stripe** — Checkout, subscriptions, webhooks
- **Celery + Redis** — Background jobs (e.g. content generation), rate limiting
- **Docker Compose** — One-command local run
- **CI** — GitHub Actions: test, build, push image  
- **Observability** — Prometheus `/metrics` with `ollama_up` gauge (1/0), updated when `/health/ollama` is called

## Quick start (Docker)

```bash
# 1. Copy env and set secrets
cp .env.example .env
# Edit .env: JWT_SECRET_KEY (min 16 chars), STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET

# 2. Start stack
docker compose up -d --build

# 3. Run migrations
docker compose exec api alembic upgrade head

# 4. Seed Free plan (optional; new users get Free if this plan exists)
docker compose exec api python -c "
import asyncio
from app.db.session import async_session
from app.db import models
from sqlalchemy import select

async def main():
    async with async_session() as db:
        r = await db.execute(select(models.Plan).where(models.Plan.name == 'Free'))
        if r.scalar_one_or_none() is None:
            db.add(models.Plan(
                name='Free',
                description='100 calls/month, no card required',
                stripe_price_id='price_0FREE',
                price_usd=0,
                monthly_quota=100,
                is_active=True,
            ))
            await db.commit()
            print('Free plan created')
asyncio.run(main())
"
```

- **API docs:** http://localhost:8000/docs  
- **Health:** http://localhost:8000/health  
- **Ollama health:** http://localhost:8000/health/ollama (also updates the `ollama_up` Prometheus gauge)  
- **Metrics:** http://localhost:8000/metrics (includes `ollama_up` 1/0 for Ollama liveness)  

## Local dev (no Docker)

```bash
python -m venv .venv
.venv\Scripts\activate   # or source .venv/bin/activate
pip install -r requirements.txt
# Set DATABASE_URL (Postgres), REDIS_URL, JWT_SECRET_KEY in .env
alembic upgrade head
uvicorn app.main:app --reload
# In another terminal: celery -A app.workers.tasks worker --loglevel=info
```

## API flow

1. **Register** `POST /auth/register` → get access + refresh token (and Free plan if seeded).
2. **Login** `POST /auth/login` → tokens.
3. **Generate** `POST /service/generate` (Bearer token) → job_id; poll `GET /service/status/{job_id}` for result.
4. **Usage** `GET /usage/me` → current usage and quota.
5. **Plans** `GET /subscription/plans` → list plans; `POST /subscription/checkout/{plan_id}` → Stripe checkout URL.

## Python SDK

The SDK is a separate installable package under `sdk/python/`. To install it locally in editable mode (bound to your repo):

```bash
pip install -e "sdk/python[dev]"
```

(Omit `[dev]` if you don't need the dev extras: pytest, requests-mock, etc.)

Then use it from any script or REPL:

```python
from myai_client import MyAIClient, MyAIClientError

client = MyAIClient(base_url="http://localhost:8000")
client.login("alice@example.com", "SuperSecret123")
print(client.summarise("Your long text here..."))
```

You can also run without installing by setting `PYTHONPATH` to the repo root and importing `from sdk.python import MyAIClient`. See [sdk/python/README.md](sdk/python/README.md) for full usage.

**Node / TypeScript SDK** – See [sdk/node/](sdk/node/). Install with `npm i myai-client` (or from the repo: `cd sdk/node && npm install && npm run build`). Same workflow: `register`, `login`, `summarise(text)`.

## Graceful shutdown

- **API:** On SIGTERM, FastAPI runs a shutdown handler that closes the Redis connection and disposes the DB engine so the process exits cleanly (e.g. on Kubernetes, Fly.io, Render).
- **Worker:** The Celery worker runs with `--pool=solo` so a single process handles tasks and exits cleanly on SIGTERM without leaving orphan processes.

## Security checklist

- HTTPS in production; strong `JWT_SECRET_KEY` (e.g. `openssl rand -hex 32`).
- Stripe webhook URL over HTTPS; use test keys in dev.
- CORS, rate limits, and quotas are in place; tighten CORS for production.

## License

See LICENSE.
