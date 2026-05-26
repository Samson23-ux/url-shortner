import httpx
import pytest


pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestGetAnalytics:
    async def test_get_user_analytics(self, async_client: httpx.AsyncClient, login: httpx.Response, shorten_url: httpx.Response):
        access_token = login.json()["access_token"]

        res = await async_client.get(
            "/analytics",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"}
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["total_urls"] >= 1
        assert json_res["data"]["recently_created_urls"][0] == "fake_long_url"

    async def test_get_user_click_analytics(self, async_client: httpx.AsyncClient, login: httpx.Response, shorten_url: httpx.Response):
        access_token = login.json()["access_token"]

        shortened_url: str = shorten_url.json()["data"]["shortened_url"]

        await async_client.get(
            f"/shorten/{shortened_url}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        res = await async_client.get(
            "/analytics",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"}
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["total_clicks"] >= 1
        assert json_res["data"]["most_clicked_url"] == "fake_long_url"
