import pytest_asyncio
from uuid import uuid7
from sqlalchemy.pool import NullPool
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport, Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncConnection,
    AsyncTransaction,
)


from app.main import app
from app.api.models.otp import Otp
from app.api.models.base import Base
from app.core.config import get_settings
from app.api import models  # noqa: F401
from app.dependencies import get_session


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    async_db_engine: AsyncEngine = create_async_engine(
        url=get_settings().ASYNC_TEST_DB_URL, poolclass=NullPool
    )

    async with async_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_db_engine

    async with async_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await async_db_engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine: AsyncEngine):
    async_connection: AsyncConnection = await async_engine.connect()
    async_transaction: AsyncTransaction = await async_connection.begin()

    session = async_sessionmaker(
        bind=async_connection,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async_session: AsyncSession = session()
    yield async_session

    await async_session.close()
    await async_transaction.rollback()
    await async_connection.close()


@pytest_asyncio.fixture
async def async_client(async_session: AsyncSession):
    async def get_test_session():
        return async_session

    app.dependency_overrides[get_session] = get_test_session

    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://localhost/api/v1"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def create_user(async_client: AsyncClient):
    path: str = "app.api.services.auth_service.send_email.delay"

    sign_up_payload: dict = {
        "email": "user@example.com",
        "password": "test_user_password",
    }

    with patch(path, new_callable=AsyncMock) as email_patch:
        res: Response = await async_client.post(
            "/auth/signup",
            json=sign_up_payload,
            headers={"env": "test"},
        )

    email_patch.assert_called_once()

    return res


@pytest_asyncio.fixture
async def verify_user(async_client: AsyncClient, create_user: Response):
    otp_path: str = "app.api.services.auth_service._otp_repo.get_record"
    update_path: str = "app.api.services.auth_service._otp_repo.add"

    fake_otp: Otp = Otp(
        id=uuid7(),
        otp="test_otp_token",
        user_id=uuid7(),
        purpose="email_signup",
        status="valid",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
    )

    otp_payload: dict = {
        "email": "user@example.com",
        "otp_token": "test_otp_token",
        "password": "new_test_user_password"
    }

    with (
        patch(otp_path, new_callable=AsyncMock) as otp_patch,
        patch(update_path, new_callable=AsyncMock) as update_patch
    ):
        otp_patch.return_value = fake_otp

        res: Response = await async_client.post(
            "/auth/verify",
            json=otp_payload,
            headers={"env": "test"},
        )

    otp_patch.assert_awaited_once()
    update_patch.assert_awaited_once()

    return res

@pytest_asyncio.fixture
async def login(async_client: AsyncClient, verify_user: Response):
    login_payload: dict = {
        "username": "user@example.com",
        "password": "test_user_password",
    }

    res: Response = await async_client.post(
        "/auth/login",
        json=login_payload,
        headers={"env": "test"},
    )

    return res


@pytest_asyncio.fixture
async def shorten_url(async_client: AsyncClient, login: Response):
    access_token = login.json()["access_token"]

    url_create_payload: dict = {
        "original_url": "fake_long_url",
    }

    res = await async_client.post(
        "/shorten",
        json=url_create_payload,
        headers={"Authorization": f"Bearer {access_token}", "env": "test"},
    )

    return res


@pytest_asyncio.fixture
async def create_slug(async_client: AsyncClient, login: Response):
    access_token = login.json()["access_token"]

    slug_create_payload: dict = {
        "custom_slug": "test-slug",
    }

    res = await async_client.post(
        "/slugs",
        json=slug_create_payload,
        headers={"Authorization": f"Bearer {access_token}", "env": "test"},
    )

    return res
