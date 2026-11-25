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

```bash
git clone https://github.com/Razoradams9/opencampus.git
cd opencampus
```

Commands below start from the repository root, in a bash-compatible shell
(macOS/Linux terminal, Git Bash or WSL). Windows PowerShell users: see
[Windows (PowerShell)](#windows-powershell).

### 1. Configuration

```bash
cd backend
cp .env.example .env
```

Replace every `<...>` in `.env` (generate values with
`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`). `.env` is
git-ignored; never commit it.

### 2. Database

With Docker:

```bash
docker compose --env-file backend/.env up -d
```

With a local PostgreSQL (run as a superuser):

```bash
cd backend
set -a; . ./.env; set +a
bash db/init/01-roles.sh --print | sudo -u postgres psql -v ON_ERROR_STOP=1
```

Either way this creates the `opencampus_owner` (migrations) and
`opencampus_app` (runtime, RLS-bound) roles and the `opencampus` and
`opencampus_test` databases.

### 3. Backend

```bash
cd backend
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
cd frontend
npm install
```

## Windows (PowerShell)

PowerShell 5.1 has no `&&`; run commands one per line. Requires Docker
Desktop for Postgres. From the repository root:

```powershell
cd backend
$gen = { python -c "import secrets;print(secrets.token_urlsafe(32))" }
$su = & $gen; $own = & $gen; $app = & $gen; $jwt = & $gen; $rl = & $gen
@"
OPENCAMPUS_ENV=development
OPENCAMPUS_DB_SUPERUSER_PASSWORD=$su
OPENCAMPUS_DB_OWNER_PASSWORD=$own
OPENCAMPUS_DB_APP_PASSWORD=$app
OPENCAMPUS_DATABASE_URL=postgresql+psycopg://opencampus_app:$app@127.0.0.1:5432/opencampus
OPENCAMPUS_MIGRATION_DATABASE_URL=postgresql+psycopg://opencampus_owner:$own@127.0.0.1:5432/opencampus
OPENCAMPUS_TEST_DATABASE_URL=postgresql+psycopg://opencampus_app:$app@127.0.0.1:5432/opencampus_test
OPENCAMPUS_TEST_MIGRATION_DATABASE_URL=postgresql+psycopg://opencampus_owner:$own@127.0.0.1:5432/opencampus_test
OPENCAMPUS_JWT_SECRET=$jwt
OPENCAMPUS_RATE_LIMIT_SECRET=$rl
OPENCAMPUS_COOKIE_SECURE=false
"@ | Set-Content -Encoding ascii .env
cd ..
docker compose --env-file backend\.env up -d
cd backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed-demo
uvicorn app.main:app --reload --port 8000 --no-proxy-headers
```

Second PowerShell window, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

## Run (development)

```bash
# Terminal 1 — API on http://127.0.0.1:8000
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000 --no-proxy-headers
```

```bash
# Terminal 2 — UI on http://localhost:5173
cd frontend
npm run dev
```

Open http://localhost:5173 and sign in or create an account (institution code
`aldermoor` or `halvard` after seeding). API docs: http://127.0.0.1:8000/docs

### Password reset emails in development

With no SMTP configured, emails are written to `backend\.dev-mail\` instead
of being sent (git-ignored). After "Forgot password?", show the newest one:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli dev-mail
```

Copy the `http://localhost:5173/reset-password#token=…` link into the
browser. `.eml` files also open in Outlook or any text editor. For production
SMTP settings see `backend/.env.example` and `docs/security.md`.

## Migrations

```bash
cd backend
alembic upgrade head                               # apply
alembic downgrade -1                               # roll back one
alembic revision --autogenerate -m "describe it"   # new migration (review it!)
```

Migrations connect with `OPENCAMPUS_MIGRATION_DATABASE_URL` (owner role).
New institution-owned tables must include `institution_id`, enable + force
RLS, add policies and grant the app role, in the migration itself.

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

Tests need `OPENCAMPUS_TEST_DATABASE_URL` / `OPENCAMPUS_TEST_MIGRATION_DATABASE_URL`
(a database whose name contains `test`). The suite migrates it from scratch
and connects as the app role, so RLS is exercised for real.

```bash
cd frontend && npm run build    # type-check + production build
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
`OPENCAMPUS_JWT_SECRET` and `OPENCAMPUS_RATE_LIMIT_SECRET` (each ≥ 32 chars, different). The API refuses to start without them,
and refuses insecure cookies when `OPENCAMPUS_ENV=production`.
