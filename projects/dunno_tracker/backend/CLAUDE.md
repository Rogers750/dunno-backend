# Backend — FastAPI + Supabase

## Entry Point
`app/main.py` — mounts all routers, CORS middleware, and the `/setup` bootstrap endpoint.

## File Structure
```
app/
├── main.py          # App entry, /health, /setup
├── config.py        # Pydantic settings (reads .env)
├── database.py      # Supabase client singleton (get_db())
├── auth.py          # API key validation, key generation
├── models/          # Pydantic request/response schemas
│   ├── agent.py
│   ├── event.py
│   ├── person.py
│   └── fingerprint.py
└── routers/         # One file per resource
    ├── agents.py
    ├── events.py
    ├── people.py
    ├── fingerprints.py
    ├── sessions.py
    └── dashboard.py
```

## API Endpoints

### Public (no auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/setup` | One-time bootstrap — creates project + first API key. Disabled after first use. |

### Authenticated (X-API-Key header required)
| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/v1/agents` | Create or upsert agent |
| GET | `/api/v1/agents` | List all agents |
| GET | `/api/v1/agents/{name}` | Get agent by name |
| PUT | `/api/v1/agents/{name}/agent-versions` | Create agent version |
| GET | `/api/v1/agents/{name}/agent-versions` | List agent versions |
| GET | `/api/v1/agents/{name}/agent-versions/{ver}` | Get specific version |
| PUT | `/api/v1/people` | Create or upsert person |
| GET | `/api/v1/people` | List all people |
| GET | `/api/v1/people/{id}` | Get person |
| PUT | `/api/v1/people/{id}` | Merge-update person properties |
| PUT | `/api/v1/fingerprints` | Register environment fingerprint |
| POST | `/api/v1/events` | Create an event (core tracking call) |
| GET | `/api/v1/events` | List events (optional ?session_id filter) |
| GET | `/api/v1/events/{id}` | Get single event |
| GET | `/api/v1/sessions` | List sessions |
| GET | `/api/v1/sessions/{id}` | Get session + full event timeline |
| GET | `/api/v1/dashboard` | Analytics summary (totals + chart data) |
| GET | `/api/v1/dashboard/api-keys` | List API keys |
| POST | `/api/v1/dashboard/api-keys` | Create new API key |
| DELETE | `/api/v1/dashboard/api-keys/{id}` | Revoke API key |

## Auth Flow (`auth.py`)
1. Client sends `X-API-Key: dn_live_...` header
2. `get_project_id()` SHA-256 hashes the key and looks it up in `api_keys` table
3. Returns `project_id` — every query is then scoped to that project
4. `generate_api_key()` returns `(raw_key, prefix, hash)` — only `prefix` and `hash` are stored

## Database (`database.py`)
Single Supabase client singleton via `get_db()`. Uses the **service role key** (bypasses RLS).

## Event Creation Flow (`routers/events.py`)
When `POST /api/v1/events` is called:
1. Validate fingerprint exists in DB
2. Resolve agent name → agent DB id (if provided)
3. Resolve agent version name → id (if provided)
4. Upsert person (auto-creates if new person_id)
5. Upsert session (auto-creates if new session_id)
6. Insert event row with extracted token/latency fields
7. Insert message rows if `properties.messages` provided

## Database Schema Summary
```
projects          — top-level tenant
api_keys          — hashed keys scoped to a project
agents            — logical agent identities
agent_versions    — point-in-time agent configs
people            — end-users
fingerprints      — environment metadata per SDK init
sessions          — conversation threads
events            — individual LLM calls (core unit)
messages          — messages within an event
intents           — AI-analyzed user intents (future)
corrections       — AI-analyzed corrections (future)
resolutions       — session resolution outcomes (future)
```
Full schema: `supabase/schema.sql`

## Environment Variables (`.env`)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=service-role-key   ← NOT the anon key
SECRET_KEY=random-string
ALLOWED_ORIGINS=http://localhost:8081,http://localhost:3000
```
