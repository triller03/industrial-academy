from contextlib import asynccontextmanager
import sys
from html import escape as escape_html
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api import (
    activity_router,
    auth_router,
    billing_router,
    credentials_router,
    curriculum_router,
    devices_router,
    fault_router,
    integrations_router,
    licensing_router,
    mentor_router,
    offline_router,
    orchestrator_router,
    progress_router,
    projects_router,
    stats_router,
    sync_router,
)
from app.config import get_settings
from app.content.curriculum import install_curriculum
from app.content.mining_track import install_mining_track
from app.database import Base, SessionLocal, engine, ensure_schema
from app.integrations.manager import IntegrationManager
from app.middleware import HttpsEnforceMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.models import PortfolioEntry, User
from app.offline import ensure_bundles
from app.seeder import seed_if_empty

settings = get_settings()

ROOT = Path(__file__).resolve().parent.parent
# PyInstaller onedir bundles ship the static frontend under _internal/frontend:
# honour sys._MEIPASS when present, otherwise fall back to the repo layout.
FRONTEND_DIR = Path(getattr(sys, "_MEIPASS", ROOT.parent)) / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = ROOT.parent / "frontend"


def _guard_production_settings() -> None:
    """Fail fast on deployment foot-guns instead of serving degraded."""
    if settings.environment != "production":
        return
    if settings.secret_key == "change-me-in-production":
        raise RuntimeError(
            "SECRET_KEY is still the insecure default. Generate one and export it: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )


_guard_production_settings()


PORTFOLIO_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@ — Portfolio | @@ORIGIN@@</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; background: #f2f4f8; color: #1c2431; }
  header { background: #0b1220; color: #fff; padding: 22px 28px; }
  header h1 { margin: 0; font-size: 22px; font-weight: 700; }
  header p { margin: 6px 0 0; color: #9fb0c7; font-size: 13px; }
  main { max-width: 760px; margin: 26px auto; padding: 0 20px; }
  .card { background: #fff; border: 1px solid #dbe1ea; border-radius: 12px; padding: 26px 28px; box-shadow: 0 1px 3px rgba(16,24,40,.06); }
  .owner { font-size: 13px; color: #566174; letter-spacing: .02em; text-transform: uppercase; }
  .ref { margin-top: 18px; font-size: 12px; color: #98a2b3; }
  footer { text-align: center; color: #98a2b3; font-size: 12px; padding: 26px 0 40px; }
  .badge { display: inline-block; background: #eef2ff; color: #4338ca; border-radius: 999px; font-size: 12px; padding: 4px 12px; margin-bottom: 12px; }
  pre { white-space: pre-wrap; font-family: inherit; }
</style>
</head>
<body>
<header>
  <h1>@@TITLE@@</h1>
  <p>Industrial automation engineering work sample</p>
</header>
<main>
  <div class="card">
    <span class="badge">ASAPA Project Work Sample</span>
    <div class="owner">By @@OWNER@@</div>
    <pre>@@SUMMARY@@</pre>
    <div class="ref">Entry ref: @@REF@@ · Verified on @@ORIGIN@@</div>
  </div>
</main>
<footer>Powered by @@ORIGIN@@</footer>
</body>
</html>
"""

PORTFOLIO_NOT_FOUND = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Not found</title></head>
<body style="font-family:sans-serif;background:#f2f4f8;padding:60px 24px;color:#1c2431">
  <h1>Portfolio entry not found</h1>
  <p>The entry is unpublished or the reference is wrong. Contact the author for a current link.</p>
</body></html>
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    if settings.seed_on_startup:
        seed_if_empty()
    with Session(engine) as session:
        created = install_curriculum(session)
        if created:
            print(f"  [curriculum] installed {len(created)} projects: {', '.join(created)}")
        mining_created = install_mining_track(session)
        if mining_created:
            print(f"  [mining-track] installed {len(mining_created)} projects: {', '.join(mining_created)}")
        ensure_bundles(session)
    manager = IntegrationManager(settings)
    manager.start()
    app.state.integrations = manager
    yield
    manager.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)

cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, settings=settings)
app.add_middleware(HttpsEnforceMiddleware, settings=settings)
app.add_middleware(SecurityHeadersMiddleware)

for router in (
    auth_router,
    projects_router,
    mentor_router,
    fault_router,
    progress_router,
    devices_router,
    sync_router,
    credentials_router,
    offline_router,
activity_router,
        integrations_router,
        curriculum_router,
        stats_router,
        licensing_router,
        billing_router,
        orchestrator_router,
    ):
        app.include_router(router, prefix=settings.api_prefix)


@app.get("/portfolio/{entry_ref}", response_class=HTMLResponse)
def public_portfolio(entry_ref: str):
    """Shareable public work-sample page (Professional+ published entries only)."""
    db = SessionLocal()
    try:
        entry = (
            db.query(PortfolioEntry)
            .filter(
                PortfolioEntry.entry_ref == entry_ref,
                PortfolioEntry.published.is_(True),
            )
            .first()
        )
        if not entry:
            return HTMLResponse(PORTFOLIO_NOT_FOUND, status_code=404)
        owner = db.query(User).filter(User.id == entry.user_id).first()
        owner_name = owner.full_name if owner else "Anonymous"
        page = (
            PORTFOLIO_TEMPLATE
            .replace("@@TITLE@@", escape_html(entry.title))
            .replace("@@ORIGIN@@", settings.app_name)
            .replace("@@OWNER@@", escape_html(owner_name))
            .replace("@@SUMMARY@@", escape_html(entry.summary or ""))
            .replace("@@REF@@", entry.entry_ref)
        )
        return HTMLResponse(page)
    finally:
        db.close()


@app.get(f"{settings.api_prefix}/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")