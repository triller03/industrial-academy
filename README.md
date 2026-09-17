# AI-Powered Industrial Academy

An offline-capable learning platform for industrial automation engineering. Learners work through a
full 17-section engineering project lifecycle, guided by a Socratic AI mentor, then prove their
competence by diagnosing injected faults. Progress, certificates, and portfolio entries are issued
by the platform.

The flagship project is a **500 m³/h municipal water treatment plant** — 17 lifecycle sections and
8 fault scenarios.

---

## Features

- **Socratic AI mentor** — leads with questions instead of answers. Three modes:
  - `socratic` — default, probing questions that build reasoning.
  - `guided` — structured step-by-step scaffolding, triggered by frustration signals or a higher
    assistance level.
  - `safety` — hard override. Any safety keyword produces a direct, unambiguous procedure with no
    guessing. Assistance levels 1–5 control how much the mentor reveals.
- **17-section project lifecycle** — from project brief and process description through P&ID, I/O and
  tag lists, control philosophy, PLC/HMI/SCADA, alarms, interlocks, networking, testing, fault
  injection, troubleshooting, commissioning, and final documentation.
- **Fault injection & graded diagnosis** — decision trees drive 8 realistic faults. A learner selects
  the checks they would run and submits a diagnosis; scoring is 60% correct checks / 40% diagnosis,
  with feedback on missed checks, unnecessary checks, and known misdiagnoses.
- **Offline-first sync** — the client caches project bundles in IndexedDB, works fully disconnected,
  then syncs. Server-authoritative conflict resolution (completed beats in-progress, higher score,
  then newest), device binding limited to **3 devices** per user, and a 90-day offline sync window.
- **Offline content bundles** — content-addressed JSON bundles (sections, faults, mentor pack) are
  generated on startup and downloaded per project. `known_version` returns `204` when the client is
  already current. Bundles never contain grading answers.
- **Service worker** — caches the app shell so the UI loads with no connection; API responses are
  always fetched from the network (never cached).
- **Credentials** — a certificate and a portfolio entry are issued automatically when all 17 sections
  of a project are completed. Certificates carry a public verification token.
- **Content generator** — templates for water, mining, and manufacturing industries with difficulty
  tiers, so new projects can be generated rather than hand-authored.
- **Single-page frontend** — vanilla HTML/CSS/JS served by FastAPI. No build step, works offline.

---

## Architecture

```
industrial-academy/
├── backend/
│   ├── app/
│   │   ├── api/          # auth, projects, mentor, fault, progress, devices, sync, credentials
│   │   ├── content/      # project generator (17-section lifecycle, industry templates)
│   │   ├── core/         # security: password hashing, JWT access/refresh tokens
│   │   ├── fault/        # decision trees + diagnosis evaluator
│   │   ├── mentor/       # Socratic mentor engine (safety / guided / socratic)
│   │   ├── models/       # 13 SQLAlchemy tables
│   │   ├── offline/      # content-addressed bundle builder
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── sync/         # offline sync manager + device binding
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── seeder.py     # seed data: water treatment plant, 17 sections, 8 faults
│   │   └── main.py       # FastAPI app, routers, static frontend mount
│   ├── tests/            # integration + static checks (see Testing)
│   ├── requirements.txt
│   └── run.py
└── frontend/
    ├── index.html        # auth screen + app shell (6 tabs)
    ├── sw.js             # service worker (app-shell cache only)
    ├── css/styles.css
    └── js/
        ├── app.js        # SPA: routing, dashboard, mentor, faults, devices
        └── offline.js    # IndexedDB bundles, offline queue, local progress
```

**Stack:** FastAPI 0.115 · SQLAlchemy 2.0 · Pydantic 2 · SQLite · JWT (python-jose) ·
passlib/bcrypt.

The frontend is mounted at `/` via `StaticFiles`, so the API and UI are served from one process.

---

## Quick start

Requires **Python 3.12**.

```bash
cd backend

python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**.

Demo account (seeded on first startup):

```
email:    demo@academy.local
password: demo1234
```

API docs: http://127.0.0.1:8000/docs

### Configuration

Copy `backend/.env.example` to `backend/.env` to override defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./academy.db` | Database connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key — **change this in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Access token lifetime |
| `DEVICE_LIMIT_PER_USER` | `3` | Max bound devices per user |
| `MAX_DAYS_OFFLINE_SYNC` | `90` | Acceptable offline window |
| `SEED_ON_STARTUP` | `true` | Seed demo data if the database is empty |

---

## API overview

All endpoints are prefixed with `/api`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register` · `POST /auth/token` · `POST /auth/refresh` · `GET /auth/me` |
| Projects | `GET /projects` · `GET /projects/{id}` · `GET /projects/{id}/sections/{key}` · `GET /projects/{id}/progress` |
| Faults | `GET /projects/{id}/faults` · `GET /projects/{id}/faults/{fault_id}` · `POST /fault/diagnose` |
| Mentor | `POST /mentor/chat` · `POST /mentor/solution` |
| Progress | `GET /progress` · `POST /progress` |
| Devices | `POST /devices/authorize` · `GET /devices` · `POST /devices/revoke` · `POST /devices/{id}/touch` |
| Sync | `POST /sync` |
| Offline | `GET /offline/manifest` · `GET /projects/{id}/offline-bundle` · `POST /offline/rebuild` (admin) |
| Credentials | `GET /credentials/certificates` · `GET /credentials/portfolio` · `GET /credentials/certificates/verify/{token}` |
| Health | `GET /health` |

The fault-detail endpoint deliberately omits the expected checks and correct diagnosis; those are
only revealed by `POST /fault/diagnose` after a learner submits an attempt.

---

## The 17-section lifecycle

`project_brief` · `process_description` · `p_and_id` · `io_list` · `tag_list` ·
`control_philosophy` · `plc_program` · `hmi` · `scada` · `alarms` · `interlocks` · `networking` ·
`testing` · `fault_injection` · `troubleshooting` · `commissioning` · `final_documentation`

## Seeded fault scenarios

`dosing-pump-overrun` · `filter-bed-blinding` · `magflow-failed-low` · `level-loop-open` ·
`chlorine-airlock` · `pump-permissive-blocked` · `backwash-valve-feedback` · `comms-loss-scada`

---

## Offline sync model

The client keeps a stable device fingerprint and queues local changes while disconnected. On sync,
the server:

1. Rejects unknown or revoked devices (`403`).
2. Resolves conflicts server-authoritatively — **completed > in-progress**, then **higher score**,
   then **newest timestamp**. Losing changes are returned in `conflicts`.
3. Applies accepted changes and returns the authoritative `server_state`.

Offline learning flow:

1. The client authorizes its device and calls `GET /offline/manifest`.
2. It downloads each project bundle (skipped with `204` when `known_version` matches) and stores it in
   IndexedDB.
3. While offline it records section completions and fault attempts locally; the mentor falls back to a
   local rule-based pack.
4. `POST /sync` flushes the queue, including `fault_attempt` changes which are graded server-side and
   folded into `fault_injection` progress.

---

## Testing

With the server running (`python run.py`), from `backend/`:

```bash
.\.venv\Scripts\python.exe tests\smoke_test.py        # 25 end-to-end API checks
.\.venv\Scripts\python.exe tests\refresh_test.py      # refresh-token rotation + reuse rejection
.\.venv\Scripts\python.exe tests\offline_test.py      # 13 offline bundle + sync checks
.\.venv\Scripts\python.exe tests\frontend_static.py   # JS bracket balance + element-ID references
```

---

## Notes

- `bcrypt` is pinned to `4.0.1`: `passlib` 1.7.4 is not compatible with `bcrypt` 5.x.
- SQLite is used for zero-config local development. Set `DATABASE_URL` for any other database.
- Change `SECRET_KEY` before exposing the service.
