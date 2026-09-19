from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api import (
    activity_router,
    auth_router,
    credentials_router,
    devices_router,
    fault_router,
    integrations_router,
    mentor_router,
    offline_router,
    progress_router,
    projects_router,
    sync_router,
)
from app.config import get_settings
from app.database import Base, engine
from app.integrations.manager import IntegrationManager
from app.middleware import HttpsEnforceMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.offline import ensure_bundles
from app.seeder import seed_if_empty

settings = get_settings()

ROOT = Path(__file__).resolve().parent.parent
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        seed_if_empty()
    with Session(engine) as session:
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
):
    app.include_router(router, prefix=settings.api_prefix)


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