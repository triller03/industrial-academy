"""First-run initialiser used by the offline installer (python -m app.init_db).

Affectionately mirrors what the server lifespan does on boot, so an install
can pre-build everything (DB + seed accounts + curriculum + mining track +
offline bundles) before the first real start. Idempotent.
"""
from sqlalchemy.orm import Session

from app.content.curriculum import install_curriculum
from app.content.mining_track import install_mining_track
from app.database import Base, engine, ensure_schema
from app.offline import ensure_bundles
from app.seeder import seed_if_empty


def init_db() -> dict:
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    seed_if_empty()
    with Session(engine) as session:
        created = install_curriculum(session)
        mining_created = install_mining_track(session)
        bundles_written = ensure_bundles(session)
    return {
        "curriculum_created": created,
        "mining_created": mining_created,
        "bundles_written": bundles_written,
    }


if __name__ == "__main__":
    summary = init_db()
    print(
        "[init] DB ready — curriculum created: {}, mining created: {}, offline bundles written: {}".format(
            ", ".join(summary["curriculum_created"]) if summary["curriculum_created"] else "none (already present)",
            ", ".join(summary["mining_created"]) if summary["mining_created"] else "none (already present)",
            summary["bundles_written"],
        )
    )