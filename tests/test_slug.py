import httpx
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestCreateSlug:
    async def test_create_slug(
        self, create_slug: httpx.Response
    ):
        json_res = create_slug.json()

        assert create_slug.status_code == 201
        assert json_res["data"]

    async def test_slug_exists(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        slug_create_payload: dict = {
            "custom_slug": "test-slug",
        }

        res = await async_client.post(
            "/slugs",
            json=slug_create_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 409

    async def test_invalid_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        slug_create_payload: dict = {
            "custom_slug": "test-slug!!!!!",
        }

        res = await async_client.post(
            "/slugs",
            json=slug_create_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 400

class TestGetSlug:
    async def test_get_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]
        custom_slug: str = create_slug.json()["data"]["custom_slug"]

        res = await async_client.post(
            f"/slugs/{custom_slug}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["custom_slug"] == "test-slug"

    async def test_get_invalid_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        res = await async_client.post(
            "/slugs/custom_slug",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

    async def test_get_all_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        res = await async_client.post(
            "/slugs",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert len(json_res["data"]) >= 1

class TestUpdateSlug:
    async def test_update_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]
        custom_slug: str = create_slug.json()["data"]["custom_slug"]

        update_payload: dict = {
            "new_custom_slug": "new-test-slug",
        }

        res = await async_client.patch(
            f"/slugs/{custom_slug}",
            json=update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert custom_slug == json_res["data"]["custom_slug"]


    async def test_update_invalid_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        update_payload: dict = {
            "new_custom_slug": "new-test-slug",
        }

        res = await async_client.patch(
            "/slugs/custom_slug",
            json=update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

class TestDeleteUrl:
    async def test_delete_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]
        custom_slug: str = create_slug.json()["data"]["custom_slug"]

        res = await async_client.delete(
            f"/slugs/{custom_slug}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 204

        res = await async_client.get(
            f"/slugs/{custom_slug}",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404

    async def test_delete_invalid_slug(
        self,
        async_client: httpx.AsyncClient,
        create_slug: httpx.Response,
        login: httpx.Response,
    ):
        access_token = login.json()["access_token"]

        res = await async_client.delete(
            "/slugs/custom-slug",
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 404        
