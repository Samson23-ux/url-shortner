from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    pass


class ServerError(AppException):
    """Internal Server error."""

    pass


class TransientError(AppException):
    """Worker Transient error"""

    pass


class AuthenticationError(AppException):
    """User not authenticated."""

    pass


class InvalidSlugError(AppException):
    """Invalid slug name for url"""

    def __init__(self, slug: str):
        self.slug = slug


class UserExistsError(AppException):
    """User already exists"""

    def __init__(self, user_email: str):
        self.user_email = user_email


class UserNotFoundError(AppException):
    """User not found"""

    def __init__(self, user_email: str):
        self.user_email = user_email


class InvalidOtpError(AppException):
    """Invalid otp received"""

    pass


class CredentialError(AppException):
    """wrong credentials provided"""

    pass


class PasswordMissingError(AppException):
    """password not set for password reset"""

    pass


class UrlExistsError(AppException):
    """Url already exists"""

    def __init__(self, url: str):
        self.url = url


class SlugExistsError(AppException):
    """Url already exists"""

    def __init__(self, slug: str):
        self.slug = slug


class UrlsNotFoundError(AppException):
    """Urls not found"""

    pass


class UrlNotFoundError(AppException):
    """Url not found"""

    def __init__(self, slug: str):
        self.slug = slug


class SlugsNotFoundError(AppException):
    """Slugs not found"""

    pass

class SlugNotFoundError(AppException):
    """Slug not found"""

    def __init__(self, slug: str):
        self.slug = slug


class UrlExpiredError(AppException):
    """Url already expired"""

    def __init__(self, url: str):
        self.url = url


def create_exception_handler(
    status_code: int, initial_detail: dict
) -> callable[[Request, AppException], JSONResponse]:
    async def exception_handler(request: Request, exc: AppException):
        message: str = initial_detail.get("message")
        initial_detail["message"] = message.format(**exc.__dict__)

        return JSONResponse(content=initial_detail, status_code=status_code)

    return exception_handler
