# 🧠 AI Digital Twin — Backend System

A production-grade FastAPI backend that creates a continuously evolving personal AI clone.
The twin understands who you are, remembers every meaningful exchange, and responds *as you*.

---

## Architecture Overview

```
Client (HTTP/REST)
       │
       ▼
┌─────────────────────────────────────────────┐
│           API LAYER  (FastAPI)              │
│  /auth  /chat  /personality  /memory       │
└───────────────┬─────────────────────────────┘
                │ Depends()
┌───────────────▼─────────────────────────────┐
│           SERVICE LAYER                     │
│  AuthService │ ChatService                  │
│  PersonalityService │ MemoryService         │
│  AIService │ PromptBuilder                  │
└───────┬───────────────────┬─────────────────┘
        │                   │
┌───────▼──────┐   ┌────────▼────────────────┐
│  AI LAYER    │   │      DATA LAYER         │
│  Grok API    │   │  PostgreSQL (SQLAlchemy) │
│  HuggingFace │   │  Qdrant (vectors)       │
│  Embedder    │   └─────────────────────────┘
└──────────────┘
```

### Request Lifecycle — `/chat`

```
1. JWT validated → user_id extracted
2. PersonalityProfile loaded from PostgreSQL
3. User message embedded (HuggingFace all-MiniLM-L6-v2)
4. Top-5 relevant memories retrieved from Qdrant (cosine ≥ 0.72)
5. Multi-block system prompt assembled (Identity + Memory + Rules)
6. Prompt sent to Grok API → response collected
7. Exchange stored in PostgreSQL (chats table)
8. Memory vector upserted to Qdrant (background task)
9. Personality auto-learn triggered if N % 10 == 0 (background task)
10. Response returned to client
```

---

## Quick Start (Docker)

```bash
# 1. Clone and configure
git clone <repo-url>
cd ai_digital_twin
cp .env.example .env
# Edit .env — set SECRET_KEY and GROK_API_KEY at minimum

# 2. Start all services
docker compose up --build

# 3. Run DB migrations
docker compose exec api alembic upgrade head

# 4. Verify health
curl http://localhost:8000/health
# → {"status":"ok","version":"1.0.0","env":"development"}

# 5. Open API docs (development only)
open http://localhost:8000/docs
```

---

## Manual Setup (No Docker)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Qdrant (local or Qdrant Cloud free tier)
- Redis (optional, for Celery workers)

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in: SECRET_KEY, DATABASE_URL, SYNC_DATABASE_URL, QDRANT_HOST, GROK_API_KEY

# Run migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# (Optional) Start Celery worker
celery -A app.workers.personality_updater worker --loglevel=info
```

---

## API Reference

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user, returns token pair |
| POST | `/api/v1/auth/login` | Login, returns token pair |
| POST | `/api/v1/auth/refresh` | Refresh access token |

### Chat (🔒 JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send message to your digital twin |
| GET | `/api/v1/chat/history` | Get recent chat history |

**POST /api/v1/chat — Request:**
```json
{
  "message": "Should I take the job offer?",
  "session_id": "optional-uuid-to-continue-a-session"
}
```

**Response:**
```json
{
  "response": "Honestly, given how much I value growth over stability right now...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "memories_used": 3,
  "tokens_used": 312
}
```

### Personality (🔒 JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/personality` | Get personality profile |
| POST | `/api/v1/personality` | Create/overwrite profile |
| PATCH | `/api/v1/personality` | Partial update |

**Example personality profile:**
```json
{
  "tone": "casual",
  "communication_style": "direct and concise",
  "values": ["honesty", "efficiency", "growth"],
  "interests": ["technology", "philosophy", "fitness"],
  "decision_style": "analytical",
  "openness": 0.85,
  "conscientiousness": 0.75,
  "extraversion": 0.40,
  "agreeableness": 0.60,
  "neuroticism": 0.30,
  "persona_summary": "A pragmatic technologist who values clear thinking and direct communication."
}
```

### Memory (🔒 JWT required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/memory` | List all stored memories |
| DELETE | `/api/v1/memory/{point_id}` | Delete a specific memory |
| DELETE | `/api/v1/memory` | Delete ALL memories |

---

## Free Deployment (Zero Cost)

| Service | Platform | Free Tier |
|---------|----------|-----------|
| FastAPI API | [Railway](https://railway.app) or [Render](https://render.com) | 512MB RAM |
| PostgreSQL | [Supabase](https://supabase.com) | 500MB |
| Qdrant | [Qdrant Cloud](https://cloud.qdrant.io) | 1GB cluster |
| Redis | [Upstash](https://upstash.com) | 10K commands/day |

### Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway add --plugin postgresql
railway up

# Set environment variables
railway variables set SECRET_KEY="your-32-char-secret"
railway variables set GROK_API_KEY="your-grok-key"
railway variables set QDRANT_HOST="your-qdrant-cloud-host"
railway variables set QDRANT_API_KEY="your-qdrant-api-key"
```

---

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=app --cov-report=html

# Load testing (requires running server)
locust -f locustfile.py --host=http://localhost:8000
# Open http://localhost:8089 → set 100 users, spawn rate 10
```

---

## Auto Personality Learning

Every 10 conversations, the system:

1. Fetches the 30 most recent chat messages
2. Sends them to Grok with the personality extraction prompt
3. Merges extracted traits with the existing profile using weighted averaging:
   - **New profiles** (confidence < 0.3): LLM result weight = 0.7 (learns fast)
   - **Established profiles** (confidence ≥ 0.3): LLM result weight = 0.3 (learns conservatively)
4. Increments `trait_confidence` by 0.05 (asymptotically approaches 1.0)

---

## Memory Scoring Formula

```
composite_score = cosine_similarity × 0.6
                + recency_weight × 0.25
                + importance_score × 0.15

recency_weight = 1 / (1 + log(days_since_created + 1))
```

High-importance memories (≥ 0.8) are scored by the LLM at storage time and decay more slowly.

---

## Security

- All passwords hashed with **bcrypt** (via passlib)
- JWT access tokens expire in **30 minutes**; refresh tokens in **7 days**
- Per-user data isolation in Qdrant via payload filtering on `user_id`
- No cross-user memory leakage: every Qdrant query includes a `must` filter
- Secrets loaded exclusively from environment variables (never committed)

---

## Project Structure

```
ai_digital_twin/
├── app/
│   ├── main.py                  # App factory + lifespan
│   ├── config.py                # Pydantic Settings
│   ├── dependencies.py          # DI providers
│   ├── api/v1/                  # HTTP routes
│   ├── services/                # Business logic
│   ├── models/                  # SQLAlchemy ORM
│   ├── schemas/                 # Pydantic I/O schemas
│   ├── repositories/            # DB + vector store access
│   ├── core/                    # DB engine, Qdrant, embedder, security
│   └── workers/                 # Celery background tasks
├── alembic/                     # DB migrations
├── tests/unit/                  # Unit tests (no I/O)
├── tests/integration/           # API-level tests
├── locustfile.py                # Load testing
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
