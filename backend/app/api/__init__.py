from app.api.routes_activity import router as activity_router
from app.api.routes_auth import router as auth_router
from app.api.routes_credentials import router as credentials_router
from app.api.routes_curriculum import router as curriculum_router
from app.api.routes_devices import router as devices_router
from app.api.routes_fault import router as fault_router
from app.api.routes_integrations import router as integrations_router
from app.api.routes_mentor import router as mentor_router
from app.api.routes_progress import router as progress_router
from app.api.routes_offline import router as offline_router
from app.api.routes_projects import router as projects_router
from app.api.routes_sync import router as sync_router

__all__ = [
    "activity_router",
    "auth_router",
    "credentials_router",
    "curriculum_router",
    "devices_router",
    "fault_router",
    "integrations_router",
    "mentor_router",
    "offline_router",
    "progress_router",
    "projects_router",
    "sync_router",
]