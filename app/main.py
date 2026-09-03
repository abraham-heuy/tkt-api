
"""
ISP Network Ticketing System — main application entry point.

Run:
    uvicorn app.main:app --reload
"""
import ssl
import certifi

_original_create_default_context = ssl.create_default_context

def _patched_create_default_context(*args, **kwargs):
    # Force use of certifi's CA bundle for every SSL context
    kwargs['cafile'] = certifi.where()
    return _original_create_default_context(*args, **kwargs)

ssl.create_default_context = _patched_create_default_context
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.core.service_registry import seed_services
from app.database import AsyncSessionLocal
from app.api.v1 import all_routers

settings = get_settings()


# ── OpenAPI tags ─────────────────────────────────────────────────

TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Liveness and readiness probes",
    },
    {
        "name": "Auth",
        "description": (
            "Google OAuth (clients) and email+PIN login "
            "(managers/superadmin)"
        ),
    },
    {
        "name": "Users",
        "description": (
            "User management — KYC, profiles, account lifecycle"
        ),
    },
    {
        "name": "Profile",
        "description": "Client self-service profile (GET /profile/me)",
    },
    {
        "name": "Tickets",
        "description": (
            "Ticket CRUD — create, track, transition, assign"
        ),
    },
    {
        "name": "Notifications",
        "description": (
            "In-app notifications + Web Push subscription management"
        ),
    },
    {
        "name": "Permissions",
        "description": (
            "IAM-style service groups, action groups, "
            "and manager permission grants"
        ),
    },
    {
        "name": "Analytics",
        "description": (
            "Dashboard stats, ticket trends, resolution metrics, "
            "agent performance"
        ),
    },
]


# ── Lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed service groups + action groups on startup."""
    async with AsyncSessionLocal() as db:
        summary = await seed_services(db)
        seeded = {k: v for k, v in summary.items() if v}
        if seeded:
            print(f"🔧 Seeded services: {seeded}")
        else:
            print("✅ Service registry up to date")
    yield


# ── App ──────────────────────────────────────────────────────────

app = FastAPI(
    title="ISP Network Ticketing System",
    version="1.0.0",
    description=(
        "Standalone ticketing system for ISP network "
        "issue management and customer support"
    ),
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware stack (order matters — outermost first) ───────────

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
    ],
    expose_headers=["X-Total-Count"],
    max_age=600,
)


# ── Health / liveness ────────────────────────────────────────────

@app.get("/", tags=["Health"], status_code=200)
async def root():
    """Instant 200 — load balancer / uptime probe."""
    return {"status": "ok"}


@app.get("/health", tags=["Health"], status_code=200)
async def health():
    """Readiness check — confirms the app is alive."""
    return {"status": "healthy", "version": "1.0.0"}


# ── Register all routers (single loop) ──────────────────────────

for prefix, router, tags in all_routers:
    app.include_router(router, prefix=prefix, tags=tags)

