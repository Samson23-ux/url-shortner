from fastapi import FastAPI


from app.core.exceptions import (
    create_exception_handler,
    ServerError,
    AuthenticationError,
    InvalidSlugError,
    UserExistsError,
    InvalidOtpError,
    UserNotFoundError,
    CredentialError,
    PasswordMissingError,
    SlugExistsError,
    UrlExistsError,
    UrlNotFoundError,
    SlugNotFoundError,
    UrlExpiredError,
    UrlsNotFoundError,
    SlugsNotFoundError
)


class ExceptionHandler:
    def __init__(self, app: FastAPI):
        self._app = app

    def add_handlers(self):
        self._app.add_exception_handler(
            ServerError,
            create_exception_handler(
                status_code=500,
                initial_detail={
                    "status": "error",
                    "message": "Oops! Something went wrong.",
                },
            ),
        )

        self._app.add_exception_handler(
            AuthenticationError,
            create_exception_handler(
                status_code=401,
                initial_detail={
                    "status": "error",
                    "message": "User not authenticated.",
                },
            ),
        )

        self._app.add_exception_handler(
            InvalidSlugError,
            create_exception_handler(
                status_code=400,
                initial_detail={
                    "status": "error",
                    "message": "{slug} is not a valid slug",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UserExistsError,
            handler=create_exception_handler(
                status_code=409,
                initial_detail={
                    "status": "error",
                    "message": "User already exists with the provided email {user_email}",
                },
            ),
        )

        self._app.add_exception_handler(
            InvalidOtpError,
            create_exception_handler(
                initial_detail={
                    "status": "error",
                    "message": "Invalid otp received",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UserNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "User not found with email {user_email}",
                },
            ),
        )

        self._app.add_exception_handler(
            CredentialError,
            create_exception_handler(
                initial_detail={
                    "status": "error",
                    "message": "Invalid credentials!",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            PasswordMissingError,
            create_exception_handler(
                initial_detail={
                    "status": "error",
                    "message": "Password value missing for password reset account verification",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UrlExistsError,
            handler=create_exception_handler(
                status_code=409,
                initial_detail={
                    "status": "error",
                    "message": "{url} already exists",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=SlugExistsError,
            handler=create_exception_handler(
                status_code=409,
                initial_detail={
                    "status": "error",
                    "message": "{slug} already exists",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UrlsNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "No urls found at the moment",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=SlugsNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "No slugs found at the moment",
                },
            ),
        )


        self._app.add_exception_handler(
            exc_class_or_status_code=UrlNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "No url found with the slug {slug}",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=SlugNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "{slug} not found",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UrlExpiredError,
            handler=create_exception_handler(
                status_code=410,
                initial_detail={
                    "status": "error",
                    "message": "{url} expired",
                },
            ),
        )
