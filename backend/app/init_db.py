"""First-run initialiser used by the offline installer (python -m app.init_db).

Affectionately mirrors what the server lifespan does on boot, so an install
can pre-build everything (DB + seed accounts + curriculum + offline bundles)
before the first real start. Idempotent.
"""
from sqlalchemy.orm import Session

from app.content.curriculum import install_curriculum
from app.database import Base, engine
from app.offline import ensure_bundles
from app.seeder import seed_if_empty


def init_db() -> dict:
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    with Session(engine) as session:
        created = install_curriculum(session)
        bundles_written = ensure_bundles(session)
    return {
        "curriculum_created": created,
        "bundles_written": bundles_written,
    }


if __name__ == "__main__":
    summary = init_db()
    print(
        "[init] DB ready — curriculum created: {}, offline bundles written: {}".format(
            ", ".join(summary["curriculum_created"]) if summary["curriculum_created"] else "none (already present)",
            summary["bundles_written"],
        )
    )