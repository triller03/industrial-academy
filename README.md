# ASAPA — Industrial Automation Training Platform

![ASAPA](packaging/desktop/assets/asapa_lockup.png)

*ASAPA (ASAP Automation) — formerly the AI-Powered Industrial Academy — is an*
*offline-capable learning platform for industrial automation engineering.*
*"Don't teach software buttons. Teach the complete industrial engineering lifecycle."*

Learners work through a full 17-section engineering project lifecycle, guided by a Socratic AI
mentor, then prove their competence by diagnosing injected faults. Progress, certificates, and
portfolio entries are issued by the platform.

The platform ships authored learning paths — the **Automation Technician
Foundations** curriculum (4 projects: motor starter, instrument loop, conveyor
sorter cell, chlorine dosing skid) building up to the flagship **500 m³/h
municipal water treatment plant**, plus the **Mining & Minerals** track
(`mining-primary-crushing`, a 17-section primary crushing plant with 4 graded
faults). See [`CURRICULUM.md`](CURRICULUM.md) for the full tracks, and Admin →
*Learning content* for the sync action.

---

## Features

- **Socratic AI mentor** — leads with questions instead of answers. Three modes:
  - `socratic` — default, probing questions that build reasoning.
  - `guided` — structured step-by-step scaffolding, triggered by frustration signals or a higher
    assistance level.
  - `safety` — hard override. Any safety keyword produces a direct, unambiguous procedure with no
    guessing. Assistance levels 1–5 control how much the mentor reveals.
- **Real LLM reasoning (optional)** — set `AI_PROVIDER` (+ key) and the mentor answers through a
  real model (OpenAI, OpenRouter, Anthropic Claude, Google Gemini, or a local Ollama). Without a
  provider it falls back to the bundled deterministic engine, so it still works fully offline. The
  safety override is *never* delegated to the model. See [AI Mentor backend §](##-ai-mentor-backend).
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
- **Tiered plans & HWID licensing** — Sandbox (free, 5 fault diagnoses/day) · Student Pro ·
  Professional · Institutional. 30-day full-access trial, per-device HWID binding (3 devices),
  signed offline license tokens, and a local checkout gateway by default with optional Stripe /
  Paynow (Zimbabwe) webhooks. Plan gates: project generation (Student Pro+), FRS/P&ID schematic
  viewer (Student Pro+), public portfolio publishing (Professional+), TIA bridge (Professional+).
- **FRS/P&ID structured viewer** — each project's `p_and_id` section is parsed into a structured
  view (instruments, I/O map, tag register) served behind the `can_schematic_viewer` gate.
- **Public portfolio** — completed projects can be published to a shareable public URL
  (`/portfolio/{entry_ref}`), gated to Professional+ plans.
- **TIA Openness bridge** — `probe`, rule-based SCL pre-compile validation (`validate-scl`) and IEC
  61131-3 tag CSV import validation, exposed under `/api/integrations/tia/*`. Hardware dependent:
  without a licensed TIA host the probe reports *not available* and validators run offline.
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
│   │   ├── api/          # auth, projects, mentor, fault, progress, devices, sync, credentials, activity, integrations, stats, billing, licensing
│   │   ├── content/      # project generator (17-section lifecycle, industry templates), mining_track + admin service
│   │   ├── core/         # security: password hashing, JWT access/refresh tokens, licensing tokens
│   │   ├── fault/        # decision trees + diagnosis evaluator + check palette
│   │   ├── integrations/ # Modbus TCP (FACTORY I/O), snap7 (S7), OPC UA (WinCC) links + manager
│   │   ├── mentor/       # Socratic mentor engine (safety / guided / socratic)
│   │   ├── models/       # SQLAlchemy tables
│   │   ├── offline/      # content-addressed bundle builder
│   │   ├── orchestrator/ # Engineering Desk: project pipeline state machine, desktop tool registry + launcher
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── schematics.py # FRS/P&ID structured viewer parser
│   │   ├── sync/         # offline sync manager + device binding
│   │   ├── tia/          # TIA Openness bridge: probe, SCL validator, tag-CSV importer
│   │   ├── plans.py      # tier definitions, gates, daily-budget + trial helpers
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── init_db.py    # first-run init: schema, seed, curriculum, offline bundles
│   │   ├── seeder.py     # seed data: water treatment plant, 17 sections, 8 faults
│   │   └── main.py       # FastAPI app, routers, static frontend mount
│   ├── tests/            # 15 integration + static suites (see Testing)
│   ├── requirements.txt
│   ├── requirements-integrations.txt   # optional hardware-link dependencies
│   └── run.py
├── frontend/
│   ├── index.html        # auth screen + app shell (6 tabs)
│   ├── sw.js             # service worker (app-shell cache only)
│   ├── css/styles.css
│   └── js/
│       ├── app.js        # SPA: routing, dashboard, mentor, faults, devices, integrations
│       └── offline.js    # IndexedDB bundles, offline queue, local progress
└── packaging/
    ├── Build-Iso.ps1     # builds the offline installer ISO (Windows IMAPI2)
    ├── setup/            # offline installer: setup.bat/ps1, start/stop, uninstall, INSTALL.txt
    └── desktop/          # Windows desktop app: launcher.py + build-desktop.ps1 + installer.iss
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

Demo accounts (seeded on first startup):

```
email:    demo@academy.local
password: demo1234        # professional plan (full features: portfolio, TIA, schematic)

email:    admin@academy.local
password: admin1234       # admin + institutional plan — can generate projects & view the audit trail
```

> The seeded accounts are for local development only; remove them before production.

API docs: http://127.0.0.1:8000/docs

### Configuration

Copy `backend/.env.example` to `backend/.env` to override defaults (a repo-root copy also exists for
the container build):

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
| `TRIAL_GRACE_DAYS` | `30` | Full-access trial days for fresh users |
| `MAX_FREE_FAULT_ATTEMPTS_PER_DAY` | `5` | Sandbox cap on online fault diagnoses per day |
| `LICENSE_LENGTH_DAYS` | `365` | Paid license duration once activated |
| `INTERFACE_ORIGIN` | `` | Public origin used to build shareable portfolio URLs |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_MAP` | `` | Stripe billing (empty = local test gateway) |
| `PAYNOW_INTEGRATION_ID` / `PAYNOW_API_KEY` / `PAYNOW_RESULT_URL` | `` | Paynow billing (Zimbabwe) |
| `TIA_OPENNESS_ENABLED` | `false` | Hardware TIA Openness host on / off (graceful degradation) |
| `AI_PROVIDER` | `` | Mentor LLM backend: `openai` / `openrouter` / `anthropic` / `gemini` / `ollama` (blank = deterministic engine) |
| `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` | `` | Provider credentials; `AI_BASE_URL` points any OpenAI-compatible endpoint (Ollama, vLLM, Groq, DeepSeek…) |
| `AI_MAX_TOKENS` / `AI_TIMEOUT_SECONDS` / `AI_TEMPERATURE` | `900` / `60` / `0.7` | LLM generation tuning |
| `SEED_ON_STARTUP` | `true` | Seed demo data if the database is empty |
| `INTEGRATIONS_ENABLED` / `MODBUS_ENABLED` / `SIMULATED_PLANT` | `true` | Integration layer on/off |
| `S7_ENABLED` / `OPCUA_ENABLED` | `false` | S7 / WinCC links (see Integrations) |
| `ORCHESTRATOR_ENABLED` | `true` | Engineering Desk on/off |
| `ORCHESTRATOR_MODE` | `auto` | `auto` (live when a tool is installed) / `simulate` / `live` |
| `ORCHESTRATOR_APP_PATHS` | `` | JSON override: `{"tia": "…", "wincc": "…", "factoryio": "…"}` to bypass auto-detection |

---

## AI Mentor backend

The mentor is a **hybrid**: a small deterministic safety/behaviour engine in front of an optional
LLM.

```text
learner message
      │
      ▼
┌ safety keyword / section? ───────── yes ──▶ deterministic safety steps (never the model)
      │ no
      ▼
mode & level decided deterministically (socratic / guided)
      │
      ├─ AI_PROVIDER set ──▶ real LLM writes the reply (SYSTEM_PROMPT + recent chat history)
      └─ no provider         └─▶ deterministic Socratic engine (works fully offline)
      │
      └─ LLM calls the function only when the prompt can't involve a live hazard.
```

Enabled by env (see Configuration); provider choices:

- `openai` → `https://api.openai.com/v1` (default model `gpt-4o-mini`)
- `openrouter` → `https://openrouter.ai/api/v1` — runtime model switching, one key
- `anthropic` → `https://api.anthropic.com/v1` (`claude-3-5-sonnet-latest` default)
- `gemini` → `https://generativelanguage.googleapis.com` (`gemini-2.0-flash` default)
- `ollama` → `http://127.0.0.1:11434/v1` — local, private, works inside the desktop app offline
- any OpenAI-compatible base via `AI_PROVIDER=openai` + `AI_BASE_URL` (Ollama, vLLM, Groq, DeepSeek…)

The backend exposes `GET /mentor/status` (provider + model in effect); the frontend shows a small
chip next to the AI Mentor title. If the provider is unreachable, the engine logs and falls back to
the deterministic response, so chat never errors out. `POST /mentor/solution` stays gated by plan as
before.

---

## Offline installer (ISO / USB)

The platform can be shipped as a self-contained **Windows installer ISO**: the media bundles the
application, every dependency as wheels, and the Python 3.12 runtime, so an air-gapped lab PC can
install and run everything with no internet and no prerequisites.

The installer (`packaging/setup/setup.bat` → `setup.ps1`) copies the app to
`%LOCALAPPDATA%\IndustrialAcademy`, installs bundled Python 3.12 silently if needed, creates a fresh
virtual environment from the bundled `wheels/`, builds the database + curriculum + offline bundles
(`python -m app.init_db`), and creates Desktop / Start Menu shortcuts. INSTALL.txt on the media has
the full runbook (firewall flag, scheduled-task autostart, production `.env`, uninstall).

### Build the ISO

Windows 10/11 ships the IMAPI2 filesystem API the builder uses, so no extra tools are required:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\Build-Iso.ps1
```

This produces `dist\Industrial-Academy-1.0.0-setup-x64.iso` (~40 MB) and stages the tree at
`dist\staging\Industrial-Academy-1.0.0`. Options: `-SkipIso` (stage only), `-NoWheelDownload`
(reuse cached wheels), `-ShowProgress`.

What ends up on the disc:

- `setup.bat` / `setup.ps1` + `start-academy.bat` / `stop-academy.bat` / `uninstall.ps1`
- `INSTALL.txt`, `AUTORUN.INF` (no auto-run — you always choose to install), `CHECKSUMS.txt`
- `app/` — backend + frontend (venv, tests, bundles and databases excluded)
- `docs/` — README, SECURITY, CURRICULUM, `.env.example`
- `wheels/` — every pinned dependency (built `--only-binary` for CPython 3.12, win_amd64)
- `python/python-3.12.10-amd64.exe` (silent per-user install; SHA256-verifiable)

The version string lives in `backend/app/config.py` (`app_version`) and drives both the ISO filename
and the recorded installer version. Rebuild the media any time the app or dated dependencies change.

---

## Windows desktop app + installer

For a native, browser-less experience the platform is also packaged as the **ASAPA Windows desktop
application** (`IndustrialAcademy.exe`): it starts the API on a random loopback port and hosts the
UI in a WebView2 window (no console, no separate browser tab). A per-user **Inno Setup installer**
wraps the whole bundle.

The desktop build ships without the optional hardware-integration libraries, so the admin
"Live integrations" view reports them as *disabled* and the app never binds the privileged Modbus
port 502. The app icon and installer icon use the ASAPA mark (assets generated by
`packaging/desktop/assets/make_icon.py`). All user data (SQLite database, curriculum, offline
bundles) is stored in `%LOCALAPPDATA%\IndustrialAcademy`, outside the install directory, and
survives re-installs and uninstalls.

### Enable the live AI mentor (internet)

Out of the box the desktop app uses the built-in Socratic mentor engine, which
works fully offline. To switch it to a live LLM whenever there is internet
access, edit `%LOCALAPPDATA%\IndustrialAcademy\config.env` (a template is
written there on first launch; see `packaging/desktop/config.env.example`) and
add:

```
AI_PROVIDER=openrouter
AI_API_KEY=sk-or-...
```

Other providers are supported (`openai`, `anthropic`, `gemini`, local
`ollama`, or any OpenAI-compatible endpoint via `AI_BASE_URL`). The app still
falls back to the deterministic engine on offline use or provider errors, and
safety-critical questions never reach the model. Real environment variables on
the machine take precedence over the file.

### Build the desktop bundle + installer

Requires a machine with Python 3.12 and internet on first run (PyInstaller + pywebview + Inno Setup
are fetched automatically; the rest can be reused across rebuilds):

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\desktop\build-desktop.ps1
```

This produces:

- `packaging/desktop/dist-desktop/IndustrialAcademy/` — the standalone app folder (run
  `IndustrialAcademy.exe` directly)
- `packaging/desktop/dist-desktop/ASAPA-Setup-1.0.0.exe` (~23 MB, per-user installer → Start Menu +
  Desktop shortcuts, uninstaller included, no admin required)

Options: `-SkipVenv` (reuse the `.build-venv`), `-SkipInstaller` (bundle only). `ISCC_PATH` can
point at an existing Inno Setup 6 compiler instead of the portable copy the script installs.

Headless verification (used by the build pipeline) runs the packaged app against a temp data dir:

```powershell
$env:INDUSTRIAL_ACADEMY_DATA = "$env:TEMP\ia-test"; $env:INDUSTRIAL_ACADEMY_SMOKE = "1"
$env:INDUSTRIAL_ACADEMY_SMOKE_FILE = "$env:TEMP\ia-test\smoke.json"
packaging\desktop\dist-desktop\IndustrialAcademy\IndustrialAcademy.exe
Get-Content "$env:TEMP\ia-test\smoke.json"
```

A launch log is appended to `%TEMP%\IndustrialAcademy-launch.log` on every start; failures there
report anything that went wrong before the window opened.

---

## API overview

All endpoints are prefixed with `/api`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register` · `POST /auth/token` · `POST /auth/refresh` · `GET /auth/me` |
| Projects | `GET /projects` · `GET /projects/{id}` · `GET /projects/{id}/sections/{key}` · `GET /projects/{id}/progress` · `GET /projects/{id}/schematic` (Student Pro+) · `POST /projects/generate` (Student Pro+) |
| Curriculum | `GET /curriculum` (foundations only) · `GET /curriculum/tracks` · `GET /curriculum/mining` · `GET /curriculum/projects/{slug}` · `POST /curriculum/install` (admin) |
| Faults | `GET /projects/{id}/faults` · `GET /projects/{id}/faults/{fault_id}` · `POST /fault/diagnose` |
| Mentor | `GET /mentor/status` · `POST /mentor/chat` · `POST /mentor/solution` |
| Progress | `GET /progress` · `POST /progress` |
| Devices | `POST /devices/authorize` · `GET /devices` · `POST /devices/revoke` · `POST /devices/{id}/touch` |
| Sync | `POST /sync` |
| Offline | `GET /offline/manifest` · `GET /projects/{id}/offline-bundle` · `POST /offline/rebuild` (admin) |
| Credentials | `GET /credentials/certificates` · `GET /credentials/portfolio` · `GET /credentials/certificates/verify/{token}` · `POST /credentials/portfolio/{entry_ref}/publish` · `POST /credentials/portfolio/{entry_ref}/unpublish` (Professional+) |
| Billing | `GET /billing/plans` · `GET /billing/status` · `GET /billing/licenses` · `POST /billing/checkout` · `POST /billing/activate` · `POST /billing/webhook` |
| Licensing | `GET /licensing/status` · `POST /licensing/register-hwid` · `POST /licensing/verify` |
| Integrations | `GET /integrations` · `POST /integrations/start\|stop\|snapshot` · **TIA**: `POST /integrations/tia/probe` · `POST /integrations/tia/validate-scl` · `POST /integrations/tia/import-tags` · `GET /integrations/tia/template.csv` |
| Orchestrator | `GET /orchestrator/status` · `GET /orchestrator/projects/{id}/workflow` · `POST /orchestrator/projects/{id}/advance` · `POST /orchestrator/projects/{id}/regress` · `POST /orchestrator/tools/{tia\|wincc\|factoryio}/launch` (admin) |
| Activity | `GET /activity` (admin sees all users) |
| Stats | `GET /stats/learner` (dashboard rollups, streaks, 14-day activity) · `GET /stats/admin` (admin platform analytics) |
| Portfolio | `GET /portfolio/{entry_ref}` (public HTML share page) |
| Health | `GET /health` |

The fault-detail endpoint deliberately omits the expected checks and correct diagnosis; those are
only revealed by `POST /fault/diagnose` after a learner submits an attempt.

Plan gates are enforced with `403` (upgrade detail) for Sandbox users and `402` (budget exhausted)
when the daily fault-diagnosis cap is reached; see `app/plans.py`.

---

## The 17-section lifecycle

`project_brief` · `process_description` · `p_and_id` · `io_list` · `tag_list` ·
`control_philosophy` · `plc_program` · `hmi` · `scada` · `alarms` · `interlocks` · `networking` ·
`testing` · `fault_injection` · `troubleshooting` · `commissioning` · `final_documentation`

## Seeded fault scenarios

Water treatment: `dosing-pump-overrun` · `filter-bed-blinding` · `magflow-failed-low` ·
`level-loop-open` · `chlorine-airlock` · `pump-permissive-blocked` · `backwash-valve-feedback` ·
`comms-loss-scada`

Mining (Minerals primary crushing): `belt-misalignment-at-tonnage` · `crusher-feed-choke` ·
`tramp-metal-false-trip` · `feeder-never-commands`

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

### TIA Openness bridge (Professional+)

`TIA_OPENNESS_ENABLED=1`, `TIA_OPENNESS_HOST=127.0.0.1`, `TIA_OPENNESS_PORT=8600`. The bridge exposes:

- `POST /api/integrations/tia/probe` — version/host availability probe.
- `POST /api/integrations/tia/validate-scl` — pre-compile SCL static validation (structured control
  balance, block framing, operand/assignability rules) with a 0–100 score.
- `POST /api/integrations/tia/import-tags` — IEC 61131-3 tag CSV validation against the I/Q/M/DB
  address contract.
- `GET /api/integrations/tia/template.csv` — the expected tag-import template.

Without a licensed TIA Portal host on the machine the probe reports *not available* and both
validators run rule-based offline (no degradation of the rest of the platform). All three endpoints
require Professional+ (admin always passes).

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
.\.venv\Scripts\python.exe tests\curriculum_test.py    # 35 authored-curriculum content checks
.\.venv\Scripts\python.exe tests\stats_test.py         # 33 learner + admin analytics checks
.\.venv\Scripts\python.exe tests\security_test.py     # headers, CSP, CORS, rate-limit checks
.\.venv\Scripts\python.exe tests\billing_test.py      # 24 plans/checkout/webhook/license checks
.\.venv\Scripts\python.exe tests\licensing_test.py    # 18 HWID + offline-token checks
.\.venv\Scripts\python.exe tests\blueprint_test.py     # 29 tracks/mining/schematic/TIA/portfolio checks
.\.venv\Scripts\python.exe tests\ai_test.py            # 15 LLM-gateway fallback/contract checks
.\.venv\Scripts\python.exe tests\orchestrator_test.py  # 18 Engineering Desk pipeline + toolchain checks
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

### Hosted on Render (free)

The repo ships a `render.yaml` blueprint, so the platform comes up online with
a public HTTPS URL without managing your own server:

1. Sign in to [render.com](https://render.com) (free tier is enough).
2. **New → Blueprint**, select the `triller03/industrial-academy` repo, and
   press *Apply*. Render builds the `Dockerfile`, attaches a 1 GB persistent
   disk at `/app/data` for the SQLite DB + offline bundles, and auto-generates
   `SECRET_KEY` (stored encrypted, never committed).
3. The service auto-deploys on every push to `main`; the full 13-suite gate
   runs first in GitHub Actions.

Hardening the hosted instance is the same list as above — `ENVIRONMENT=production`
and `REQUIRE_HTTPS=1` are already set, and secure-by-default choices are baked in
(`CORS_ORIGINS` empty = same-origin SPA only, `MODBUS_PORT=1502` so the non-root
container user can bind the simulated-plant bridge). After first deploy:

- open `<your-app>.onrender.com/api/health` (should return `"status":"ok"`);
- set `INTERFACE_ORIGIN=https://<your-app>.onrender.com` so published portfolio
  links point at your real origin;
- set `SEED_ON_STARTUP=0` once you no longer want the well-known demo accounts
  (`demo@academy.local`, `admin@academy.local`) on a public instance.

> Render's free tier sleeps the service after ~15 min of inactivity and wakes it
> on the next request (first load after idle is slower). Use the `Starter` plan
> for always-on.

CI smoke-tests every PR; the full 13-suite gate runs on `main`.

## Security

Baseline hardening ships in `backend/app/middleware.py` and is verified by
`tests/security_test.py`:

| Control | Detail |
| --- | --- |
| Response headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` |
| CSP (SPA) | `default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'` |
| Auth rate limiting | Per-IP sliding window, bucketed per auth endpoint (login/refresh), so one abused endpoint can't lock a user out of another |
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
