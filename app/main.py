from fastapi import FastAPI


from app.api.routers import router
from app.core.config import get_settings
from app.core.exception_handlers import ExceptionHandler


settings = get_settings()


app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)


app.include_router(router.router)


exception_handler = ExceptionHandler(app=app)
exception_handler.add_handlers()


@app.get("/", status_code=200)
async def home():
    message: dict = {
        "status": "success",
        "message": "Welcome to URL Shortner API",
    }
    return message
