# OpenCampus

Open-source, multi-tenant academic platform. **Current milestone: M0 — Foundation.**

M0 delivers only the base: a FastAPI backend with a health endpoint, a React
application shell, the design-token system, and a verified frontend↔backend
connection. No authentication, database, or academic features exist yet.

## Stack

| Layer    | Technology                                            |
| -------- | ----------------------------------------------------- |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, Lucide  |
| Backend  | Python 3.11+, FastAPI, Uvicorn                        |

## Structure

```
opencampus/
├── backend/
│   ├── app/
│   │   ├── api/health.py      GET /api/health
│   │   ├── core/config.py     environment-based settings
│   │   └── main.py            app factory, CORS, router wiring
│   ├── tests/                 pytest suite
│   ├── requirements.txt       runtime deps
│   └── requirements-dev.txt   + test deps
├── frontend/
│   ├── src/
│   │   ├── components/        BrandMark, Sidebar, TopBar, ConnectionPill, Placeholder
│   │   ├── layouts/AppShell   sidebar + top bar frame
│   │   ├── pages/Dashboard    welcome, live system status, module placeholders
│   │   ├── lib/               API client, useBackendHealth hook
│   │   └── styles/index.css   design tokens + Tailwind theme
│   └── vite.config.ts         dev proxy /api → :8000
└── docs/design-system.md
```

## Prerequisites

- Python 3.11+
- Node.js 20.19+ (or 22.12+) and npm

## Setup

Backend:

```bash
cd opencampus/backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Frontend:

```bash
cd opencampus/frontend
npm install
```

## Run (development)

Use two terminals.

```bash
# Terminal 1 — API on http://127.0.0.1:8000
cd opencampus/backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 — UI on http://localhost:5173
cd opencampus/frontend
npm run dev
```

Open http://localhost:5173. The top-right pill and the **System status** panel
reflect the real result of `GET /api/health` (polled every 30 s; **Recheck**
forces a check). Stop the backend and recheck to see the offline state.

Interactive API docs: http://127.0.0.1:8000/docs

## How the frontend reaches the backend

- **Development:** the browser calls `/api/...` on the Vite origin; Vite proxies
  it to `http://127.0.0.1:8000`. Override with `OPENCAMPUS_API_URL`.
- **Separate origins:** set `VITE_API_BASE_URL` (e.g. `https://api.example.edu`)
  at build time, and allow the UI origin on the backend with
  `OPENCAMPUS_CORS_ORIGINS` (comma-separated; default `http://localhost:5173`).

## Configuration

| Variable                  | Where    | Default                 |
| ------------------------- | -------- | ----------------------- |
| `OPENCAMPUS_ENV`          | backend  | `development`           |
| `OPENCAMPUS_CORS_ORIGINS` | backend  | `http://localhost:5173` |
| `OPENCAMPUS_API_URL`      | Vite dev | `http://127.0.0.1:8000` |
| `VITE_API_BASE_URL`       | frontend | empty (same origin)     |

## Checks

```bash
cd opencampus/backend && .venv/bin/python -m pytest -q
```

```bash
cd opencampus/frontend && npm run build    # type-check + production build
```

## API

`GET /api/health` → `200`

```json
{
  "status": "ok",
  "service": "OpenCampus API",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-11-25T05:46:06.915871Z",
  "uptime_seconds": 0.329
}
```

This is a liveness check of the API process only; there are no downstream
dependencies to report on yet.
