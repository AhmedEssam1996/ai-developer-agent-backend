# MyWork AI — AI Work Operating System

> Stop switching between Outlook, Teams, Calendar and GoodDay. MyWork AI understands your work context and helps you act on it.

MyWork AI connects your work tools into one intelligent workspace. It normalizes email, calendar, chat and task data into a single unified model, then layers a tool-using AI agent on top that can search, summarize, connect information, detect commitments, prepare meetings, and perform **approved** actions.

## Monorepo layout

```
.
├── backend/            # FastAPI + SQLAlchemy + Redis + agent runtime
├── frontend/           # Next.js (App Router) + TypeScript + Tailwind
├── docker-compose.yml  # Postgres (+ pgvector) + Redis + backend + frontend
├── .env.example        # All required configuration
└── README.md
```

## Architecture

```
Frontend (Next.js)
   │ REST + SSE
   ▼
FastAPI API layer
   │
   ▼
Agent Gateway → Intent → Context Retrieval → Planner → Tool Selection
   → Tool Execution → Observation → Reasoning/Replanning → streamed response
   │
   ├── Policies & Approval gate (WRITE tools require human approval)
   ├── Memory (structured facts · external records · semantic · temp context)
   └── Observability + Audit
   │
Integration layer (normalized models only):
   Microsoft Graph (Outlook Mail/Calendar, Teams) · GoodDay · isolated MockAdapter
   │
Sync engine (incremental, idempotent) → PostgreSQL / Redis
```

Key principles:

- Business logic **never** talks to a provider directly — everything goes through an integration adapter returning normalized internal models.
- The AI is **not** `frontend → OpenRouter → text`. It is a tool-using agent with planner, executor, policies and approval gates.
- External content (emails, Teams messages, docs) is **untrusted input** and can never authorize a side effect or override instructions.
- Write actions require approval according to policy.

## Quick start (Docker)

```bash
cp .env.example .env      # fill in OPENROUTER_API_KEY (+ optional Microsoft/GoodDay)
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend + Swagger: http://localhost:8000/docs

## Quick start (local)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m app.db.init_db          # create tables (alembic available too)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Configuration — see `.env.example`

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key |
| `TOKEN_ENCRYPTION_KEY` | Fernet key for OAuth token encryption at rest |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | AI gateway (server-side only) |
| `MICROSOFT_CLIENT_ID` / `_SECRET` / `_TENANT_ID` / `_REDIRECT_URI` | Entra app registration |
| `GOODDAY_API_KEY` / `GOODDAY_BASE_URL` | GoodDay API |
| `INTEGRATION_MODE` | `live` or `mock` |
| `FRONTEND_BASE_URL` / `BACKEND_BASE_URL` | CORS + redirects |

### Microsoft (Entra) app registration

1. Create an app registration in Microsoft Entra ID.
2. Add Web redirect URI `http://localhost:8000/api/integrations/microsoft/callback`.
3. Create a client secret.
4. Grant delegated, least-privilege permissions: `openid`, `offline_access`, `User.Read`, `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`, `Chat.Read`, `ChatMessage.Send`, `ChannelMessage.Read.All`.
5. Set `MICROSOFT_*` in `.env`.

### GoodDay

1. Generate an API key in GoodDay (Settings → API).
2. Set `GOODDAY_API_KEY`.

> **No credentials?** Set `INTEGRATION_MODE=mock`. Integration calls route through an isolated mock adapter returning clearly-labeled synthetic data. The UI shows a persistent "Development data" badge so mock data is never mistaken for real. Production code paths are unchanged.

## Database

SQLAlchemy 2.0 async models + Alembic migrations. Tables: `users`, `organizations`, `memberships`, `integrations`, `oauth_accounts`, `projects`, `tasks`, `emails`, `messages`, `calendar_events`, `people`, `agent_runs`, `agent_messages`, `agent_actions`, `action_approvals`, `commitments`, `sync_states`, `audit_logs`, `memory_items`.

Every external record stores `source` + `external_id` with a unique constraint so sync is **idempotent**.

## AI Agent

- **Provider abstraction**: `AIProvider` → `OpenRouterProvider` (streaming, tool calls, retries, timeouts, token accounting).
- **Tools**: separated into READ (auto-run) and WRITE (approval-gated).
- **Approval**: WRITE tools create a `pending_approval` action; UI renders Approve / Edit / Cancel; execution proceeds only after approval.
- **Observability**: Activity panel shows concise tool status (never chain-of-thought), latency, token usage, errors.

### Prompt-injection defense

External content is wrapped in a delimited, explicitly-untrusted envelope before reaching the model. A heuristic scanner flags injection attempts. Critically, **write actions always require human approval**, so no email can autonomously trigger an external side effect.

## Testing

```bash
cd backend && pytest -q
```

Covers auth, normalization, integration adapters, agent tool gating, approval policy, orchestration, sync idempotency, and prompt-injection protection.

## License

MIT.