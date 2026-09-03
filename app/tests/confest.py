
"""
Shared pytest fixtures — async DB, test client, seeded users.

Requires:
    pip install pytest pytest-asyncio httpx
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.core.security import hash_secret
from app.core.service_registry import seed_services
from app.database import Base, get_async_session
from app.main import app
from app.models.client_profile import ClientProfile
from app.models.role import Role, RoleName
from app.models.user import AuthMethod, User

settings = get_settings()

TEST_DB_URL = settings.database_url.replace(
    "/isp_ticketing", "/isp_ticketing_test"
)

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, expire_on_commit=False)


# ── Event loop ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── DB setup / teardown ─────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as db:
        await seed_services(db)
        await _seed_roles(db)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session
        await session.rollback()


# ── Override DB dependency ───────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def override_db():
    async def _override():
        async with TestSession() as session:
            yield session
            await session.rollback()

    app.dependency_overrides[get_async_session] = _override
    yield
    app.dependency_overrides.clear()


# ── Async HTTP client ───────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


# ── Seed roles ───────────────────────────────────────────────────

async def _seed_roles(db: AsyncSession):
    for name in (
        RoleName.CLIENT,
        RoleName.MANAGER,
        RoleName.SUPER_ADMIN,
    ):
        db.add(Role(name=name))
    await db.commit()


# ── Test users ───────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client_user(db: AsyncSession) -> User:
    from sqlalchemy import select

    role = await db.execute(
        select(Role).where(Role.name == RoleName.CLIENT)
    )
    role_id = role.scalar_one().id

    user = User(
        email="client@test.com",
        role_id=role_id,
        auth_method=AuthMethod.GOOGLE,
        google_sub="google-test-sub-123",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    db.add(ClientProfile(
        user_id=user.id,
        full_name="Test Client",
        phone="+254700000000",
        connection_area="Nairobi CBD",
    ))
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def manager_user(db: AsyncSession) -> User:
    from sqlalchemy import select

    role = await db.execute(
        select(Role).where(Role.name == RoleName.MANAGER)
    )
    role_id = role.scalar_one().id

    user = User(
        email="manager@test.com",
        role_id=role_id,
        auth_method=AuthMethod.CREDENTIALS,
        pin_hash=hash_secret("1234"),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    from sqlalchemy import select

    role = await db.execute(
        select(Role).where(Role.name == RoleName.SUPER_ADMIN)
    )
    role_id = role.scalar_one().id

    user = User(
        email="admin@test.com",
        role_id=role_id,
        auth_method=AuthMethod.CREDENTIALS,
        pin_hash=hash_secret("9999"),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── Auth headers ─────────────────────────────────────────────────

def _make_token(user: User, role_name: str) -> str:
    from app.core.security import (
        AuthAudience,
        TokenType,
        create_token,
    )

    audience = (
        AuthAudience.CLIENT
        if role_name == RoleName.CLIENT
        else AuthAudience.ADMIN
    )
    token, _ = create_token(
        str(user.id), role_name, audience, TokenType.ACCESS
    )
    return token


@pytest.fixture
def client_headers(client_user: User) -> dict:
    token = _make_token(client_user, RoleName.CLIENT)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_headers(manager_user: User) -> dict:
    token = _make_token(manager_user, RoleName.MANAGER)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    token = _make_token(admin_user, RoleName.SUPER_ADMIN)
    return {"Authorization": f"Bearer {token}"}

