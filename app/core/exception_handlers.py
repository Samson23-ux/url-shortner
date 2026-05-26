from fastapi import FastAPI


from app.core.exceptions import create_exception_handler, ServerError, AuthenticationError, InvalidSlugError

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
                    "message": "Oops! Something went wrong."
                }
            )
        )

        self._app.add_exception_handler(
            AuthenticationError,
            create_exception_handler(
                status_code=401,
                initial_detail={
                    "status": "error",
                    "message": "User not authenticated."
                }
            )
        )

        self._app.add_exception_handler(
            InvalidSlugError,
            create_exception_handler(
                status_code=400,
                initial_detail={
                    "status": "error",
                    "message": "{slug} is not a valid slug"
                }
            )
        )