import httpx
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestShortenUrl:
    async def test_shorten_url(
        self, shorten_url: httpx.Response
    ):
        json_res = shorten_url.json()

        assert shorten_url.status_code == 201
        assert json_res["data"]

    async def test_shorten_url_exists(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        url_create_payload: dict = {
            "original_url": "fake_long_url",
        }

        res = await async_client.post(
            "/shorten",
            json=url_create_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 409

    async def test_shorten_url_with_slug(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["access_token"]

        url_create_payload: dict = {
            "original_url": "fake_long_url",
            "slug": "test-custom-slug",
        }

        res = await async_client.post(
            "/shorten",
            json=url_create_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        code_split: list[str] = json_res["data"]["shortened_url"].split()

        assert res.status_code == 201
        assert "test-custom-slug" in code_split

    async def test_shorten_url_invalid_slug(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["access_token"]

        url_create_payload: dict = {
            "original_url": "fake_long_url",
            "slug": "$test-custom-slug::::",
        }

        res = await async_client.post(
            "/shorten",
            json=url_create_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 400


class TestGetUrl:
    async def test_redirect_to_url(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        shortened_url: str = shorten_url.json()["data"]["shortened_url"]

        res = await async_client.get(
            f"/shorten/{shortened_url}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 302

    async def test_invalid_shortened_url(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        res = await async_client.get(
            "/shorten/shortened_url",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

    async def get_all_urls(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        res = await async_client.get(
            "/shorten/all",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert len(json_res["data"]) >= 1


class TestUpdateUrl:
    async def test_update_url(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]
        shortened_url: str = shorten_url.json()["data"]["shortened_url"]

        update_payload: dict = {
            "old_original_url": shortened_url,
            "new_original_url": "new_test_original_url",
        }

        res = await async_client.patch(
            f"/shorten/{shortened_url}",
            json=update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert shortened_url == json_res["data"]["shortened_url"]

    async def test_update_invalid_url(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        update_payload: dict = {"new_original_url": "new_test_long_url"}

        res = await async_client.patch(
            "/shorten/shortened_url",
            json=update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404


class TestDeleteUrl:
    async def test_delete_url(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]
        shortened_url: str = shorten_url.json()["data"]["shortened_url"]

        res = await async_client.delete(
            f"/shorten/{shortened_url}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 204

        res = await async_client.get(
            f"/shorten/{shortened_url}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

    async def test_update_invalid_url(
        self,
        async_client: httpx.AsyncClient,
        shorten_url: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        res = await async_client.delete(
            "/shorten/shortened_url",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404
