"""
Database engine, session factory, and declarative base.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── Engine ───────────────────────────────────────────────────────────────────
# SQLite needs check_same_thread=False for FastAPI's async request handling.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

# ── Session ──────────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Base ─────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def init_db() -> None:
    """Create all tables (idempotent)."""
    # Import models so they are registered on Base.metadata before create_all.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # SQLite migrations for existing databases
    from sqlalchemy import text
    with engine.connect() as conn:
        # Update projects table
        try:
            res = conn.execute(text("PRAGMA table_info(projects)")).fetchall()
            columns = [r[1] for r in res]
            if "prd_url" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN prd_url VARCHAR(512)"))
                conn.commit()
            if "deployment_url" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN deployment_url VARCHAR(512)"))
                conn.commit()
            if "rbac_enabled" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN rbac_enabled BOOLEAN DEFAULT 0"))
                conn.commit()
            if "admin_url" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN admin_url VARCHAR(512)"))
                conn.commit()
            if "user_url" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN user_url VARCHAR(512)"))
                conn.commit()
            if "secret_reference" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN secret_reference VARCHAR(512)"))
                conn.commit()
        except Exception:
            pass


        # Update users table
        try:
            res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            columns = [r[1] for r in res]
            if "company_name" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN company_name VARCHAR(255)"))
                conn.commit()
        except Exception:
            pass
