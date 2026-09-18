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
from app.offline import ensure_bundles
from app.seeder import seed_if_empty

settings = get_settings()

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT.parent / "frontend"


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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")