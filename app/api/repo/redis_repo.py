from redis import Redis as SyncRedis
from redis.asyncio import Redis


class RedisRepository:
    def __init__(self, async_redis: Redis = None, sync_redis: SyncRedis = None):
        self._sync_redis = sync_redis
        self._async_redis = async_redis

    async def _set_hash(self, key: str, value: dict, ttl: int | None = None):
        if ttl is None:
            await self._async_redis.hset(key, mapping=value)
            return

        async with self._async_redis.pipeline() as pipe:
            pipe.hset(key, mapping=value)
            pipe.expire(key, ttl)
            await pipe.execute()

    async def add_refresh_token(self, key: str, value: str):
        await self._set_hash(key, value)

    async def get_refresh_token(self, key: str) -> dict:
        return await self._async_redis.hgetall(key)

    async def increment_clicks(self, key: str, ttl: int):
        async with self._async_redis.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, ttl)
            await pipe.execute()

    async def delete_key(self, key: str):
        await self._async_redis.delete(key)

    async def cache_url(self, key: str, value: dict, ttl: int):
        await self._set_hash(key, value, ttl)

    async def get_cached_url(self, key: str) -> dict:
        return await self._async_redis.hgetall(key)

    async def cache_user(self, key: str, value: dict, ttl: int):
        await self._set_hash(key, value, ttl)

    async def get_cached_user(self, key: str) -> dict:
        return await self._async_redis.hgetall(key)

    async def delete_filter_value(self, key: str, value: str):
        await self._async_redis.cf().delete(key, value)

    def get_clicks_keys(self, prefix_key: str):
        return self._sync_redis.keys(prefix_key)

    def get_clicks(self, key: str):
        return self._sync_redis.getdel(key)
