# M4 Academic Batch — Environment Setup Note

Generated: 2026-11-26

## Docker / Database

- **Container**: `opencampus-postgres-1` — running (Docker Desktop)
- **Host port**: `15432` (mapped → container 5432)
- **PostgreSQL version**: 16.16 (Debian)
- **Reachability**: ✅ Confirmed — `psql` via `127.0.0.1:15432` with `opencampus_app` user returns a valid `SELECT version()` response
- **Connection string** (app role): `postgresql+psycopg://opencampus_app:***@127.0.0.1:15432/opencampus`
- **Migration URL** (owner role): `postgresql+psycopg://opencampus_owner:***@127.0.0.1:15432/opencampus`
- **Test DB**: `opencampus_test` available at the same host/port
- **psql binary**: `C:\Program Files\PostgreSQL\18\bin\psql.exe` (local PG18 client install used for connectivity check)

## Git

- **Branch**: `main`
- **HEAD**: `d8b7978 feat: three-color palette + dashboard declutter`
- **Status**: branch is ahead of `origin/main` by 1 commit; untracked files in `frontend/.agents/` only — working tree clean otherwise

## Backend

- **Virtual environment**: `backend/.venv` — ✅ present
- **Framework**: FastAPI / SQLAlchemy 2.0 (sync) / psycopg3 / Alembic / Argon2id / PyJWT
- **Runtime**: Python 3.11+

## Frontend

- **Directory**: `frontend/` — ✅ present
- **Stack**: React 19 / TypeScript / Vite 8 / Tailwind CSS 4

## Environment Variables (backend/.env)

| Variable | Value |
|---|---|
| `OPENCAMPUS_ENV` | `development` |
| `OPENCAMPUS_DB_PORT` | `15432` |
| `OPENCAMPUS_COOKIE_SECURE` | `false` |
| `OPENCAMPUS_FRONTEND_URL` | `http://localhost:5173` |
| Passwords / secrets | redacted — present in `backend/.env` |

## Ready to Proceed

All prerequisites confirmed. M4.1 (Courses and Subjects) may begin.
