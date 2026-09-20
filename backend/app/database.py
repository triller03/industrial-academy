from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_schema(engine) -> None:
    """Idempotent lightweight migration for SQLite deployments.

    create_all() adds new *tables* but never alters existing ones. Additive
    columns needed by running installs are applied here so an upgrade does not
    force a DB wipe. Mirrors the preferred column definitions below.
    """
    if not engine.dialect.name == "sqlite":
        return
    with engine.begin() as conn:
        user_cols = {c[1] for c in conn.exec_driver_sql("PRAGMA table_info(users)")}
        if "plan" not in user_cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN plan VARCHAR(32) NOT NULL DEFAULT 'sandbox'"
            )
        portfolio_cols = {c[1] for c in conn.exec_driver_sql("PRAGMA table_info(portfolio_entries)")}
        if "published" not in portfolio_cols:
            conn.exec_driver_sql(
                "ALTER TABLE portfolio_entries ADD COLUMN published BOOLEAN NOT NULL DEFAULT 0"
            )
        if "published_at" not in portfolio_cols:
            conn.exec_driver_sql(
                "ALTER TABLE portfolio_entries ADD COLUMN published_at DATETIME NULL"
            )
        project_cols = {c[1] for c in conn.exec_driver_sql("PRAGMA table_info(projects)")}
        if "orchestration_stage" not in project_cols:
            conn.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN orchestration_stage INTEGER NOT NULL DEFAULT 0"
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()