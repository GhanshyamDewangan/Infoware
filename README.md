# 🤖 Persistent Sales Assistant Agent

> A production-grade AI Sales Assistant API — with persistent cross-session memory, real tool calling, and self-evaluation on every response.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-orange)](https://console.groq.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase)](https://supabase.com)
[![Railway](https://img.shields.io/badge/Deployed-Railway-0B0D0E?logo=railway)](https://railway.app)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)](https://docker.com)

---

## 🌐 Live URL

```
https://YOUR-APP.up.railway.app
```
> Replace with your Railway URL after deployment.

---

## 📐 Architecture

### Message Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT REQUEST                           │
│              POST /chat/{user_id}  {"message": "..."}           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Route Handler                      │
│                    app/api/chat.py                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Chat Service                              │
│                 app/services/chat_service.py                    │
│  1. Generate session_id (UUID)                                  │
│  2. Save user message → Supabase DB                             │
└────────────────┬──────────────────────────────────┬────────────┘
                 │                                  │
                 ▼                                  ▼
┌────────────────────────────┐      ┌───────────────────────────────┐
│       Memory Layer         │      │         Agent Loop            │
│  app/memory/               │      │    app/agents/agent.py        │
│  supabase_memory.py        │◄─────│                               │
│                            │      │  • Inject DB history context  │
│  - get_recent_context()    │      │  • Send to Groq with tools    │
│  - save_message()          │      │  • Handle tool_calls          │
│  - clear_memory()          │      │  • Loop until "stop"          │
└────────────────────────────┘      └──────────────┬────────────────┘
                                                   │
                          ┌────────────────────────┤
                          │         TOOLS          │
                          ▼                        ▼                        ▼
              ┌─────────────────┐    ┌──────────────────────┐   ┌──────────────────┐
              │ search_catalog  │    │  get_user_memory     │   │ flag_for_human   │
              │                 │    │                      │   │                  │
              │ Keyword search  │    │ Real DB query via    │   │ Writes to        │
              │ over            │    │ MemoryInterface      │   │ flagged_logs     │
              │ catalog.json    │    │ (PostgreSQL)         │   │ table            │
              └────────┬────────┘    └──────────┬───────────┘   └────────┬─────────┘
                       │                        │                        │
                       └────────────────────────┴────────────────────────┘
                                                │
                                                ▼
                                 ┌──────────────────────────┐
                                 │      Groq LLM            │
                                 │  llama-3.3-70b-versatile │
                                 │                          │
                                 │  Generates final         │
                                 │  response text           │
                                 └──────────────┬───────────┘
                                                │
                                                ▼
                               ┌────────────────────────────────┐
                               │       Eval Service             │
                               │  app/services/eval_service.py  │
                               │                                │
                               │  Second Groq LLM call:         │
                               │  • groundedness score          │
                               │  • relevance score             │
                               │  • confidence score            │
                               │  • flagged (bool)              │
                               │  • reasoning (text)            │
                               └──────────────┬─────────────────┘
                                              │
                                              ▼
                               ┌────────────────────────────────┐
                               │   Save to Supabase DB          │
                               │   (response + eval + tools)    │
                               └──────────────┬─────────────────┘
                                              │
                                              ▼
                               ┌────────────────────────────────┐
                               │      ChatResponse JSON         │
                               │  {response, eval, tools_called,│
                               │   session_id, user_id}         │
                               └────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
app/
├── api/                    # Route handlers only (thin layer)
│   ├── chat.py             # POST /chat, GET /history, DELETE /memory, GET /evals
│   └── catalog.py          # GET /catalog, GET /health
│
├── agents/                 # Agent loop + eval prompts
│   ├── agent.py            # Main Groq tool-calling agent loop
│   └── eval.py             # Eval system prompt and prompt builder
│
├── memory/                 # ABSTRACTED memory layer
│   ├── memory_interface.py # Abstract base class (MemoryInterface)
│   └── supabase_memory.py  # PostgreSQL implementation (swap here for new backend)
│
├── tools/                  # Real callable tool functions
│   ├── search_catalog.py   # Keyword search over catalog.json
│   ├── get_user_memory.py  # DB memory retrieval
│   └── flag_for_human.py   # Escalation to flagged_logs table
│
├── services/               # Business logic / orchestration
│   ├── chat_service.py     # Full pipeline: save → agent → eval → save → respond
│   └── eval_service.py     # Self-evaluation via second Groq LLM call
│
├── models/
│   └── schemas.py          # All Pydantic v2 request/response models
│
├── db/
│   ├── database.py         # SQLAlchemy async engine + session factory
│   └── models.py           # ORM table models (Message, FlaggedLog)
│
└── catalog.json            # Mock product catalog

main.py                     # FastAPI app + lifespan + routers
requirements.txt
Dockerfile
docker-compose.yml
railway.toml
.env.example
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- A [Groq API key](https://console.groq.com) (free tier works)
- A [Supabase project](https://supabase.com) (free tier works)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/sales-assistant-agent.git
cd sales-assistant-agent

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt --prefer-binary
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GROQ_API_KEY=gsk_your_key_here
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

> **Supabase DB URL**: Go to Supabase Dashboard → Settings → Database → Connection String (URI mode) → copy the URI and change `postgresql://` to `postgresql+asyncpg://`

### 3. Open the frontend

No build step needed — just open the HTML file directly in your browser:

```
frontend/index.html
```

Or, if the backend is running, open it in your browser via the file system. The UI will prompt you for:
- **User ID** — any string (e.g., `ghanshyam`)
- **API URL** — defaults to `http://localhost:8000`, change to your Railway URL for production

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### 4. Run with Docker

```bash
docker-compose up --build
```

---

## 🔗 API Reference

### `POST /chat/{user_id}`
Send a message. Get a response with self-eval scores.

**Request:**
```json
{
  "message": "What is your Enterprise pricing?"
}
```

**Response:**
```json
{
  "response": "Our Enterprise plan is $499/month and includes unlimited users, SSO (SAML 2.0), audit logs, 24/7 support with 1-hour SLA, and a dedicated account manager.",
  "eval": {
    "groundedness": 0.95,
    "relevance": 0.92,
    "confidence": 0.90,
    "flagged": false,
    "reasoning": "Response sourced directly from catalog. User context applied. No hallucination detected."
  },
  "tools_called": ["get_user_memory", "search_catalog"],
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "ghanshyam"
}
```

---

### `GET /chat/{user_id}/history`
Full conversation history across all sessions.

```bash
curl https://YOUR-APP.up.railway.app/chat/ghanshyam/history
```

---

### `DELETE /chat/{user_id}/memory`
GDPR-style memory wipe.

```bash
curl -X DELETE https://YOUR-APP.up.railway.app/chat/ghanshyam/memory
```

**Response:**
```json
{
  "message": "Memory cleared successfully for user 'ghanshyam'.",
  "user_id": "ghanshyam",
  "deleted_count": 12
}
```

---

### `GET /catalog`
Returns the product catalog.

---

### `GET /health`
Service health check (includes DB connectivity).

---

### `GET /chat/{user_id}/evals` *(Bonus)*
Aggregated eval stats — confidence rates, flag rates, etc.

---

## 🧠 Cross-Session Memory Demo

These two `curl` commands demonstrate persistent memory. **Run them sequentially** — the agent will remember the first conversation in the second call.

### Call 1 — Establish context
```bash
curl -X POST https://YOUR-APP.up.railway.app/chat/ghanshyam \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your Enterprise pricing and does it include SSO?"}'
```

**Expected response:** Agent explains Enterprise is $499/mo with SSO, audit logs, and SLA.

### Call 2 — Test memory (separate session, different `session_id`)
```bash
curl -X POST https://YOUR-APP.up.railway.app/chat/ghanshyam \
  -H "Content-Type: application/json" \
  -d '{"message": "Does the plan we discussed also include audit logs? And what is the uptime guarantee?"}'
```

**Expected response:** Agent remembers the Enterprise plan discussion and answers about audit logs and 99.99% SLA — **without the user repeating any context**.

> ✅ The second call uses a different `session_id` (auto-generated UUID), proving memory comes from the database — not the request payload or in-memory state.

---

## 🗄️ Memory Design

### What I used: Supabase PostgreSQL via SQLAlchemy async

**Why SQL over a vector DB for this use case:**
- Conversation history is naturally structured (role, content, timestamp)
- Exact retrieval by `user_id` is a simple indexed query — no semantic similarity needed
- SQL is ACID-compliant — no message is ever lost, even on crash
- Supabase gives us free PostgreSQL hosting + instant setup

**Memory abstraction (`MemoryInterface`):**
The memory layer is a Python ABC (Abstract Base Class). The current implementation (`SupabaseMemory`) is in one file. **Swapping to SQLite, Redis, or Mem0 requires changing exactly one file** — the concrete implementation — and updating one import in `chat_service.py`. The rest of the codebase is unaffected.

**What I'd use at scale:**
- **Short-term context**: PostgreSQL (current) — fast, indexed retrieval
- **Long-term semantic retrieval**: Add a vector DB (Qdrant, Pinecone) alongside SQL
- **Memory compression**: After 50+ messages, use an LLM to summarize older history into a `memory_summary` column — reducing token usage while preserving context
- **At 10M+ users**: Partition `messages` table by `user_id` hash, cache recent context in Redis

---

## 📊 Eval Design

### How it works

Every `/chat` response triggers a **second Groq LLM call** that scores the first response. The evaluator receives:
1. The original user question
2. The agent's response
3. The catalog context retrieved by `search_catalog`
4. The list of tools called

It returns a structured JSON with three scores:

| Score | What it measures |
|---|---|
| `groundedness` | Is the answer based on catalog data or hallucinated? |
| `relevance` | Does the answer actually address what the user asked? |
| `confidence` | Combined quality signal — triggers `flagged=true` if < 0.70 |

All scores are **always present** (never null), **always logged to the database**, and **always returned in the API response**.

### Limitations & What I'd replace it with

| Limitation | Production Solution |
|---|---|
| LLM self-scoring has upward bias (inflated scores) | **RAGAS** or **DeepEval** with reference-based metrics |
| The judge and the agent use the same model | Use a **different model** as the judge (e.g., judge with GPT-4o, agent with llama) |
| No ground-truth labels | Collect human ratings over time to fine-tune a dedicated judge model |
| Eval adds ~1s latency | Run eval **async in background** after returning the response to the user |

---

## 🔧 Tool Use — Not Hallucination

All three tools are **real callable Python functions** — not text injected into the system prompt.

| Tool | Implementation | Groq Integration |
|---|---|---|
| `search_catalog(query)` | Keyword search over `catalog.json` with scoring | JSON schema passed to Groq's `tools` parameter |
| `get_user_memory(user_id)` | SQLAlchemy async query to `messages` table | JSON schema passed to Groq's `tools` parameter |
| `flag_for_human(user_id, reason)` | Writes to `flagged_logs` table in DB | JSON schema passed to Groq's `tools` parameter |

The agent loop handles Groq's `tool_calls` response, dispatches to real functions, and feeds results back as `role: "tool"` messages — standard OpenAI-compatible tool calling format.

---

## 🚢 Railway Deployment

### Step-by-step

1. Push code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo
4. Add environment variables in Railway dashboard:
   - `GROQ_API_KEY` → your Groq key
   - `DATABASE_URL` → your Supabase connection string
5. Railway auto-detects `railway.toml` and deploys
6. Copy the generated Railway URL to this README

### Environment Variables on Railway

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | From console.groq.com |
| `DATABASE_URL` | From Supabase → Settings → Database |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `DEBUG` | `false` |

---

## 🛡️ Security Notes

- API keys are loaded from environment variables only — never hardcoded
- Database connections use SSL (`ssl=require` for Supabase)
- Docker runs as a non-root user
- `.env` is in `.gitignore` — only `.env.example` is committed

---

## 📝 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Framework | FastAPI | Async-native, auto docs, Pydantic integration |
| LLM | Groq `llama-3.3-70b-versatile` | Fastest inference, native tool calling, free tier |
| Database | Supabase PostgreSQL | Managed, free tier, PostgreSQL-compatible |
| ORM | SQLAlchemy async + asyncpg | True async, production-grade |
| Validation | Pydantic v2 | Type safety, auto-serialization |
| Deployment | Railway | One-click deploy, auto-HTTPS, free tier |
| Container | Docker | Reproducible builds, multi-stage |

---

## 👤 Author

Built as a take-home assignment demonstrating:
- **Persistent cross-session memory** (not in-memory dicts)
- **Real tool calling** (not string injection)
- **Structured self-evaluation** (always present, always logged)
- **Clean layered architecture** (memory abstraction, service separation)
