"""
Database engine, session factory, and declarative base.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── Engine ───────────────────────────────────────────────────────────────────
# Build engine configuration based on the database backend.
connect_args = {}
engine_kwargs = {
    "echo": settings.DEBUG,
}

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite needs check_same_thread=False for FastAPI's async request handling.
    connect_args["check_same_thread"] = False
else:
    # PostgreSQL connection pool configuration for production use.
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    })

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys for SQLite connections (no-op for PostgreSQL)."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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

    # Legacy SQLite migrations for existing databases.
    # These are no-ops for PostgreSQL since the schema is managed by Alembic.
    if settings.DATABASE_URL.startswith("sqlite"):
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
                if "auth_required" not in columns:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN auth_required BOOLEAN DEFAULT 0"))
                    conn.commit()
                if "login_url" not in columns:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN login_url VARCHAR(512)"))
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
