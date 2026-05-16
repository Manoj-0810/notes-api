<div align="center">

# 📝 Notes API

### Production-Grade Multi-User Notes Backend

*A backend system inspired by Google Keep & Notion — built with enterprise engineering standards*

[![Live API](https://img.shields.io/badge/API-Live%20on%20Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://notes-api-uqs5.onrender.com)
[![Swagger Docs](https://img.shields.io/badge/Swagger-Interactive%20Docs-85EA2D?style=for-the-badge&logo=swagger&logoColor=black)](https://notes-api-uqs5.onrender.com/docs)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

**[🚀 Live Demo](https://notes-api-uqs5.onrender.com/docs)** • **[📖 API Reference](#-api-reference)** • **[🐳 Quick Start](#-quick-start)** • **[🏗️ Architecture](#️-architecture)**

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Live Deployment](#-live-deployment)
- [Features](#-features)
- [Architecture](#️-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
- [Security Design](#-security-design)
- [Database Schema](#-database-schema)
- [Testing](#-testing)
- [Deployment Guide](#-deployment-guide)
- [Engineering Decisions](#-engineering-decisions)

---

## 🧭 Overview

A **production-ready REST API** powering a collaborative notes platform — think backend for Google Keep, with version history like Google Docs, and sharing like Notion.

Built to demonstrate real-world backend engineering: not just working code, but the kind of system that handles thousands of users, never leaks passwords, recovers gracefully from errors, and ships with a one-command deployment pipeline.

### What makes this production-grade?

| Concern | Implementation |
|---|---|
| **Security** | bcrypt hashing · JWT auth · rate limiting · SQL injection prevention · no secrets in code |
| **Reliability** | Global error handler · input validation · cascade-safe DB schema · async throughout |
| **Scalability** | Stateless JWT (no sessions) · paginated endpoints · connection pooling · Docker-ready |
| **Maintainability** | Clean 3-layer architecture · schema/model separation · 3 test files · Alembic migrations |
| **Observability** | Structured logging · Swagger/OpenAPI docs · health check endpoint |

---

## 🌐 Live Deployment

| Resource | URL |
|---|---|
| **Base API** | `https://notes-api-uqs5.onrender.com` |
| **Swagger UI** | `https://notes-api-uqs5.onrender.com/docs` |
| **OpenAPI JSON** | `https://notes-api-uqs5.onrender.com/openapi.json` |
| **Health Check** | `https://notes-api-uqs5.onrender.com/about` |

> **Note:** Deployed on Render's free tier — first request after inactivity may take ~30s to cold-start.

---

## ✨ Features

### Core
- 🔐 **JWT Authentication** — stateless Bearer token auth with 30-min expiry
- 📝 **Full Note CRUD** — create, read, update, delete with ownership validation
- 👥 **Note Sharing** — share notes with any registered user by email (read-only access)
- 🔍 **Full-Text Search** — search across note titles and content
- 🏷️ **Tagging System** — user-scoped tags with filtered listing
- 📄 **Pagination** — `page` + `limit` with `total` and `pages` metadata

### Advanced
- 🕒 **Automatic Version History** — every `PUT` snapshots the previous state before overwriting
- ↩️ **Version Restore** — roll back any note to any historical version
- ⚡ **Rate Limiting** — per-IP limits on auth and notes endpoints (slowapi)
- 🌐 **CORS** — configurable allowed origins for frontend integration
- 📖 **Auto-generated Docs** — Swagger UI and ReDoc available in non-production mode

---

## 🏗️ Architecture

### System Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Client / Frontend                     │
└────────────────────────┬────────────────────────────────┘
                         │  HTTP + JSON
┌────────────────────────▼────────────────────────────────┐
│                   Uvicorn (ASGI Server)                  │
├─────────────────────────────────────────────────────────┤
│                FastAPI Application Layer                 │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────────┐  │
│  │ CORS Middle  │  │ Rate Limit │  │ Global Exception│  │
│  │    -ware     │  │ Middleware  │  │    Handler      │  │
│  └──────────────┘  └────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     Router Layer                         │
│           /auth routes │ /notes routes                   │
├─────────────────────────────────────────────────────────┤
│                  Dependency Layer                        │
│        get_current_user() │ get_db() │ rate_limit()      │
├─────────────────────────────────────────────────────────┤
│                  Business Logic Layer                    │
│    auth.py │ ownership checks │ version snapshotting     │
├─────────────────────────────────────────────────────────┤
│                 SQLAlchemy ORM Layer                     │
│         Async engine │ Session factory │ Models          │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────▼──────┐                 ┌────────▼───────┐
│   SQLite     │                 │   PostgreSQL    │
│ (dev/tests)  │                 │  (production)   │
└──────────────┘                 └─────────────────┘
```

### Request Lifecycle

```
Incoming Request
      │
      ▼
CORS middleware ──── origin blocked? ──→ 403
      │
      ▼
Rate limiter ──── limit exceeded? ──→ 429
      │
      ▼
Route matched
      │
      ▼
Dependencies resolved:
  ├── get_db()          → open async DB session
  └── get_current_user()
        ├── read Authorization header
        ├── decode + verify JWT
        └── fetch User from DB
              │
              ├── invalid/expired? ──→ 401
              └── valid → User object injected
                    │
                    ▼
              Route handler executes
                    │
              Pydantic serializes response
                    │
                    ▼
              HTTP response sent
                    │
              DB session closed (finally block)
```

---

## 🛠 Tech Stack

| Layer | Technology | Why This Choice |
|---|---|---|
| **Language** | Python 3.11 | Fastest CPython release, dominant in backend/fintech |
| **Framework** | FastAPI 0.109 | Native async, auto-docs, Pydantic-native, top performance |
| **Server** | Uvicorn + uvloop | ASGI, near Node.js throughput, async-first |
| **ORM** | SQLAlchemy 2.x (async) | Industry standard, prevents SQL injection, DB-agnostic |
| **Migrations** | Alembic | Version control for DB schema, safe production upgrades |
| **Validation** | Pydantic v2 | Compile-time schema enforcement, automatic error responses |
| **Auth** | python-jose (JWT) | Stateless, scalable, industry-standard HS256 tokens |
| **Passwords** | passlib + bcrypt | One-way hashing, constant-time comparison, brute-force resistant |
| **Rate Limiting** | slowapi | Per-IP limits, 429 responses, minimal overhead |
| **Dev DB** | SQLite + aiosqlite | Zero-config async local database |
| **Prod DB** | PostgreSQL 15 | Battle-tested, concurrent-safe, cloud-native |
| **Testing** | pytest + httpx | ASGI transport — tests without a live server |
| **Containers** | Docker + Compose | Reproducible builds, isolated environments |
| **Deployment** | Render.com | Auto-deploy on push, managed PostgreSQL, free HTTPS |

---

## 📂 Project Structure

```
notes-api/
│
├── app/                         # Application source
│   ├── __init__.py
│   ├── main.py                  # App factory — middleware, routers, lifespan
│   ├── config.py                # Pydantic Settings — all env vars, validated on startup
│   ├── database.py              # Async engine, session factory, get_db() dependency
│   ├── models.py                # SQLAlchemy ORM models (6 tables)
│   ├── schemas.py               # Pydantic request/response contracts
│   ├── auth.py                  # bcrypt hashing · JWT create/decode · get_current_user()
│   └── routers/
│       ├── __init__.py
│       ├── auth.py              # POST /register · POST /login
│       └── notes.py             # All /notes/* endpoints · /tags · /search · /about
│
├── alembic/                     # Database migrations
│   ├── env.py                   # Migration environment — async engine config
│   ├── script.py.mako           # Migration file template
│   └── versions/
│       └── 001_initial.py       # Creates all 6 tables with indexes and constraints
│
├── tests/                       # Automated test suite
│   ├── conftest.py              # Fixtures: in-memory DB · ASGI client · user/note factories
│   ├── test_auth.py             # Registration · login · token validation · edge cases
│   ├── test_notes.py            # CRUD · pagination · search · tags · versioning
│   └── test_sharing.py          # Share flow · access control · permission enforcement
│
├── Dockerfile                   # Multi-stage build (builder + slim runtime)
├── docker-compose.yml           # API + PostgreSQL orchestration for local dev
├── render.yaml                  # Render Blueprint — auto-provisions service + DB
├── alembic.ini                  # Alembic CLI configuration
├── pytest.ini                   # pytest settings (asyncio mode, test paths)
├── requirements.txt             # Production dependencies (pinned versions)
├── requirements-dev.txt         # Dev-only (pytest, httpx, coverage)
└── .env.example                 # Template — copy to .env, never commit .env
```

---

## 🚀 Quick Start

### Option 1 — Docker Compose *(Recommended — one command)*

```bash
# Clone the repository
git clone <your-repo-url>
cd notes-api

# Copy environment template
cp .env.example .env

# Start API + PostgreSQL (builds automatically)
docker-compose up --build
```

```
✅ API →  http://localhost:8000
✅ Docs → http://localhost:8000/docs
```

Stop everything: `docker-compose down`  
Stop and wipe database: `docker-compose down -v`

---

### Option 2 — Local Python *(No Docker required)*

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — for SQLite (zero setup):
# DATABASE_URL=sqlite+aiosqlite:///./notes.db
# SECRET_KEY=any-string-at-least-16-chars

# 4. Run database migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload
```

```
✅ API →  http://localhost:8000
✅ Docs → http://localhost:8000/docs  (only in development mode)
```

---

## ⚙️ Environment Variables

All configuration is environment-driven — no secrets in code.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | JWT signing key. Min 16 chars. Generate: `openssl rand -hex 32` |
| `DATABASE_URL` | **Yes** | — | Full database connection string (see examples below) |
| `ENVIRONMENT` | No | `development` | `development` · `staging` · `production` |
| `ALLOWED_ORIGINS` | No | `*` | CORS origins — comma-separated list or `*` |
| `AUTH_RATE_LIMIT` | No | `100` | Max requests/min per IP on auth endpoints |
| `NOTES_RATE_LIMIT` | No | `1000` | Max requests/min per IP on notes endpoints |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | JWT lifetime in minutes |

### Database URL Formats

```bash
# SQLite — local development (no setup required)
DATABASE_URL=sqlite+aiosqlite:///./notes.db

# PostgreSQL — local or cloud
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/notesdb

# PostgreSQL — Docker Compose (uses service hostname)
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/notesapp
```

> **Security:** `.env` is gitignored. Never commit secrets. Render auto-generates `SECRET_KEY` and `DATABASE_URL` from `render.yaml`.

---

## 📡 API Reference

Base URL: `https://notes-api-uqs5.onrender.com`

> 💡 Try every endpoint interactively at [`/docs`](https://notes-api-uqs5.onrender.com/docs)

---

### 🔐 Authentication

#### Register
```http
POST /register
Content-Type: application/json
```
```json
{ "email": "user@example.com", "password": "mypassword123" }
```
| Response | Condition |
|---|---|
| `201 Created` | Registration successful |
| `409 Conflict` | Email already registered |
| `422 Unprocessable Entity` | Invalid email or password < 8 chars |

---

#### Login
```http
POST /login
Content-Type: application/json
```
```json
{ "email": "user@example.com", "password": "mypassword123" }
```
```json
{ "access_token": "eyJhbGciOiJIUzI1NiJ9...", "token_type": "bearer" }
```
| Response | Condition |
|---|---|
| `200 OK` | Returns JWT access token |
| `401 Unauthorized` | Invalid credentials |

---

### 📝 Notes

> All notes endpoints require: `Authorization: Bearer <token>`

#### List Notes
```http
GET /notes?page=1&limit=20&tag=work&q=keyword
```
```json
{
  "notes": [{ "id": "...", "title": "...", "content": "...", "created_at": "...", "updated_at": "..." }],
  "total": 47,
  "page": 1,
  "pages": 3
}
```

| Query Param | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `limit` | integer | Results per page (default: 20, max: 100) |
| `tag` | string | Filter by tag name |
| `q` | string | Full-text search in title + content |

---

#### Create Note
```http
POST /notes
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{ "title": "Meeting Notes", "content": "Discussed Q3 roadmap...", "tags": ["work", "q3"] }
```
Returns `201 Created` with the full note object.

---

#### Get Note
```http
GET /notes/{note_id}
Authorization: Bearer <token>
```
Returns the note if you are the owner or a sharee. Returns `403` otherwise.

---

#### Update Note
```http
PUT /notes/{note_id}
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{ "title": "Updated Title", "content": "New content", "tags": ["updated"] }
```
> **Automatic versioning:** the current state is snapshotted to `note_versions` before overwriting.

All fields are optional — send only what you want to change.

---

#### Delete Note
```http
DELETE /notes/{note_id}
Authorization: Bearer <token>
```
Returns `204 No Content`. Cascades to all versions, shares, and tag links.

---

#### Share Note
```http
POST /notes/{note_id}/share
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{ "share_with_email": "colleague@example.com" }
```
| Response | Condition |
|---|---|
| `200 OK` | Note shared successfully |
| `400 Bad Request` | Cannot share with yourself |
| `404 Not Found` | Recipient has no account |
| `409 Conflict` | Already shared with this user |

---

### 🕒 Version History

```http
# List all versions (newest first)
GET /notes/{note_id}/versions

# Get a specific version snapshot
GET /notes/{note_id}/versions/{version_num}

# Restore note to a previous version
POST /notes/{note_id}/restore/{version_num}
```

> **Restore is non-destructive:** the current state is saved as a new version before rolling back.

---

### 🏷️ Tags

```http
# List all your tags
GET /tags

# Delete a tag (unlinks from notes, doesn't delete notes)
DELETE /tags/{tag_name}
```

---

### 🔍 Search

```http
GET /search?q=keyword
Authorization: Bearer <token>
```
Searches across all note titles and content visible to you (owned + shared).

---

### 💓 Health Check

```http
GET /about
```
No authentication required. Returns API metadata. Used by Render for health monitoring.

---

## 🔒 Security Design

Security is applied in 8 independent layers:

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1 │ bcrypt password hashing (cost 12, ~250ms/hash) │
│ Layer 2 │ JWT Bearer tokens (HS256, 30-min expiry)       │
│ Layer 3 │ Ownership checks (owner vs sharee vs stranger) │
│ Layer 4 │ Information hiding (403 not 404 for auth fail) │
│ Layer 5 │ Rate limiting (100/min auth, 1000/min notes)   │
│ Layer 6 │ Pydantic input validation (every request body) │
│ Layer 7 │ Global exception handler (no stack trace leaks)│
│ Layer 8 │ Parameterized queries (SQL injection proof)    │
└─────────────────────────────────────────────────────────┘
```

**Password flow:**
```
Registration:  "password123"  →  bcrypt(12 rounds)  →  "$2b$12$..." stored in DB
Login:         "password123"  →  bcrypt.verify()   →  constant-time compare → ✓/✗
```

**JWT flow:**
```
Login success → jwt.encode({sub: user_id, exp: now+30min}, SECRET_KEY) → token
Request      → jwt.decode(token, SECRET_KEY) → verify sig + exp → extract user_id
```

**Why 403 instead of 404 for unauthorized access:**  
If the API returned 404 for notes the user can't see, an attacker could enumerate valid note IDs by comparing 403 vs 404 responses. Always 403 prevents this.

---

## 🗄️ Database Schema

```
┌─────────────────┐       ┌──────────────────┐
│     users       │       │      notes        │
├─────────────────┤       ├──────────────────┤
│ id (UUID PK)    │──┐    │ id (UUID PK)     │
│ email (UNIQUE)  │  └───▶│ owner_id (FK)    │
│ password_hash   │       │ title            │
│ created_at      │       │ content (TEXT)   │
│ is_active       │       │ created_at       │
└─────────────────┘       │ updated_at       │
                          └────────┬─────────┘
                                   │
              ┌────────────────────┼───────────────────┐
              │                    │                   │
    ┌─────────▼──────┐  ┌──────────▼──────┐  ┌────────▼──────┐
    │  note_versions  │  │   note_shares   │  │   note_tags   │
    ├─────────────────┤  ├─────────────────┤  ├───────────────┤
    │ id (UUID PK)    │  │ id (UUID PK)    │  │ note_id (FK)  │
    │ note_id (FK)    │  │ note_id (FK)    │  │ tag_id (FK)   │
    │ title           │  │ shared_with(FK) │  └───────────────┘
    │ content         │  │ shared_by (FK)  │         │
    │ version_num     │  │ shared_at       │  ┌──────▼────────┐
    │ created_at      │  └─────────────────┘  │     tags      │
    └─────────────────┘                       ├───────────────┤
                                              │ id (UUID PK)  │
                                              │ name          │
                                              │ user_id (FK)  │
                                              └───────────────┘
```

**Key design decisions:**

- **UUID primary keys** — prevents ID enumeration attacks (vs sequential integers)
- **Cascade deletes** — deleting a user removes all their notes, versions, shares, and tags
- **Unique constraints** — `(note_id, shared_with)` prevents duplicate shares; `(name, user_id)` prevents duplicate tags per user
- **Tags are user-scoped** — two users can both have a "work" tag independently
- **Versions are append-only** — they're never modified after creation (audit trail)

---

## 🧪 Testing

### Run Tests

```bash
# All tests, verbose output
pytest -v

# Specific test file
pytest tests/test_auth.py -v
pytest tests/test_notes.py -v
pytest tests/test_sharing.py -v

# With coverage report
pytest --cov=app --cov-report=term-missing
```

### Test Architecture

Tests use an **in-memory SQLite database** — isolated, fast, no external dependencies.

```
conftest.py provides:
  ├── test_engine       — sqlite+aiosqlite:///:memory:
  ├── db_session        — fresh DB per test, wiped after
  ├── client            — httpx AsyncClient with ASGI transport
  ├── create_test_user  — factory: inserts User directly into DB
  ├── create_test_note  — factory: inserts Note directly into DB
  └── get_auth_headers  — generates valid JWT for any user
```

### Coverage by File

| Test File | Scenarios Covered |
|---|---|
| `test_auth.py` | Register (success, duplicate, invalid email, short password) · Login (success, wrong password, unknown user) · Protected endpoints (no token, bad token, expired token) |
| `test_notes.py` | CRUD operations · Pagination edge cases · Tag filtering · Full-text search · Version auto-creation on update · Version restore · Cross-user access rejection |
| `test_sharing.py` | Share with valid user · Shared user reads note · Shared user cannot edit/delete · Share with self → 400 · Share unknown email → 404 · Double-share → 409 |

### Test Pattern (Arrange → Act → Assert)

```python
async def test_update_creates_version(client, db_session):
    # Arrange — create user and note
    user = await create_test_user(db_session)
    note = await create_test_note(db_session, owner_id=user.id, title="Original")
    headers = get_auth_headers(user.id)

    # Act — update the note
    response = await client.put(
        f"/notes/{note.id}",
        json={"title": "Updated Title"},
        headers=headers
    )

    # Assert — version was captured before update
    assert response.status_code == 200
    versions = await client.get(f"/notes/{note.id}/versions", headers=headers)
    assert versions.json()[0]["title"] == "Original"  # pre-update state preserved
```

---

## ☁️ Deployment Guide

### Deploy to Render.com *(Production — Free Tier)*

**Step 1 — Push to GitHub**
```bash
git init
git add .
git commit -m "feat: initial production-ready notes API"
git remote add origin https://github.com/YOUR_USERNAME/notes-api.git
git push -u origin main
```

**Step 2 — Deploy via Blueprint**

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Blueprint**
2. Connect GitHub → select your repository
3. Render detects `render.yaml` automatically
4. Click **Apply** — Render provisions:
   - Python web service (auto-deploys on every `git push`)
   - PostgreSQL 15 database (managed, backed up)
   - Auto-generated `SECRET_KEY` (cryptographically secure)
   - Auto-injected `DATABASE_URL` from the managed DB
   - Free HTTPS / SSL certificate

**Step 3 — Verify**
```bash
curl https://notes-api-<your-name>.onrender.com/about
```

---

### Docker Build Details

The `Dockerfile` uses a **multi-stage build** to minimize the production image:

```dockerfile
# Stage 1: Builder — compiles packages (includes GCC, ~600MB)
FROM python:3.11-slim AS builder
RUN pip install --user -r requirements.txt

# Stage 2: Runtime — lean production image (~180MB)
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local   # only compiled packages
COPY . .
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Result: significantly smaller final image, faster deployment, smaller attack surface.

---

## 🧠 Engineering Decisions

### Why FastAPI over Django/Flask?

| Framework | Verdict |
|---|---|
| **Django** | Includes ORM, admin, templates — heavyweight for a pure API. Slower auto-docs. |
| **Flask** | Minimalist but requires manually wiring validation, async, docs, auth. |
| **FastAPI** ✓ | Native async, Pydantic-first validation, auto Swagger docs, Python's best performance/ergonomics ratio. |

### Why JWT over session-based auth?

Sessions store state on the server — every API server needs access to the same session store (usually Redis). JWTs are **self-contained**: any server can verify any token using only the `SECRET_KEY`. This makes horizontal scaling trivial.

### Why UUIDs over sequential integer IDs?

Integer IDs (`/notes/1`, `/notes/2`) let attackers enumerate all records. UUIDs (`/notes/f47ac10b-58cc-...`) are 128-bit random values — impossible to enumerate or guess.

### Why version snapshots instead of diffs?

Diffs (storing only what changed) are space-efficient but complex to reconstruct ("apply patch 1 then 2 then 3..."). Full snapshots (storing the complete state each time) are simpler to implement, query, and restore — and for note-sized payloads, the storage cost is negligible.

### Why SQLite for dev and PostgreSQL for production?

SQLite is zero-config for local development and test runs. PostgreSQL handles concurrent writes, large datasets, and advanced indexing at production scale. SQLAlchemy's dialect abstraction means the same Python code works against both — only the `DATABASE_URL` changes.

---

## 🔮 Future Enhancements

- [ ] **Redis caching** — cache frequently-read notes, reduce DB load
- [ ] **WebSocket support** — real-time collaborative editing
- [ ] **Refresh token rotation** — extend sessions without re-login
- [ ] **Role-based permissions** — owner/editor/viewer access levels on shared notes
- [ ] **CI/CD pipeline** — GitHub Actions: test → lint → deploy on merge to main
- [ ] **Observability** — structured JSON logging, Prometheus metrics, Sentry error tracking
- [ ] **Kubernetes deployment** — Helm chart for auto-scaling production
- [ ] **Full PostgreSQL text search** — `tsvector` indexes for sub-millisecond search at scale
- [ ] **Soft deletes** — mark notes as deleted rather than permanently removing

---

## 📋 Production Challenges Solved

During development and cloud deployment, the following real-world issues were identified and resolved:

- bcrypt hashing edge cases under async context
- JWT validation with missing/malformed Authorization headers
- SQLite → PostgreSQL compatibility in SQLAlchemy async mode
- Render cold-start timing with Alembic migrations running at boot
- Docker multi-stage dependency isolation
- CORS preflight handling for browser-based clients
- Race conditions on concurrent user registration (IntegrityError handling)
- Uvicorn `--reload` behaviour with `lifespan` context managers

---

## 📜 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with precision · Deployed on Render · Documented for humans

*If you found this useful, consider giving it a ⭐*

</div>
