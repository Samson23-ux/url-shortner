from uuid import uuid4
from redis.asyncio import Redis
from fastapi import Request, Response
from pyrate_limiter.limiter import Limiter
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter.abstracts import Rate, Duration
from fastapi_limiter.callback import default_callback
from fastapi_limiter.identifier import default_identifier
from pyrate_limiter.buckets.redis_bucket import RedisBucket


async def _test_aware_identifier(request: Request):
    """Same env: test bypass slowapi used, minus the bug where the old
    get_test_id returned the get_remote_address function itself instead
    of calling it — every non-test client shared one bucket as a result.
    default_identifier already keys by client IP + path."""
    if request.headers.get("env") == "test":
        return f"test:{uuid4()}"
    return await default_identifier(request)


# Populated by init_limiters() from the app's lifespan, since building a
# RedisBucket awaits a Lua SCRIPT LOAD — can't happen at plain import time.
limiter: Limiter | None = None


DEFAULT_LIMIT = 10
DEFAULT_DURATION = Duration.MINUTE


async def init_limiters(redis: Redis):
    global limiter

    limit_bucket = await RedisBucket.init(
        rates=[Rate(limit=DEFAULT_LIMIT, interval=DEFAULT_DURATION)],
        redis=redis,
        bucket_key="limiter",
    )
    limiter = Limiter(limit_bucket)


class _LazyRateLimiter:
    """Route decorators need a concrete dependency at import time, but the
    real Limiter doesn't exist until init_limiters() runs inside the app's
    async lifespan (before any request is served). This defers building
    the actual RateLimiter to request time, by which point it's ready."""

    def __init__(self, limiter):
        self._limiter = limiter

    async def __call__(self, request: Request, response: Response):
        rate_limiter = RateLimiter(
            limiter=self._limiter(),
            identifier=_test_aware_identifier,
            callback=default_callback,
        )
        return await rate_limiter(request, response)


def _limiter_handler(
    key: str, limit: int = None, unit: str = None, multiplier: int = 1
):
    async def rate_limiter(request: Request, response: Response):
        duration_mapping: dict[str, Duration] = {
            "seconds": Duration.SECOND,
            "minutes": Duration.MINUTE,
            "hour": Duration.HOUR,
        }
        redis_bucket: RedisBucket = limiter.bucket_factory.bucket

        redis_bucket.bucket_key = key

        if limit:
            redis_bucket.rates[0].limit = limit
        if unit:
            redis_bucket.rates[0].interval = duration_mapping.get(unit) * multiplier

        rate_limit = _LazyRateLimiter(lambda: limiter)
        return await rate_limit(request, response)

    return rate_limiter
