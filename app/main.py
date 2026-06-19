"""
FastAPI application factory — AI Project Audit Platform.
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.security import hash_password

settings = get_settings()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the app begins serving requests."""
    logger.info("🚀 Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # 1. Create tables
    init_db()
    logger.info("✅ Database tables created / verified")

    # 2. Seed admin user
    _seed_admin_user()

    yield

    logger.info("🛑 Shutting down %s", settings.APP_NAME)


def _seed_admin_user() -> None:
    """Create the admin user from .env if it doesn't already exist."""
    db = SessionLocal()
    try:
        user_repo = UserRepository(db)
        existing = user_repo.get_by_email(settings.ADMIN_EMAIL)
        if existing:
            logger.info("ℹ️  Admin user already exists: %s", settings.ADMIN_EMAIL)
            return

        admin = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            full_name="Platform Admin",
            is_admin=True,
            is_active=True,
        )
        user_repo.create(admin)
        logger.info("✅ Admin user seeded: %s", settings.ADMIN_EMAIL)
    finally:
        db.close()


# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready backend for an AI-powered Project Audit Platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique X-Request-ID header to every response."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handler ────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler to prevent leaking internal errors."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Register routers ────────────────────────────────────────────────────────
from app.routers import auth, users, projects, reports, audit_runs, prd_analysis, github_analysis  # noqa: E402

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(reports.router)
app.include_router(audit_runs.router)
app.include_router(prd_analysis.router)
app.include_router(github_analysis.router)



# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    """Simple health-check endpoint."""
    return {"status": "healthy", "version": settings.APP_VERSION}
