from fastapi import FastAPI
from contextlib import asynccontextmanager


from app.api.routers import router
from app.core.config import get_settings
from app.database.session import redis_client
from app.core.exception_handlers import ExceptionHandler


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis_client
    yield
    await app.state.redis.asclose()


app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION, lifespan=lifespan)


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
