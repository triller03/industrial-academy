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
  tiers, so new projects can be generated rather than hand-authored. Exposed as an admin endpoint:
  each generated project gets the full 17-section lifecycle plus graded fault scenarios, and is
  packaged into an offline bundle automatically.
- **Audit trail** — user actions (section completions, credential issuance, fault attempts, syncs,
  project generation, bundle rebuilds) are recorded in `activity_logs` and readable via `GET /activity`.
- **Single-page frontend** — vanilla HTML/CSS/JS served by FastAPI. No build step, works offline.
- **Live integrations** — a Modbus TCP server bridges FACTORY I/O into the app (port 502), with
  optional Siemens S7 (snap7) and WinCC/OPC UA links. Status + live registers under **Admin → Live
  integrations**; see *Integrations* below.

---

## Architecture

```
industrial-academy/
├── backend/
│   ├── app/
│   │   ├── activity.py    # audit-trail helper (activity_logs)
│   │   ├── api/          # auth, projects, mentor, fault, progress, devices, sync, credentials, activity, integrations
│   │   ├── content/      # project generator (17-section lifecycle, industry templates) + admin service
│   │   ├── core/         # security: password hashing, JWT access/refresh tokens
│   │   ├── fault/        # decision trees + diagnosis evaluator + check palette
│   │   ├── integrations/ # Modbus TCP (FACTORY I/O), snap7 (S7), OPC UA (WinCC) links + manager
│   │   ├── mentor/       # Socratic mentor engine (safety / guided / socratic)
│   │   ├── models/       # 14 SQLAlchemy tables
│   │   ├── offline/      # content-addressed bundle builder
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── sync/         # offline sync manager + device binding
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── seeder.py     # seed data: water treatment plant, 17 sections, 8 faults
│   │   └── main.py       # FastAPI app, routers, static frontend mount
│   ├── tests/            # integration + static checks (see Testing)
│   ├── requirements.txt
│   ├── requirements-integrations.txt   # optional hardware-link dependencies
│   └── run.py
└── frontend/
    ├── index.html        # auth screen + app shell (6 tabs)
    ├── sw.js             # service worker (app-shell cache only)
    ├── css/styles.css
    └── js/
        ├── app.js        # SPA: routing, dashboard, mentor, faults, devices, integrations
        └── offline.js    # IndexedDB bundles, offline queue, local progress
```

**Stack:** FastAPI 0.115 · SQLAlchemy 2.0 · Pydantic 2 · SQLite · JWT (python-jose) ·
passlib/bcrypt · pymodbus (optional) · python-snap7 (optional) · asyncua (optional).

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
# optional: live integrations (Modbus / S7 / OPC UA) — API also runs without them
pip install -r requirements-integrations.txt
python run.py
```

You can also run it from **Visual Studio 2026** (install the *Python development* workload): open the
repo root as a folder, then run `backend/run.py` (F5 debugging works once the workload is installed),
or run the API from the integrated terminal: `Set-Location backend` then
`..\.venv\Scripts\python.exe run.py`.

Open **http://127.0.0.1:8000**.

Demo account (seeded on first startup):

```
email:    demo@academy.local
password: demo1234        # regular student

email:    admin@academy.local
password: admin1234       # admin — can generate projects & view the audit trail
```

> The seeded accounts are for local development only; remove them before production.

API docs: http://127.0.0.1:8000/docs

### Configuration

Copy `.env.example` (repo root) to `.env` to override defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `production` disables docs/schema and arms the guards + hardening |
| `DATABASE_URL` | `sqlite:///./academy.db` | Database connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key — **change this in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Access token lifetime |
| `CORS_ORIGINS` | `*` | Comma-separated allowed browser origins |
| `REQUIRE_HTTPS` | `false` | Reject plain-http clients (`426`) when behind TLS |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `60` | Per-IP login/refresh budget |
| `RATE_LIMIT_GLOBAL_PER_MINUTE` | `600` | Per-IP budget for the remaining `/api/*` surface |
| `DEVICE_LIMIT_PER_USER` | `3` | Max bound devices per user |
| `MAX_DAYS_OFFLINE_SYNC` | `90` | Acceptable offline window |
| `SEED_ON_STARTUP` | `true` | Seed demo data if the database is empty |
| `INTEGRATIONS_ENABLED` / `MODBUS_ENABLED` / `SIMULATED_PLANT` | `true` | Integration layer on/off |
| `S7_ENABLED` / `OPCUA_ENABLED` | `false` | S7 / WinCC links (see Integrations) |

---

## API overview

All endpoints are prefixed with `/api`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register` · `POST /auth/token` · `POST /auth/refresh` · `GET /auth/me` |
| Projects | `GET /projects` · `GET /projects/{id}` · `GET /projects/{id}/sections/{key}` · `GET /projects/{id}/progress` · `POST /projects/generate` (admin) |
| Faults | `GET /projects/{id}/faults` · `GET /projects/{id}/faults/{fault_id}` · `POST /fault/diagnose` |
| Mentor | `POST /mentor/chat` · `POST /mentor/solution` |
| Progress | `GET /progress` · `POST /progress` |
| Devices | `POST /devices/authorize` · `GET /devices` · `POST /devices/revoke` · `POST /devices/{id}/touch` |
| Sync | `POST /sync` |
| Offline | `GET /offline/manifest` · `GET /projects/{id}/offline-bundle` · `POST /offline/rebuild` (admin) |
| Credentials | `GET /credentials/certificates` · `GET /credentials/portfolio` · `GET /credentials/certificates/verify/{token}` |
| Activity | `GET /activity` (admin sees all users) |
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

## Integrations (FACTORY I/O · TIA Portal · WinCC)

Optional hardware/simulation links. Install them with
`pip install -r requirements-integrations.txt`; without them the links simply report *disabled*.
Enable with env vars: `INTEGRATION_SIMS_PLANT`/`INTEGRATION_MODBUS_ENABLED` are on by default;
`INTEGRATION_S7_ENABLED=1`, `INTEGRATION_OPCUA_ENABLED=1` switch on the others (see `app/config.py`).

### FACTORY I/O → Modbus TCP bridge (default on, port 502)

In FACTORY I/O pick **Driver → Modbus TCP/IP Client** and point it at `127.0.0.1:502`:

| FACTORY I/O configuration | Setting |
|---|---|
| Read Digital | **Coils** |
| Digital Inputs (sensors) | offset **64**, e.g. 10 coils |
| Digital Outputs (actuators) | offset **0**, e.g. 8 coils |
| Read Register | **Input Registers** |
| Register Inputs (measurements) | offset **0**, e.g. 6 registers |
| Register Outputs (setpoints) | offset **0**, e.g. 5 registers (Holding) |

The app writes sensor bits and analog measurements into the FIO side; FIO writes actuator bits and
setpoints back into the app. All analog values are scaled **×100** (FIO *Scale: 100*). With a real
PLC absent, the built-in plant simulator drives the sensor/measurement registers every second; the
admin view (**Admin → Live integrations**) shows the live map, which round-trips over real Modbus.
`POST /api/integrations/snapshot` logs the current register map to the audit trail.

### Siemens S7 (snap7)

`INTEGRATION_S7_ENABLED=1`, `INTEGRATION_S7_IP=192.168.0.1` (rack 0, slot 1, DB 1). The link polls
DB1: byte 0 bits 0–3 = `start/running/estop/reset`, INTs at bytes 2 = `level`, 4 = `speed`,
6 = `speed_setpoint` (writable). Use **Admin → Live integrations → Test S7** to probe.

### WinCC / SCADA (OPC UA)

`INTEGRATION_OPCUA_ENABLED=1`, `INTEGRATION_OPCUA_URL=opc.tcp://127.0.0.1:4840`,
`INTEGRATION_OPCUA_NODES=ns=2;s=Tag1,ns=2;s=Tag2`. The link polls the listed node ids and shows live
values in the admin view.

---

## Testing

With the server running (`python run.py`), from `backend/`:

```bash
.\.venv\Scripts\python.exe tests\smoke_test.py        # 25 end-to-end API checks
.\.venv\Scripts\python.exe tests\refresh_test.py      # refresh-token rotation + reuse rejection
.\.venv\Scripts\python.exe tests\offline_test.py      # 14 offline bundle + sync checks
.\.venv\Scripts\python.exe tests\admin_test.py        # 11 admin/rebuild/auth-path checks
.\.venv\Scripts\python.exe tests\generator_test.py    # 20 project-generation + audit-trail checks
.\.venv\Scripts\python.exe tests\frontend_static.py   # JS bracket balance + element-ID references
.\.venv\Scripts\python.exe tests\integration_test.py  # 20 Modbus bridge + live-register checks
.\.venv\Scripts\python.exe tests\security_test.py     # headers, CSP, CORS, rate-limit checks
```

Or run all suites at once (checks the server is up first):

```bash
.\.venv\Scripts\python.exe tests\run_all.py
```

The same pipeline runs automatically in CI (`.github/workflows/ci.yml`) on every push to `main`.

---

## Production deployment

The repo ships with a `Dockerfile`, `docker-compose.yml`, `.env.example` and CI
so the platform deploys anywhere with a single command:

```bash
cp .env.example .env   # then edit with real values (see below)
docker compose up -d --build
```

Required before exposing the service:

1. **`ENVIRONMENT=production`** is set by the compose file — it disables `/docs`,
   `/redoc` and the OpenAPI schema, and arms the bulk of the hardening.
2. **`SECRET_KEY`** must be a real random value, or the app refuses to boot:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
3. **`CORS_ORIGINS`** should list your frontend origin(s), not `*`.
4. **`REQUIRE_HTTPS=1`** plus a TLS-terminating reverse proxy (nginx/Caddy/Traefik);
   the app then rejects plain-http clients with `426 Upgrade Required`.
5. Delete or disable the seeded demo accounts before opening it to real users.

Persistent state:
- SQLite DB → `./data/academy.db` (auto-created container volume)
- Generated offline bundles → `./data/offline_packages/`

CI smoke-tests every PR; the full 8-suite gate runs on `main`.

## Security

Baseline hardening ships in `backend/app/middleware.py` and is verified by
`tests/security_test.py`:

| Control | Detail |
| --- | --- |
| Response headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` |
| CSP (SPA) | `default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'` |
| Auth rate limiting | Per-IP sliding window on `/api/auth/*` (default 60/min) + global `/api/*` budget |
| Login hardening | Generic 401 on bad credentials; accounts can be disabled; passwords ≥ 8 chars at registration |
| Token lifecycle | Refresh tokens rotate on use and are rejected on reuse |
| Production guard | Boot fails if `ENVIRONMENT=production` with the default `SECRET_KEY`; docs/traces disabled |
| HTTPS enforcement | `REQUIRE_HTTPS=1` returns `426` for plain-http without a `X-Forwarded-Proto: https` |

### Industrial safety interlocks

The simulated plant implements a small but honest e-stop interlock:

- An `estop` coil deglitched for **1.5 s** trips the failsafe.
- Under failsafe the plant decays speed to zero, freezes level/flow, clears the
  running lamp and halts part movement **regardless of what the external PLC
  (FACTORY I/O) keeps commanding**, and logs `failsafe_enabled` to the event
  queue.
- `estop_asserted` / `failsafe_enabled` / `estop_released` events and the live
  safety state (`GET /api/integrations`) are shown in Admin → Live integrations.

> The failsafe is a teaching simulation bound to the plant simulator. A real
> machine calls for a physical, certified safety relay chain — never rely on
> software alone.

---

## Notes

- `bcrypt` is pinned to `4.0.1`: `passlib` 1.7.4 is not compatible with `bcrypt` 5.x.
- SQLite is used for zero-config local development. Set `DATABASE_URL` for any other database.
- Change `SECRET_KEY` before exposing the service.
