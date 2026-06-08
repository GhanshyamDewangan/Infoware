# Persistent Sales Assistant Agent

A production-grade AI Sales Assistant API with persistent cross-session memory, real tool calling, and self-evaluation on every response.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-orange)](https://console.groq.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?logo=supabase)](https://supabase.com)
[![Railway](https://img.shields.io/badge/Deployed-Railway-0B0D0E?logo=railway)](https://railway.app)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)](https://docker.com)

---

## Live Deployments

* **Frontend Web Application**: https://infoware-xi.vercel.app/
* **Backend REST API**: https://infoware-production-6459.up.railway.app/

---

## Architecture and Message Flow

```mermaid
graph TD
    Client[Client Request] -->|POST /chat/user_id| FastAPI[FastAPI Route Handler]
    FastAPI -->|Request Payload| ChatService[Chat Service]
    
    subgraph Service Layer
        ChatService -->|1. Save User Message| DB[(Supabase PostgreSQL)]
        ChatService -->|2. Invoke Agent Loop| AgentLoop[Agent Loop]
        AgentLoop -->|3. Retrieve History| MemoryLayer[Memory Layer]
        MemoryLayer --> DB
        AgentLoop -->|4. Call Tools| Tools{Tools}
        Tools -->|search_catalog| SearchCatalog[search_catalog]
        Tools -->|get_user_memory| GetUserMemory[get_user_memory]
        Tools -->|flag_for_human| FlagForHuman[flag_for_human]
        
        SearchCatalog -->|Read| CatalogJson[catalog.json]
        GetUserMemory -->|Query| DB
        FlagForHuman -->|Write Log| DB
        
        AgentLoop -->|5. Generate Response| LLM[Groq LLM Llama-3.3-70b-versatile]
        ChatService -->|6. Run Evaluation| EvalService[Evaluation Service]
        EvalService -->|Assess Groundedness and Relevance| EvalLLM[Groq LLM Evaluator]
        EvalService -->|7. Save Evaluation and Final Response| DB
    end
    
    ChatService -->|8. Return Response and Evals| Client
```

---

## Project Structure

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
├── memory/                 # Abstracted memory layer
│   ├── memory_interface.py # Abstract base class (MemoryInterface)
│   └── supabase_memory.py  # PostgreSQL implementation (swap here for new backend)
│
├── tools/                  # Real callable tool functions
│   ├── search_catalog.py   # Keyword search over catalog.json
│   ├── get_user_memory.py  # DB memory retrieval
│   └── flag_for_human.py   # Escalation to flagged_logs table
│
├── services/               # Business logic / orchestration
│   ├── chat_service.py     # Full pipeline: save -> agent -> eval -> save -> respond
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

## Quick Start and Local Running Guide

### Prerequisites
* Python 3.11 or higher
* Groq API Key (from console.groq.com)
* Supabase PostgreSQL Database URI (with pgvector/SSL support)

### 1. Local Setup and Installation

Clone the repository and navigate to the project directory:
```bash
git clone https://github.com/GhanshyamDewangan/Infoware.git
cd Infoware
```

Create and activate a virtual environment:
```bash
# Windows:
python -m venv venv
venv\Scripts\activate

# macOS/Linux:
python -m venv venv
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt --prefer-binary
```

### 2. Environment Configuration

Copy the example environment file and configure it:
```bash
cp .env.example .env
```

Edit the `.env` file with your credentials:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
GROQ_MODEL=llama-3.3-70b-versatile
APP_NAME=Sales Assistant Agent
APP_VERSION=1.0.0
DEBUG=false
MEMORY_CONTEXT_LIMIT=20
EVAL_CONFIDENCE_THRESHOLD=0.70
```

Note: Supabase Connection URI must use `postgresql+asyncpg://` as the protocol for async SQLAlchemy compatibility.

### 3. Run Locally

Start the Uvicorn development server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
* Interactive Swagger API docs will be available at: http://localhost:8000/docs
* Open `frontend/index.html` directly in your browser. The frontend UI contains a hidden input field that automatically points to your production backend. For local testing, you can change the API URL configuration in the UI or let it connect to the default live URL.

### 4. Run with Docker

Alternatively, build and run using Docker Compose:
```bash
docker-compose up --build
```
This starts the backend application inside a container mapping port 8000.

---

## Deployment Instructions

### Deploy Backend on Railway

1. Push your code to GitHub.
2. Log in to [railway.app](https://railway.app) and create a New Project.
3. Choose Deploy from GitHub repo and select the Infoware repository.
4. Go to the Variables tab of the newly created service and add:
   * `GROQ_API_KEY`: Your Groq API credentials.
   * `DATABASE_URL`: Your Supabase connection string.
   * `GROQ_MODEL`: `llama-3.3-70b-versatile`.
   * `DEBUG`: `false`.
   * `MEMORY_CONTEXT_LIMIT`: `20`.
   * `EVAL_CONFIDENCE_THRESHOLD`: `0.70`.
5. Go to the Settings tab -> Networking -> click Generate Domain. Railway will compile the codebase using the Dockerfile and Nixpacks configuration and launch it.

### Deploy Frontend on Vercel

1. Log in to [vercel.com](https://vercel.com).
2. Choose Add New -> Project -> import your Infoware repository.
3. Edit the Root Directory setting to select the `frontend` folder.
4. Click Deploy. Vercel will host the static frontend files and update automatically on every commit.

---

## Testing Scenarios and Queries

Use these test queries in your frontend interface to validate the system's capabilities:

### Test Case 1: Catalog Tool Verification
These queries verify that the agent successfully fetches information from the local mock catalog instead of hallucinating:
* **Query**: "What is the pricing for the Growth plan, and does it include custom roles?"
  * **Expected Behavior**: Agent calls `search_catalog` and responds that the plan is $199/mo and includes custom roles.
* **Query**: "Do you offer an on-premise deployment option?"
  * **Expected Behavior**: Agent retrieves that on-premise deployment is exclusive to the Enterprise plan ($499/mo) and details it.
* **Query**: "Is there any discount for startups?"
  * **Expected Behavior**: Agent references the FAQ portion of the catalog and answers that startups get a 30% discount.

### Test Case 2: Cross-Session Memory Verification
These sequential queries verify that the database-backed memory successfully keeps track of conversation contexts across separate sessions:
* **Query 1**: "Hi, I am looking for a plan for my team of 15 users. What do you recommend?"
  * **Expected Behavior**: Agent recommends the Growth plan (which supports up to 25 users).
* **Query 2**: "How much storage will I get with the plan we just discussed?"
  * **Expected Behavior**: Agent remembers the recommended plan and responds: "The Growth plan includes 100 GB of storage."
* **Query 3**: "What is the SLA for this plan?"
  * **Expected Behavior**: Agent correctly remembers the plan is Growth and responds: "The uptime SLA for the Growth plan is 99.9%."

### Test Case 3: Human Escalation Tool Verification
These queries test the agent's logic for executing the `flag_for_human` tool when encountering requests outside its predefined boundaries:
* **Query**: "I want a custom 50% discount for my company. Can you authorize this?"
  * **Expected Behavior**: Agent detects it lacks authorization, calls `flag_for_human`, flags the response, and tells the user that the request has been escalated to sales (sales@saasco.io).
* **Query**: "My API is throwing a 502 Bad Gateway error. How do I fix my database connection?"
  * **Expected Behavior**: Agent recognizes it is a sales bot, not a support tech, calls `flag_for_human`, and directs the user to support (support@saasco.io).

### Test Case 4: Evaluation and Scoring Verification
* Examine the metrics section underneath every bot response.
* Check that `groundedness`, `relevance`, and `confidence` scores are populated between 0.00 and 1.00.
* Confirm that any query failing the evaluation threshold (confidence < 0.70) receives the Flagged badge.

---

## API Reference

### Send Message
* **Endpoint**: `POST /chat/{user_id}`
* **Headers**: `Content-Type: application/json`
* **Request Body**:
```json
{
  "message": "What is your Enterprise pricing?"
}
```
* **Response Body**:
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

### Get History
* **Endpoint**: `GET /chat/{user_id}/history`
* **Response**: Returns full chat logs and evaluation metrics for a user across all sessions.

### Delete Memory
* **Endpoint**: `DELETE /chat/{user_id}/memory`
* **Response**: Clears all database records for the specific user.

### Get Health Status
* **Endpoint**: `GET /health`
* **Response**:
```json
{
  "status": "healthy",
  "app_name": "Sales Assistant Agent",
  "version": "1.0.0",
  "database": "connected"
}
```

---

## Memory and Evaluation Architecture Details

### Memory Implementation
The memory layer is modeled using Python Abstract Base Classes (`MemoryInterface`). This makes swapping the active database (e.g., from PostgreSQL to SQLite, Redis, or DynamoDB) a single-file change in `app/memory/`. Currently, the `SupabaseMemory` implementation performs indexed SQL queries against a PostgreSQL database hosted by Supabase.

For scaling to millions of users, we recommend:
* Setting up Redis caches for active sessions.
* Running LLM-based summarization cycles after 50 messages to compact older histories.
* Sharding the PostgreSQL table by user hashes.

### Self-Evaluation System
Every transaction is validated by an independent LLM judge call. The evaluator assesses the response against the catalog search results and outputs quality metrics. Responses scoring low confidence are immediately flagged and pushed to the `flagged_logs` table for human oversight.

---

## Tech Stack

* **Web Framework**: FastAPI (Async-native routing, auto Swagger documentation)
* **AI Core**: Groq Llama-3.3-70b-versatile (high-speed tool calling)
* **Database**: Supabase PostgreSQL (SQLAlchemy async + asyncpg backend)
* **Deployment**: Railway (Backend containers) + Vercel (Static frontend pages)
* **Packaging**: Docker multi-stage builds

---

## Author

Take-home assignment solution demonstrating persistent cross-session memory, native LLM tool invocation, and automated self-evaluation.
