import httpx
import pytest
from uuid import uuid7
from redis.asyncio import Redis
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta


from app.api.models.otp import Otp
from tests.conftest import mock_auth_service


class TestSignUpWithEmail:
    @pytest.mark.asyncio
    async def test_sign_up(self, create_user: httpx.Response):
        json_res = create_user.json()

        assert create_user.status_code == 201
        assert json_res["message"] == (
            "Sign up completed successfully."
            "Check your email for verification code and instrcutions"
        )

    @pytest.mark.asyncio
    async def test_user_exists(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        sign_up_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload, headers={"env": "test"}
        )

        assert res.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_email(self, async_client: httpx.AsyncClient):
        sign_up_payload: dict = {
            "email": "invalid_user_email",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload, headers={"env": "test"}
        )

        assert res.status_code == 422


class TestLogin:
    @pytest.mark.asyncio
    async def test_login(self, async_client: httpx.AsyncClient, login: httpx.Response):
        json_res = login.json()

        assert login.status_code == 201
        assert "access_token" in json_res["data"]

    @pytest.mark.asyncio
    async def test_user_not_verified(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        login_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_wrong_email_login(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        login_payload: dict = {
            "email": "user@example123.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestSignUpWithGoogle:
    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

        assert res.status_code == 200
        assert "access_token" in json_res

        token_patch.assert_called_once()


class TestAuthToken:
    @pytest.mark.asyncio
    async def test_get_access_token(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        res = await async_client.post(
            "/auth/refresh",
            headers={"env": "test"},
        )
        json_res = res.json()

        assert res.status_code == 201
        assert "access_token" in json_res["data"]

    @pytest.mark.asyncio
    async def test_unauthorized_get_access_token(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.post(
            "/auth/refresh",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_get_current_user(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

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

    @pytest.mark.asyncio
    async def test_unauthenticated_user(self, async_client: httpx.AsyncClient):
        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestResendOtp:
    @pytest.mark.asyncio
    async def test_resend_otp_token(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        path: str = "app.api.services.auth_service.send_verification_email.delay"

        resend_otp_payload: dict = {
            "email": "user@example.com",
            "purpose": "email_signup",
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

    @pytest.mark.asyncio
    async def test_invalid_email_otp_token(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        resend_otp_payload: dict = {
            "email": "user@example123.com",
            "purpose": "email_signup",
        }

        res: httpx.Response = await async_client.post(
            "/auth/verify/resend",
            json=resend_otp_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400


class TestPasswordUpdateAndReset:
    @pytest.mark.asyncio
    async def test_update_password(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        password_update_payload: dict = {
            "curr_password": "test_user_password",
            "new_password": "new_test_user_password",
        }

        access_token = login.json()["data"]["access_token"]

        res: httpx.Response = await async_client.patch(
            "/auth/password-update",
            json=password_update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        json_res = res.json()

        assert res.status_code == 200
        assert json_res["data"]["email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_invalid_password_update(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        password_update_payload: dict = {
            "curr_password": "test_user123_password",
            "new_password": "new_test_user_password",
        }

        access_token = login.json()["data"]["access_token"]

        res: httpx.Response = await async_client.patch(
            "/auth/password-update",
            json=password_update_payload,
            headers={"Authorization": f"Bearer {access_token}", "env": "test"},
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_password(
        self,
        async_client: httpx.AsyncClient,
        verify_user: httpx.Response,
        test_redis_client: Redis,
    ):
        path: str = "app.api.services.auth_service.send_verification_email.delay"

        password_reset_payload: dict = {
            "email": "user@example.com",
        }

        with patch(path, new_callable=AsyncMock) as email_patch:
            res: httpx.Response = await async_client.patch(
                "/auth/password-reset",
                json=password_reset_payload,
                headers={"env": "test"},
            )

        email_patch.assert_called_once()

        assert res.status_code == 200

        ## verify

        fake_otp: Otp = Otp(
            id=uuid7(),
            otp="test_otp_token",
            user_id=uuid7(),
            purpose="password_reset",
            status="valid",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )

        otp_payload: dict = {
            "email": "user@example.com",
            "otp_code": "test_otp_token",
            "password": "new_test_user_password",
        }

        mock_auth_service(fake_otp, test_redis_client)

        res: httpx.Response = await async_client.post(
            "/auth/verify",
            json=otp_payload,
            headers={"env": "test"},
        )

        # login with new password
        login_payload: dict = {
            "email": "user@example.com",
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

    @pytest.mark.asyncio
    async def test_invalid_email_reset_password(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        password_reset_payload: dict = {
            "email": "user@example123.com",
        }

        res: httpx.Response = await async_client.patch(
            "/auth/password-reset",
            json=password_reset_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 404


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout(self, async_client: httpx.AsyncClient, login: httpx.Response):
        access_token = login.json()["data"]["access_token"]

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

    @pytest.mark.asyncio
    async def test_unauthorized_logout(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.post(
            "/auth/logout",
            headers={"env": "test"},
        )

        assert res.status_code == 401


class TestDeactivateAndReactivate:
    @pytest.mark.asyncio
    async def test_deactivate_account(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        res = await async_client.patch(
            "/auth/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 200

        login_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthorized_deactivate_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.patch(
            "/auth/deactivate",
            headers={"env": "test"},
        )

        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_reactivate_account(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        # deactivate user
        await async_client.patch(
            "/auth/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        res = await async_client.patch(
            "/auth/reactivate",
            json={"email": "user@example.com", "user_type": "email"},
            headers={"env": "test"},
        )

        assert res.status_code == 200

        login_payload: dict = {
            "email": "user@example.com",
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

    @pytest.mark.asyncio
    async def test_invalid_email_reactivate_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.patch(
            "/auth/reactivate",
            json={"email": "user@example123.com", "user_type": "email"},
            headers={"env": "test"},
        )

        assert res.status_code == 404


class TestDeleteAccount:
    @pytest.mark.asyncio
    async def test_delete_account(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        res = await async_client.delete(
            "/auth",
            headers={
                "Authorization": f"Bearer {access_token}",
                "env": "test",
            },
        )

        assert res.status_code == 204

        login_payload: dict = {
            "email": "user@example.com",
            "password": "test_user_password",
        }

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json=login_payload,
            headers={"env": "test"},
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthorized_delete_account(
        self, async_client: httpx.AsyncClient, verify_user: httpx.Response
    ):
        res = await async_client.delete(
            "/auth",
            headers={"env": "test"},
        )

        assert res.status_code == 401
