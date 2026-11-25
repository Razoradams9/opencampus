# OpenCampus

Open-source, multi-tenant academic platform. **Current milestone: M2 — Identity, authentication and multi-tenancy.**

- **M0 — Foundation:** FastAPI backend, health endpoint, React shell, design tokens.
- **M1 — Student dashboard:** responsive Home dashboard on fictional demo content.
- **M2 — Identity:** PostgreSQL, real accounts (Argon2id), JWT access tokens +
  rotating HttpOnly refresh cookies, institutions and memberships, backend role
  checks, tenant isolation with row-level security, login/registration UI and
  institution switching. Dashboard *content* is still demo data.

No AI, coursework or faculty/admin dashboards exist yet. Security design:
[`docs/security.md`](docs/security.md).

## Stack

| Layer    | Technology                                                       |
| -------- | ---------------------------------------------------------------- |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, Lucide             |
| Backend  | Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Argon2id, PyJWT  |
| Database | PostgreSQL 14+ (16 recommended)                                  |

## Prerequisites

- Python 3.11+, Node.js 20.19+ (or 22.12+)
- PostgreSQL: Docker (Compose file provided) **or** a local install

## Setup

### 1. Configuration

```bash
cd opencampus/backend
cp .env.example .env
```

Replace every `<...>` in `.env` (generate values with
`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`). `.env` is
git-ignored; never commit it.

### 2. Database

With Docker:

```bash
cd opencampus
docker compose --env-file backend/.env up -d
```

With a local PostgreSQL (run as a superuser):

```bash
cd opencampus/backend
set -a; . ./.env; set +a
bash db/init/01-roles.sh --print | sudo -u postgres psql -v ON_ERROR_STOP=1
```

Either way this creates the `opencampus_owner` (migrations) and
`opencampus_app` (runtime, RLS-bound) roles and the `opencampus` and
`opencampus_test` databases.

### 3. Backend

```bash
cd opencampus/backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed-demo      # optional: fictional demo institutions + users
```

`seed-demo` prompts for one password shared by all demo accounts (or reads
`OPENCAMPUS_CLI_PASSWORD`). Accounts include
`maya.okafor@aldermoor.example` (student), `iris.moreau@aldermoor.example`
(college admin), and `sam.achebe@aldermoor.example` (member of two colleges).

Platform administrators are created only from the CLI:

```bash
python -m app.cli create-platform-admin --email ops@example.org --name "Ops"
```

### 4. Frontend

```bash
cd opencampus/frontend
npm install
```

## Run (development)

```bash
# Terminal 1 — API on http://127.0.0.1:8000
cd opencampus/backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 — UI on http://localhost:5173
cd opencampus/frontend
npm run dev
```

Open http://localhost:5173 and sign in or create an account (institution code
`aldermoor` or `halvard` after seeding). API docs: http://127.0.0.1:8000/docs

## Migrations

```bash
cd opencampus/backend
alembic upgrade head                               # apply
alembic downgrade -1                               # roll back one
alembic revision --autogenerate -m "describe it"   # new migration (review it!)
```

Migrations connect with `OPENCAMPUS_MIGRATION_DATABASE_URL` (owner role).
New institution-owned tables must include `institution_id`, enable + force
RLS, add policies and grant the app role, in the migration itself.

## Tests

```bash
cd opencampus/backend && .venv/bin/python -m pytest -q
```

Tests need `OPENCAMPUS_TEST_DATABASE_URL` / `OPENCAMPUS_TEST_MIGRATION_DATABASE_URL`
(a database whose name contains `test`). The suite migrates it from scratch
and connects as the app role, so RLS is exercised for real.

```bash
cd opencampus/frontend && npm run build    # type-check + production build
```

## API overview

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/api/health` | public |
| GET | `/api/institutions/{slug}` | public |
| POST | `/api/auth/register`, `/api/auth/login` | public |
| POST | `/api/auth/refresh`, `/api/auth/logout` | refresh cookie + CSRF header |
| GET | `/api/auth/me`, `/api/auth/sessions` | signed in |
| POST | `/api/auth/switch-institution` | signed in, member of target |
| DELETE | `/api/auth/sessions/{id}` | signed in, own session |
| GET | `/api/institution` | member of active institution |
| GET/PATCH | `/api/institution/members[/{id}]` | college_admin |
| POST/PATCH | `/api/platform/institutions[/{slug}]`, `…/{slug}/admins` | platform_admin |

## Configuration

See `backend/.env.example` for every variable. Required: `OPENCAMPUS_DATABASE_URL`,
`OPENCAMPUS_JWT_SECRET` (≥ 32 chars). The API refuses to start without them,
and refuses insecure cookies when `OPENCAMPUS_ENV=production`.
