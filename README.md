# Notes API

A production-grade, multi-user Notes REST API built with FastAPI. Think backend for Google Keep — with note versioning, tagging, sharing, full-text search, and pagination.

## Features

### Core
- **User registration & login** with bcrypt password hashing and JWT authentication
- **Note CRUD** — create, read, update, delete notes with proper ownership
- **Note sharing** — share notes with other users by email (read-only for sharees)
- **Auto-generated OpenAPI docs** at `/openapi.json`

### Custom Features (Assignment Requirements)
- **Note Version History** — every PUT automatically snapshots the previous state. View history and restore any past version.
- **Note Tagging System** — user-scoped tags with filterable note lists

### Stretch Goals
- **Pagination** on list endpoints with `total`, `page`, `pages` metadata
- **Full-text search** across titles and content
- **Docker & docker-compose** with PostgreSQL
- **Rate limiting** per endpoint category

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Database | SQLite (dev), PostgreSQL (production) |
| Auth | python-jose + passlib[bcrypt] |
| Validation | Pydantic v2 |
| Rate Limiting | slowapi |
| Testing | pytest + httpx |
| Deployment | Render.com |

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)

### Option 1: Docker Compose (Recommended)

```bash
# Clone and start everything (PostgreSQL + API)
git clone <repo-url>
cd notes-api
cp .env.example .env
docker-compose up --build

# API available at http://localhost:8000
# Auto-generated docs at http://localhost:8000/docs
```

### Option 2: Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Set environment variables
cp .env.example .env
# Edit .env with your settings

# 4. Run migrations (creates tables)
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | JWT signing key (32+ random bytes) |
| `DATABASE_URL` | Yes | — | Database connection string |
| `ENVIRONMENT` | No | `development` | `development` / `staging` / `production` |
| `ALLOWED_ORIGINS` | No | `*` | CORS origins (comma-separated) |
| `AUTH_RATE_LIMIT` | No | 100 | Requests/minute for auth endpoints |
| `NOTES_RATE_LIMIT` | No | 1000 | Requests/minute for notes endpoints |

### Database URLs

```bash
# SQLite (development)
DATABASE_URL=sqlite+aiosqlite:///./notes.db

# PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# PostgreSQL via docker-compose
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/notesapp
```

## API Reference

### Authentication

#### Register
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
# 201 {"message": "User registered successfully"}
```

#### Login
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
# 200 {"access_token": "eyJ...", "token_type": "bearer"}
```

### Notes

All note endpoints require a Bearer token in the `Authorization` header.

#### List Notes (with pagination, tag filter, search)
```bash
# Basic list
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/notes

# Pagination
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/notes?page=1&limit=10"

# Filter by tag
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/notes?tag=work"

# Search
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/notes?q=keyword"
```

#### Create Note
```bash
curl -X POST http://localhost:8000/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Note", "content": "Hello world", "tags": ["work", "idea"]}'
```

#### Get Note
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/notes/{note_id}
```

#### Update Note
```bash
curl -X PUT http://localhost:8000/notes/{note_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title"}'
```

#### Delete Note
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/notes/{note_id}
# 204 No Content
```

#### Share Note
```bash
curl -X POST http://localhost:8000/notes/{note_id}/share \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"share_with_email": "friend@example.com"}'
```

### Version History

```bash
# List versions
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/notes/{note_id}/versions

# Get specific version
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/notes/{note_id}/versions/1

# Restore to version
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/notes/{note_id}/restore/1
```

### Tags

```bash
# List your tags
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/tags

# Delete a tag
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/tags/{tag_name}
```

### Search

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/search?q=keyword"
```

### About

```bash
curl http://localhost:8000/about
```

### OpenAPI Schema

```bash
curl http://localhost:8000/openapi.json
```

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

## Deployment Guide (Render.com)

### 1. Create Account
Sign up at [render.com](https://render.com) with GitHub.

### 2. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 3. Create Web Service
- Click "New +" → "Web Service"
- Connect your GitHub repository
- **Name**: `notes-api`
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt && alembic upgrade head`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 4. Create PostgreSQL Database
- Click "New +" → "PostgreSQL"
- **Name**: `notes-db`
- The `render.yaml` blueprint already configures auto-linking

### 5. Environment Variables
Render will auto-generate `SECRET_KEY` and `DATABASE_URL` from the blueprint.

### 6. Deploy
Click "Deploy". The API will be live at `https://notes-api-<your-name>.onrender.com`.

Verify with:
```bash
curl https://notes-api-<your-name>.onrender.com/about
```

## Project Structure

```
notes-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # App factory, middleware, routers
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── database.py          # Engine, SessionLocal, Base, get_db
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── auth.py              # JWT logic, password hashing
│   └── routers/
│       ├── __init__.py
│       ├── auth.py          # /register, /login
│       └── notes.py         # All /notes endpoints + /about
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py
├── tests/
│   ├── conftest.py          # pytest fixtures
│   ├── test_auth.py
│   ├── test_notes.py
│   └── test_sharing.py
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── README.md
```

## Security

- **Passwords**: Hashed with bcrypt (cost factor 12, ~250ms/hash)
- **JWT**: HS256 algorithm, 30-minute expiration
- **CORS**: Configurable via ALLOWED_ORIGINS
- **Rate limiting**: Per-IP limits on auth and notes endpoints
- **No secrets in code**: All configuration via environment variables
- **SQL Injection**: Prevented via SQLAlchemy ORM (parameterized queries)

## License

MIT
