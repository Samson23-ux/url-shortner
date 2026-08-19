from uuid import uuid4
from typing import Any
from redis.asyncio import Redis
from fastapi import Request, Response
from pyrate_limiter.limiter import Limiter
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter.abstracts import Rate, Duration
from fastapi_limiter.callback import default_callback
from fastapi_limiter.identifier import default_identifier
from pyrate_limiter.buckets.redis_bucket import RedisBucket


async def _test_aware_identifier(request: Request) -> str | Any:
    """Same env: test bypass slowapi used, minus the bug where the old
    get_test_id returned the get_remote_address function itself instead
    of calling it — every non-test client shared one bucket as a result.
    default_identifier already keys by client IP + path."""
    if request.headers.get("env") == "test":
        return f"test:{uuid4()}"
    return await default_identifier(request)


DURATION_MAPPING: dict[str, Duration] = {
    "seconds": Duration.SECOND,
    "minutes": Duration.MINUTE,
    "hour": Duration.HOUR,
}


async def get_limiter(request: Request, config: tuple) -> RateLimiter:
    """Retrieve the redis bucket instnace
    Each configuration gets a separate redis bucket stored in a dictionary
    The limiters dictionary is instantiated once at startup to make it globally
    accessible and prevent against race conditions under concurrent requests
    """
    redis: Redis = request.app.state.redis
    limiters: dict[tuple, RateLimiter] = request.app.state.limiters

    if config not in limiters:
        key, limit, unit, multiplier = config
        interval = DURATION_MAPPING.get(unit) * multiplier

        limit_bucket = await RedisBucket.init(
            rates=[Rate(limit=limit, interval=interval)],
            redis=redis,
            bucket_key=key,
        )
        limiter = Limiter(limit_bucket)

        rate_limiter = RateLimiter(
            limiter=limiter,
            identifier=_test_aware_identifier,
            callback=default_callback,
        )

        limiters[config] = rate_limiter

    return limiters[config]


def _limiter_handler(
    key: str, limit: int = None, unit: str = None, multiplier: int = 1
):
    async def rate_limiter(request: Request, response: Response):
        config = (key, limit, unit, multiplier)
        rate_limiter: RateLimiter = await get_limiter(request, config)

        return await rate_limiter(request, response)

    return rate_limiter
