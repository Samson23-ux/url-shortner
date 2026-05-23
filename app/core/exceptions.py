from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    pass


class ServerError(AppException):
    """Internal Server error."""

    pass


class AuthenticationError(AppException):
    """User not authenticated."""

    pass


def create_exception_handler(
    status_code: int, initial_detail: dict
) -> callable[[Request, AppException], JSONResponse]:
    async def exception_handler(request: Request, exc: AppException):
        message: str = initial_detail.get("message")
        initial_detail["message"] = message.format(**exc.__dict__)

        return JSONResponse(content=initial_detail, status_code=status_code)

    return exception_handler
