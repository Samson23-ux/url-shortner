import time
from uuid import uuid4
from typing import Any

from redis.asyncio import Redis
from fastapi import Request, Response
from pyrate_limiter.limiter import Limiter
from fastapi_limiter.depends import RateLimiter
from fastapi_limiter.callback import default_callback
from fastapi_limiter.identifier import default_identifier
from pyrate_limiter.abstracts.bucket import BucketFactory
from pyrate_limiter.buckets.redis_bucket import RedisBucket
from pyrate_limiter.abstracts import Rate, Duration, RateItem, AbstractBucket


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


class _PerIdentityRedisBucketFactory(BucketFactory):
    """
    Passing a bare RedisBucket straight to pyrate_limiter's Limiter() wraps
    it in SingleBucketFactory, which always routes every request to the
    SAME bucket regardless of the item's identity — RedisBucket's Lua
    script counts everything in that one Redis key with no per-item
    filtering. That makes a naive Limiter(bucket) setup a limit shared
    globally by every caller, not a per-client one, no matter what
    identifier is passed to RateLimiter.

    This factory instead gives each identity (client IP, or the env:test
    bypass UUID) its own Redis sorted set, keyed off the item's full name
    (identity:route_index:dep_index, built by fastapi_limiter's
    RateLimiter). The Lua script hash is resolved once via a throwaway
    bucket when the Limiter is built, then reused here — SCRIPT LOAD
    caches server-side by script content, so building a RedisBucket per
    identity is just attribute assignment, no extra Redis round trip
    beyond the check itself.
    """

    def __init__(
        self, redis: Redis, rates: list[Rate], key_prefix: str, script_hash: str
    ):
        self._redis = redis
        self._rates = rates
        self._key_prefix = key_prefix
        self._script_hash = script_hash

    def wrap_item(self, name: str, weight: int = 1) -> RateItem:
        now_ms = time.time_ns() // 1_000_000
        return RateItem(name, now_ms, weight=weight)

    def get(self, item: RateItem) -> AbstractBucket:
        bucket_key = f"{self._key_prefix}:{item.name}"
        return RedisBucket(self._rates, self._redis, bucket_key, self._script_hash)


async def get_limiter(request: Request, config: tuple) -> RateLimiter:
    """Retrieve the RateLimiter for a given (key, limit, unit, multiplier)
    config, building it once per config and caching it on app.state.
    Each one owns a _PerIdentityRedisBucketFactory, so callers are scoped
    correctly by identity instead of sharing one global bucket.
    """
    redis: Redis = request.app.state.redis
    limiters: dict[tuple, RateLimiter] = request.app.state.limiters

    if config not in limiters:
        key, limit, unit, multiplier = config
        interval = DURATION_MAPPING.get(unit) * multiplier
        rates = [Rate(limit=limit, interval=interval)]

        # Throwaway bucket, used only to resolve the Lua script hash once.
        seed_bucket: RedisBucket = await RedisBucket.init(
            rates=rates, redis=redis, bucket_key=key
        )

        factory = _PerIdentityRedisBucketFactory(
            redis=redis,
            rates=rates,
            key_prefix=key,
            script_hash=seed_bucket.script_hash,
        )
        limiter = Limiter(factory)

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
