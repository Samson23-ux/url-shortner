import httpx
import pytest
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession


from datetime import date
from app.api.models.url_stat import UrlStat


async def create_test_url_stat(session: AsyncSession, url_stat: UrlStat):
    session.add(url_stat)
    await session.commit()


class TestGetAnalytics:
    @pytest.mark.asyncio
    async def test_get_user_analytics(
        self,
        async_client: httpx.AsyncClient,
        login: httpx.Response,
        shorten_url: httpx.Response,
        async_session: AsyncSession,
    ):
        access_token = login.json()["data"]["access_token"]

        url_id: str = shorten_url.json()["data"]["id"]
        url_stat: UrlStat = UrlStat(url_id=UUID(url_id), date=date.today())

        await create_test_url_stat(async_session, url_stat)

        res = await async_client.get(
            "/analytics",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["total_urls"] >= 1

    @pytest.mark.asyncio
    async def test_get_user_click_analytics(
        self,
        async_client: httpx.AsyncClient,
        login: httpx.Response,
        shorten_url: httpx.Response,
        async_session: AsyncSession,
    ):
        access_token = login.json()["data"]["access_token"]

        url_id: str = shorten_url.json()["data"]["id"]
        url_stat: UrlStat = UrlStat(url_id=UUID(url_id), clicks=20, date=date.today())

        await create_test_url_stat(async_session, url_stat)

        res = await async_client.get(
            "/analytics",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["total_clicks"] >= 1
        assert json_res["data"]["most_clicked_url"]
