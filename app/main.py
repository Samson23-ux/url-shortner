import sentry_sdk
from fastapi import FastAPI
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from starlette.middleware.sessions import SessionMiddleware


from app.limiter import limiter
from app.api.routers import router
from app.core.config import get_settings
from app.database.session import redis_client
from app.core.exception_handlers import ExceptionHandler


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis_client
    app.state.limiter = limiter
    yield
    await app.state.redis.aclose()
    app.state.limiter.reset()


sentry_sdk.init(
    dsn=settings.SENTRY_SDK_DSN,
    enable_logs=True,
    send_default_pii=True,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    profile_lifecycle="trace"
)


app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION, lifespan=lifespan)


app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.include_router(router.router)


exception_handler = ExceptionHandler(app=app)
exception_handler.add_handlers()


app.add_middleware(
    SessionMiddleware,
    max_age=900,
    same_site="lax",
    secret_key=settings.SESSION_SECRET_KEY,
    https_only=settings.ENVIRONMENT == "production",
)


@app.get("/", status_code=200)
async def home():
    message: dict = {
        "status": "success",
        "message": "Welcome to URL Shortner API",
    }
    return message
