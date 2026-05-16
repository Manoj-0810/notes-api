# Interview Preparation — Notes API

This document prepares you for the deep technical interview that follows the automated test evaluation. Every decision in the codebase is defensible. Know this document cold.

---

## Section A: Architecture Decisions (Q&A Format)

### Why FastAPI over Flask or Django?

**Q**: Why did you choose FastAPI for this assignment?
**A**: Three reasons. First, FastAPI auto-generates the `/openapi.json` endpoint which was explicitly required — in Flask I'd need to manually maintain an OpenAPI spec, and Django REST Framework requires a separate plugin. Second, FastAPI's native `async` support with `async/await` handles concurrent requests efficiently without thread pools. Third, Pydantic integration gives automatic request validation with clean 422 errors, eliminating an entire class of bugs. The tradeoff is a smaller ecosystem than Django, but for a focused API project, FastAPI is the pragmatic choice.

### Why UUIDs as primary keys instead of integers?

**Q**: Why use UUIDs instead of auto-incrementing integers?
**A**: UUIDs are harder to enumerate — with integer IDs, an attacker can scrape all notes by iterating `/notes/1`, `/notes/2`, etc. UUIDs add a layer of obfuscation. They're also globally unique, which simplifies distributed systems (no sequence coordination across shards) and makes merge conflicts during data migrations impossible. The tradeoff is 16 bytes vs 4-8 bytes per key and slightly slower indexing, but for a notes app, the security benefit outweighs the cost.

### Why bcrypt for password hashing?

**Q**: Why bcrypt specifically? What about Argon2 or scrypt?
**A**: Bcrypt has been battle-tested for 25+ years with no known vulnerabilities. It automatically handles salting (no two users with the same password have the same hash) and has an adaptive cost factor that can be increased as hardware improves. I use the default work factor of 12 rounds (~250ms per hash), which is the current OWASP recommendation. Argon2 won the Password Hashing Competition and is theoretically superior for GPU resistance, but bcrypt is more widely supported, has broader library compatibility, and for this project's threat model, bcrypt is perfectly adequate.

### How does JWT authentication work in your implementation?

**Q**: Walk me through your JWT implementation. What's in the payload?
**A**: The payload contains two claims: `sub` (the user's UUID as a string) and `exp` (expiration timestamp, 30 minutes from issuance). On login, after bcrypt verification, I call `jwt.encode` with the payload, a 32+ byte secret key from environment variables, and HS256 algorithm. The client sends this token in the `Authorization: Bearer <token>` header. Each protected endpoint uses the `get_current_user` dependency which decodes the token, verifies the signature and expiration, looks up the user in the database, and injects the User object into the route handler. I don't store tokens server-side — they're stateless, which scales horizontally without a session store.

### Why SQLAlchemy ORM vs raw SQL?

**Q**: Why use an ORM instead of writing raw SQL queries?
**A**: Three reasons: security, maintainability, and portability. SQLAlchemy automatically parameterizes all queries, eliminating SQL injection risks without me having to remember to use placeholders everywhere. The ORM pattern keeps database logic organized with the models rather than scattered across string literals. And because SQLAlchemy abstracts dialect differences, the same code works with SQLite in development and PostgreSQL in production — no query rewrites needed. For complex analytics queries, I might drop to raw SQL, but for CRUD operations, ORM is the right abstraction.

### What happens if the database is down?

**Q**: How does your application behave when the database is unavailable?
**A**: Currently, the app will return 500 errors when database connections fail. In a production setup, I'd add connection pooling with `create_async_engine(pool_pre_ping=True)` to validate connections before use, implement a circuit breaker pattern that returns 503 Service Unavailable after repeated failures, and add health check endpoints that the load balancer can use to route traffic away from unhealthy instances. I'd also add database connection retry logic with exponential backoff for transient failures.

### Why PostgreSQL in production but SQLite in development?

**Q**: Why two different databases?
**A**: SQLite is zero-configuration — perfect for development and testing (I use `:memory:` for tests). But SQLite doesn't support the concurrency model needed for production: it locks the entire database on writes, has limited ALTER TABLE support, and doesn't handle multiple simultaneous connections well. PostgreSQL has proper row-level locking, advanced indexing (GIN for full-text search), connection pooling, and ACID compliance under concurrency. The SQLAlchemy abstraction means the switch is transparent to application code — only the connection string changes.

---

## Section B: Every Endpoint — Deep Dive

### POST /register
- **What it does**: Creates a new user account with a bcrypt-hashed password.
- **ORM call**: `db.add(User(email=..., password_hash=hash_password(...)))`
- **Failure modes**: 409 if email exists (duplicate unique constraint), 422 if email invalid or password < 8 chars (Pydantic validators).
- **Security**: Generic error messages to prevent user enumeration. Password never logged or returned.

### POST /login
- **What it does**: Verifies credentials and returns a JWT access token.
- **ORM call**: `SELECT * FROM users WHERE email = ?` → `pwd_context.verify()`
- **Failure modes**: 401 for wrong password or nonexistent email (same message to prevent enumeration), 422 for invalid input.
- **Security**: Constant-time password comparison via passlib. Token expires in 30 minutes.

### GET /notes
- **What it does**: Returns paginated list of notes accessible to the user (owned + shared).
- **ORM call**: Complex SELECT with WHERE owner_id=? OR note_id IN (shared_subquery), plus optional tag JOIN and ILIKE search, with LIMIT/OFFSET.
- **Failure modes**: 401 if no valid JWT. Returns empty list (not 404) if no notes.
- **Security**: Users can never see notes they don't own or that haven't been shared with them.

### GET /notes/{id}
- **What it does**: Returns a single note by ID after access verification.
- **ORM call**: `SELECT * FROM notes WHERE id = ?` followed by ownership/share check.
- **Failure modes**: 403 if user has no access (even if note exists), 404 if note doesn't exist.
- **Security**: 403 returned instead of 404 to prevent information disclosure — an attacker can't probe for note existence.

### POST /notes
- **What it does**: Creates a new note with optional tags.
- **ORM call**: `INSERT INTO notes` + tag lookups/inserts via the association table.
- **Failure modes**: 422 for invalid title/content length.
- **Security**: `owner_id` is set from the JWT subject, never from user input — prevents creating notes as other users.

### PUT /notes/{id}
- **What it does**: Updates a note and saves a version snapshot beforehand.
- **ORM call**: `INSERT INTO note_versions` (snapshot) + `UPDATE notes SET ...`
- **Failure modes**: 403 if not owner (including shared users), 404 if note not found, 422 for invalid input.
- **Security**: Only the owner can update. Version history provides an audit trail.

### DELETE /notes/{id}
- **What it does**: Deletes a note and cascades to versions, shares, and tag associations.
- **ORM call**: `DELETE FROM notes WHERE id = ?` (cascade deletes via FK constraints)
- **Failure modes**: 403 if not owner, 404 if not found. Returns 204 (no body) on success.
- **Security**: Hard delete with cascade. Only owner can delete.

### POST /notes/{id}/share
- **What it does**: Creates a NoteShare record granting read-only access to another user.
- **ORM call**: `INSERT INTO note_shares` after verifying target user exists.
- **Failure modes**: 400 if sharing with self, 403 if not the owner, 404 if target user not found.
- **Security**: Sharee gets read access only — update/delete return 403. Idempotent (re-sharing returns success).

### GET /openapi.json
- **What it does**: Auto-generated OpenAPI 3.0 schema from FastAPI route definitions.
- **Generated by**: FastAPI internals from Pydantic schemas and route decorators.
- **Failure modes**: None — served statically.
- **Security**: Public endpoint, no auth required.

### GET /about
- **What it does**: Returns developer info and feature descriptions.
- **Static response**: Hardcoded JSON with feature justifications.
- **Failure modes**: None.
- **Security**: Public endpoint.

---

## Section C: Custom Features — Justify Every Choice

### Feature 1: Note Version History

**Data model**: `note_versions` table with `note_id` (FK), `version_num` (auto-incremented per note), `title`, `content`, and `created_at`. This is an append-only audit log — versions are never modified or deleted (except via CASCADE when the parent note is deleted).

**Trigger mechanism**: Service layer. In `update_note()`, before applying changes, I call `_increment_version()` which reads the current state of the note object and inserts a new `NoteVersion` row. This is explicit and visible in the code — no ORM signals or middleware magic. The tradeoff is the developer must remember to call it, but the explicitness makes the behavior predictable and testable.

**Extending to diff views**: I'd add a `generate_diff(version_a, version_b)` utility using Python's `difflib.unified_diff()` to produce line-by-line diffs. Store a `diff` text column pre-computed, or generate on-the-fly. For large notes, I'd consider storing a hash of content to skip diffing identical versions.

**Deletion behavior**: When a note is deleted, `ON DELETE CASCADE` on the foreign key automatically removes all versions. This is correct — versions without a parent note are meaningless. If soft-delete were implemented, versions would be preserved until the note is hard-deleted.

### Feature 2: Note Tagging System

**M2M join table**: `note_tags` association table with composite primary key `(note_id, tag_id)`. Both columns have `ON DELETE CASCADE` — removing a note removes its tag associations, removing a tag removes it from all notes. The `Tag` table has a unique constraint on `(name, user_id)` ensuring tags are namespaced per user — two users can each have a "work" tag.

**Tag filtering at SQL level**: Uses a subquery approach:
```sql
SELECT * FROM notes
WHERE owner_id = ? AND id IN (
    SELECT note_id FROM note_tags
    JOIN tags ON note_tags.tag_id = tags.id
    WHERE tags.name = ? AND tags.user_id = ?
)
```
I chose subquery over JOIN to avoid duplicate rows when a note has multiple matching tags. For large datasets, I'd benchmark against a JOIN approach — PostgreSQL's query planner often optimizes both similarly.

**Frontend autocomplete**: I'd add `GET /tags?prefix=wor` that returns tags starting with the prefix, using `SELECT name FROM tags WHERE user_id = ? AND name LIKE 'wor%'` with a LIMIT of 10. This query is indexed on `(name, user_id)` and would be very fast.

---

## Section D: Edge Case Walkthrough

| Edge Case | How Caught | Exact Response | Code Location |
|-----------|-----------|----------------|---------------|
| Access other's note → 403 | `_get_note_with_access()` checks owner_id and NoteShare | `{"detail": "You don't have permission..."}` | `app/routers/notes.py:85` |
| Share with nonexistent email → 404 | Query for target user returns None | `{"detail": "User not found"}` | `app/routers/notes.py:356` |
| Share with self → 400 | Explicit email comparison before DB query | `{"detail": "Cannot share a note with yourself"}` | `app/routers/notes.py:348` |
| Share note you don't own → 403 | `_require_owner()` called before share logic | `{"detail": "Only the note owner can..."}` | `app/routers/notes.py:344` |
| Duplicate registration → 409 | Explicit SELECT before INSERT + IntegrityError handler | `{"detail": "Email already registered"}` | `app/routers/auth.py:42` |
| Wrong login credentials → 401 | Generic error for both wrong email and wrong password | `{"detail": "Invalid email or password"}` | `app/routers/auth.py:75` |
| No auth header → 401 | `HTTPBearer(auto_error=False)` + None check | `{"detail": "Could not validate credentials"}` | `app/auth.py:122` |
| Expired JWT → 401 | `jwt.decode()` with `require=["exp"]` raises `ExpiredSignatureError` | `{"detail": "Could not validate credentials"}` | `app/auth.py:101` |
| Malformed JWT → 401 | `JWTError` caught in `decode_token()` | `{"detail": "Could not validate credentials"}` | `app/auth.py:106` |
| Empty title → 422 | Pydantic `min_length=1` validator | `{"detail": [{"type": "string_too_short"...}]}` | `app/schemas.py:43` |
| Title > 500 chars → 422 | Pydantic `max_length=500` validator | `{"detail": [{"type": "string_too_long"...}]}` | `app/schemas.py:43` |
| Invalid email → 422 | Pydantic `EmailStr` validator | `{"detail": [{"type": "value_error"...}]}` | `app/schemas.py:19` |
| Short password → 422 | Pydantic `min_length=8` validator | `{"detail": [{"type": "string_too_short"...}]}` | `app/schemas.py:22` |

---

## Section E: Scaling & Production Thinking

**1 million users**: At that scale, the first bottleneck is the database connection pool. I'd implement connection pooling with SQLAlchemy's `AsyncEngine` configured for 20-50 connections, add read replicas for GET endpoints (route writes to primary, reads to replicas), and introduce Redis caching for frequently accessed notes and user sessions. The `/search` endpoint would need PostgreSQL's GIN indexes on `(title, content)` or a dedicated Elasticsearch cluster. I'd shard by user_id for horizontal scaling — all of a user's data lives on the same shard.

**Real-time collaboration**: For simultaneous editing, I'd use WebSockets with Operational Transformation (OT) or CRDTs (Conflict-free Replicated Data Types). OT is what Google Docs uses — it transforms concurrent operations so they apply correctly. CRDTs are simpler to implement and don't require a central server to resolve conflicts. I'd use the Yjs library (CRDT-based) with a WebSocket server for synchronization. Each edit is broadcast to connected clients and stored as a version.

**Search at scale**: For the current implementation, I use SQL `ILIKE '%term%'` which is O(n) table scans — fine for thousands of notes, unusable at millions. The upgrade path is PostgreSQL's built-in Full-Text Search (FTS) with GIN indexes: `to_tsvector('english', title || ' ' || content)`. For even larger scale, Elasticsearch with per-user indices provides relevance scoring, fuzzy matching, and faceted search. The migration path is: ILIKE → PostgreSQL FTS → Elasticsearch.

**Observability**: I'd add structured JSON logging with correlation IDs propagated across requests, Prometheus metrics for request count/latency/error rate by endpoint, and distributed tracing with OpenTelemetry to track requests through the async call stack. Alert on p99 latency > 500ms, error rate > 1%, and database connection pool exhaustion. Use Sentry for error tracking with full stack traces and context.

**Next 2 weeks**: If I had two more weeks, I'd build: (1) Soft delete with a trash can / restore from trash feature, (2) Real-time sync via WebSockets for instant cross-device updates, (3) Note templates for common patterns (daily standup, meeting notes), and (4) Bulk operations — select multiple notes to tag, archive, or delete at once.

---

## Section F: Security Deep Dive

**Bcrypt internals**: Bcrypt runs the password through the Blowfish cipher with a salt and cost factor. The output format is `$2b$<cost>$<salt><hash>` where cost is the log2 iteration count (12 = 4096 rounds), salt is 16 random bytes base64-encoded, and hash is 24 bytes. The salt prevents rainbow table attacks — same password, different hash every time. The cost factor makes brute force computationally expensive. Verification extracts the cost and salt from the stored hash, re-hashes the candidate password with the same parameters, and compares.

**JWT structure**: A JWT has three parts separated by dots: `header.payload.signature`. Header is base64-encoded JSON with algorithm (`{"alg":"HS256"}`) and type. Payload contains claims — I store `sub` (user UUID) and `exp` (expiration timestamp). Signature is HMAC-SHA256 of `base64(header) + "." + base64(payload)` signed with the secret key. This ensures tampering is detected — changing any claim invalidates the signature.

**HS256 vs RS256**: I chose HS256 (symmetric, one shared secret) because this is a single-service API with no third-party token verification. RS256 (asymmetric, private key signs, public key verifies) is needed when multiple services need to verify tokens but only one can sign — like microservices or third-party API consumers. RS256 has higher computational overhead but better separation of concerns.

**SQL injection prevention**: I use SQLAlchemy ORM for all queries, which automatically parameterizes inputs. No string concatenation or f-strings in queries. Even raw SQL via `text()` uses bind parameters: `text("SELECT * FROM notes WHERE id = :id").bindparams(id=note_id)`. The only way SQL injection could occur is if I deliberately used string formatting, which I never do.

**OWASP Top 10 mitigations**:

| # | Vulnerability | How Mitigated |
|---|--------------|---------------|
| 1 | Broken Access Control | `get_current_user` dependency on all protected routes; ownership checks on every note operation; 403 for unauthorized access |
| 2 | Cryptographic Failures | bcrypt password hashing; JWT with HS256 and expiration; HTTPS in production; secrets in env vars |
| 3 | Injection | SQLAlchemy ORM with parameterized queries; Pydantic input validation; no raw SQL concatenation |
| 4 | Insecure Design | UUIDs prevent ID enumeration; generic login errors prevent user enumeration; version history prevents data loss |
| 5 | Security Misconfiguration | Pydantic Settings validate config; CORS restricted in production; debug endpoints disabled in production |
| 6 | Vulnerable Components | Pinned dependency versions; no known CVEs in the dependency tree |
| 7 | Auth Failures | JWT with expiration; bcrypt password storage; rate limiting on auth endpoints |

---

## Section G: 10 Likely Interview Questions + Model Answers

### Q1: Why did you use dependency injection for the database session?
**A**: Dependency injection makes the code testable — I can override `get_db` in tests with an in-memory SQLite session. It also ensures sessions are properly scoped per-request and always closed via the `async with` context manager, preventing connection leaks.
**Why this works**: Shows understanding of clean architecture and testability.

### Q2: How would you handle a user deleting their account?
**A**: I'd implement a soft delete — set `is_active = False` and schedule hard deletion after 30 days. During this period, shared notes remain accessible to sharees (transferring ownership to the first sharee). After 30 days, CASCADE deletes remove all user data. This balances GDPR right-to-erasure with not surprising collaborators.
**Why this works**: Shows product thinking, not just technical correctness.

### Q3: Your version history keeps growing forever. How do you manage storage?
**A**: I'd add a retention policy — keep all versions for 30 days, then collapse to weekly snapshots, then monthly after a year. For a notes app, recent versions are valuable; 3-year-old versions rarely need granular restoration. This could save 80%+ of storage.
**Why this works**: Shows awareness of operational costs, not just feature completeness.

### Q4: How would you implement rate limiting in a distributed deployment?
**A**: `slowapi` uses in-memory storage which won't work across multiple server instances. I'd switch to Redis-backed rate limiting — all instances share the same counter state. The key would be `ratelimit:<endpoint>:<user_id_or_ip>` with Redis EXPIRE for automatic window cleanup.
**Why this works**: Shows understanding of distributed systems constraints.

### Q5: Why return 403 instead of 404 when a user can't access a note?
**A**: 403 says "this note exists but you can't see it" while 404 says "this note doesn't exist." Using 404 for both would leak information — an attacker could probe for note existence by checking which UUIDs return 404 vs 403. Consistent 403 prevents this information disclosure.
**Why this works**: Demonstrates security-first thinking.

### Q6: How does your application handle the thundering herd problem?
**A**: Currently it doesn't explicitly. For a popular shared note receiving many simultaneous requests, I'd add Redis caching for note content with a short TTL (60 seconds), and implement request coalescing — if multiple requests hit for the same uncached note, only one database query fires and the rest wait for the result.
**Why this works**: Shows awareness of real-world load issues.

### Q7: What's the N+1 query problem and does your code have it?
**A**: N+1 is when you fetch N records then make N additional queries for related data. I prevent it with `selectinload()` on relationships — for example, loading note tags in a single additional query rather than one per note. I'd verify with SQLAlchemy's query logging that each endpoint makes a bounded number of queries regardless of result set size.
**Why this works**: Shows awareness of ORM performance pitfalls.

### Q8: How would you add soft delete to notes?
**A**: Add a `deleted_at` nullable timestamp. Filter it out in the base query: `WHERE deleted_at IS NULL`. The DELETE endpoint would set `deleted_at = now()` instead of removing the row. Add a `GET /notes/trash` endpoint and a `POST /notes/{id}/restore` endpoint. Version history and shares are preserved. A periodic job hard-deletes notes deleted > 30 days ago.
**Why this works**: Concrete implementation plan, not vague hand-waving.

### Q9: Why did you choose async SQLAlchemy over the sync version?
**A**: FastAPI is async-native. Using sync SQLAlchemy would block the event loop during database queries, defeating the purpose of async. With `AsyncSession`, while one request waits for the database, the event loop handles other requests. This is critical for I/O-bound APIs with many concurrent clients.
**Why this works**: Correctly identifies the architectural alignment.

### Q10: How would you migrate from SQLite to PostgreSQL without downtime?
**A**: Three-phase approach: (1) Set up PostgreSQL replica with dual-write logic — every write goes to both databases. (2) Run a backfill job to migrate historical data. (3) Once verified, switch reads to PostgreSQL and remove SQLite writes. For a small app, a simpler approach: maintenance window with `pg_dump` equivalent data export, or use an ETL tool like `sqlite3-to-postgres`.
**Why this works**: Shows operational maturity — knows migrations are risky and plans carefully.
