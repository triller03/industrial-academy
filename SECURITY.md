# Security

The ASAPA platform (formerly the AI-Powered Industrial Academy) is hardened for self-hosting behind a
TLS-terminating reverse proxy. This file summarises the threat stance, the built-in
controls and the deployment checklist.

## Reporting a vulnerability

This project is an educational deployment for industrial trainees. If you find
a real vulnerability: **do not disclose it in public issues** — open a private
report on the repository, or reach out to the maintainer directly, and include
reproduction steps plus the affected version.

## Threat model

The platform ships offline-first to shop-floor networks and is typically exposed
only via a reverse proxy. The control scope of hardening is:

- **Credential abuse** — /api/auth/* is rate-limited per client IP; accounts can
  be disabled server-side; refresh tokens single-use.
- **Spoofed origins** — CORS is allow-list configurable; the SPA is served with
  a strict Content-Security-Policy.
- **Information disclosure** — production builds disable `/docs`, `/redoc` and
  the OpenAPI schema; error details for failed logins are generic; audit-trail
  endpoints only expose cross-user activity to admins.
- **Misconfiguration** — the production guard refuses to boot with the default
  `SECRET_KEY`; `REQUIRE_HTTPS` rejects plain-http clients.
- **Licensing & entitlement abuse** — paid-tier features are gated server-side
  (`app/plans.py`) and never by the client; HWID licensing binds a user to a
  limited set of devices; offline license tokens are signed and HMAC-verified;
  license keys are single-use and revocable; billing webhooks verify gateway
  signatures before activating an order.
- **Budget abuse** — the free Sandbox tier caps online fault diagnoses per day
  (`5`); the offline-sync path counts into the same bucket so a client cannot
  bypass the cap by going offline and re-syncing.
- **Legal mislabelling** — offline bundles strip mentor/fault answer keys; the
  bundle build is admin-only.

## Built-in controls

| Area | Control | Verified by |
| --- | --- | --- |
| Headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` | `tests/security_test.py` |
| CSP (SPA) | `default-src 'self'`, `script-src 'self'`, `style-src 'self' 'unsafe-inline'`, `img-src 'self' data:`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'` | `tests/security_test.py` |
| Rate limiting | Per-IP sliding window, bucketed per auth endpoint (default 60/min each) + global `/api/*` budget (600/min) | `tests/security_test.py` |
| Auth | Generic 401, min 8-char passwords at registration, account disable flag | `tests/security_test.py`, `smoke_test.py` |
| Tokens | Short-lived JWT access + rotating single-use refresh tokens | `tests/refresh_test.py` |
| Admin-only | Offline-bundle rebuild, integration link start/stop/snapshot, cross-user activity, curriculum install remain admin-gated (`403` otherwise) | `tests/admin_test.py`, `tests/integration_test.py`, `tests/curriculum_test.py` |
| AuthZ | Student Pro+: project generation + FRS/P&ID schematic viewer; Professional+: portfolio publish + TIA bridge; admin always passes. `403` with upgrade detail otherwise | `tests/billing_test.py`, `tests/blueprint_test.py` |
| Budget | Sandbox daily fault-diagnosis cap (5/day, online + offline-sync counted); over cap → `402` | `tests/smoke_test.py`, `tests/offline_test.py`, `sync/manager` |
| Licensing | HWID device binding (limit 3), signed offline tokens, key redemption + revocation, gateway webhook signature checks | `tests/licensing_test.py`, `tests/billing_test.py` |
| Production guard | Boot-time `SECRET_KEY` check; docs/OpenAPI disabled in `production` | startup (documented) |
| HTTPS | `REQUIRE_HTTPS=1` → `426` without `X-Forwarded-Proto: https` | startup (documented) |

## Deployment checklist

1. `cp .env.example .env` and generate a real key:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Set `ENVIRONMENT=production`, `CORS_ORIGINS` to your frontend origin(s) only.
3. Terminate TLS at your reverse proxy, set `REQUIRE_HTTPS=1`, and forward
   `X-Forwarded-For`/`X-Forwarded-Proto` from trusted upstreams only.
4. Remove or disable the seeded `demo@`/`admin@academy.local` accounts before
   real users join, or set `SEED_ON_STARTUP=false` on a fresh database.
5. Scope: `/api/health` and `/` (SPA) may be public; everything under `/api/*`
   besides health requires a token.

## Industrial safety

The plant failsafe is a **teaching simulation only**. It exercises e-stop
deglitching, motion freeze, lamp clearance and interlock audit events, but it is
not a safety-rated control — deploy against real machines only with certified
hardware safety circuits.

## Dependencies

Pinned in `requirements.txt` / `requirements-integrations.txt`; CI installs and
smoke-tests the exact same pins. Review updates before bumping either file.