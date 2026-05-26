import httpx
import pytest
from unittest.mock import patch, AsyncMock


pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestSignUpWithEmail:
    async def test_sign_up(self, create_user: httpx.Response):
        json_res = create_user.json()

        assert create_user.status_code == 201
        assert json_res["message"] == (
            "Sign up successful."
            "Please check your email for instructions to verify account and the verification code"
        )

    async def test_user_exists(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        sign_up_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload, headers={"env": "test"}
        )

        assert res.status_code == 409

    async def test_invalid_email(self, async_client: httpx.AsyncClient):
        sign_up_payload: dict = {
            "email": "invalid_user_email",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload, headers={"env": "test"}
        )

        assert res.status_code == 422


class TestSignUpWithGoogle:
    async def test_sign_in_google(self, async_client: httpx.AsyncClient):
        url_path: str = "app.api.routers.auth.Request.url_for"
        token_path: str = "app.api.routers.auth.oauth.google.authorize_redirect"

        with (
            patch(url_path, new_callable=AsyncMock) as url_patch,
            patch(token_path, new_callable=AsyncMock) as token_patch,
        ):
            token_patch.return_value = None
            res: httpx.Response = await async_client.get(
                "/auth/google", headers={"env": "test"}
            )

        assert res.status_code == 302

        url_patch.assert_called_once()
        token_patch.assert_awaited_once()

    async def test_google_callback(self, async_client: httpx.AsyncClient):
        payload: dict = {
            "sub": "randomfakeid",
            "email": "user@example.com",
        }

        token: dict = {"userinfo": payload}

        token_path: str = "app.api.routers.auth.oauth.google.authorize_access_token"

        with patch(token_path, new_callable=AsyncMock) as token_patch:
            token_patch.return_value = token

            res: httpx.Response = await async_client.get(
                "/auth/google/callback", headers={"env": "test"}
            )

        json_res = res.json()

        assert res.status_code == 201
        assert "access_token" in json_res

        token_patch.assert_called_once()


class TestLogin:
    async def test_login(self, async_client: httpx.AsyncClient, login: httpx.Response):
        json_res = login.json()

        assert login.status_code == 201
        assert "access_token" in json_res["data"]

    async def test_user_not_verified(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        login_payload: dict = {
            "username": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    async def test_wrong_email_login(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        login_payload: dict = {
            "username": "user@example123.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestAuthToken:
    async def test_get_access_token(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        res = await async_client.post(
            "/auth/refresh",
            headers={"env": "test"},
        )
        json_res = res.json()

        assert res.status_code == 201
        assert "access_token" in json_res

    async def test_unauthorized_get_access_token(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.post(
            "/auth/refresh",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestGetCurrentUser:
    async def test_get_current_user(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["access_token"]

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        json_res = res.json()

        assert res.status_code == 200
        assert "user@example.com" == json_res["data"]["email"]

    async def test_unauthenticated_user(self, async_client: httpx.AsyncClient):
        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestResendOtp:
    async def test_resend_otp_token(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        path: str = "app.api.services.auth_service.send_email.delay"

        resend_otp_payload: dict = {
            "email": "user@example.com",
        }

        with patch(path, new_callable=AsyncMock) as email_patch:
            res: httpx.Response = await async_client.post(
                "/auth/verify/resend",
                json=resend_otp_payload,
                headers={"env": "test"},
            )

        json_res = res.json()

        email_patch.assert_called_once()

        assert res.status_code == 201
        assert json_res["status"] == "success"

    async def test_invalid_email_otp_token(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        path: str = "app.api.services.auth_service.send_email.delay"

        resend_otp_payload: dict = {
            "email": "user@example123.com",
        }

        with patch(path, new_callable=AsyncMock) as email_patch:
            res: httpx.Response = await async_client.post(
                "/auth/verify/resend",
                json=resend_otp_payload,
                headers={"env": "test"},
            )

        json_res = res.json()

        email_patch.assert_called_once()

        assert res.status_code == 201
        assert json_res["status"] == "success"


class PasswordUpdateAndReset:
    async def test_update_password(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        password_update_payload: dict = {
            "curr_password": "test_user_password",
            "new_password": "new_test_user_password",
        }

        access_token = login.json()["access_token"]

        res: httpx.Response = await async_client.post(
            "/auth/password-update",
            json=password_update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["email"] == "user@example.com"

    async def test_invalid_password_update(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        password_update_payload: dict = {
            "curr_password": "test_user123_password",
            "new_password": "new_test_user_password",
        }

        access_token = login.json()["access_token"]

        res: httpx.Response = await async_client.post(
            "/auth/password-update",
            json=password_update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 400

    async def test_reset_password(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        path: str = "app.api.services.auth_service.send_email.delay"

        password_reset_payload: dict = {
            "email": "user@example.com",
            "new_password": "new_test_user_password",
        }

        with patch(path, new_callable=AsyncMock) as email_patch:
            res: httpx.Response = await async_client.post(
                "/auth/password-reset",
                json=password_reset_payload,
                headers={"env": "test"},
            )

        email_patch.assert_called_once()

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["email"] == "user@example.com"

    async def test_invalid_email_reset_password(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        password_reset_payload: dict = {
            "email": "user@example123.com",
            "new_password": "new_test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/password-reset",
            json=password_reset_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestLogout:
    async def test_logout(self, async_client: httpx.AsyncClient, login: httpx.Response):
        access_token = login.json()["access_token"]

        res = await async_client.post(
            "/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 201

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 401

    async def test_unauthorized_logout(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.post(
            "/auth/logout",
            headers={"env": "test"},
        )

        assert res.status_code == 201


class TestDeactivateAndReactivate:
    async def test_deactivate_account(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["access_token"]

        res = await async_client.patch(
            "/auth/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 200

        login_payload: dict = {
            "username": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    async def test_unauthorized_deactivate_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.patch(
            "/auth/deactivate",
            headers={"env": "test"},
        )

        assert res.status_code == 401

    async def test_reactivate_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.patch(
            "/auth/reactivate",
            data={"email": "user@example.com"},
            headers={"env": "test"},
        )

        assert res.status_code == 200

        login_payload: dict = {
            "username": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 201
        assert "access_token" in json_res["data"]

    async def test_invalid_email_reactivate_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.patch(
            "/auth/reactivate",
            data={"email": "user@example123.com"},
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestDeleteAccount:
    async def test_delete_account(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["access_token"]

        res = await async_client.delete(
            "/auth",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 204

        login_payload: dict = {
            "username": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            data=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    async def test_unauthorized_delete_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.delete(
            "/auth",
            headers={"env": "test"},
        )

        assert res.status_code == 401
