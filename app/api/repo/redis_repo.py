from redis.asyncio import Redis
from redis import Redis as SyncRedis


class RedisRepository:
    def __init__(self, async_redis: Redis = None, sync_redis: SyncRedis = None):
        self._sync_redis = sync_redis
        self._async_redis = async_redis

    async def filter_exists(self, key) -> int:
        return await self._async_redis.exists(key)

    async def create_filter(self, key: str, capacity: int = 200, expansion: int = 2):
        await self._async_redis.cf().reserve(key, capacity, expansion=expansion)

    async def add_to_filter(self, key: str, value: str):
        await self._async_redis.cf().add(key, value)

    async def filter_value_exists(self, key: str, value: str) -> bool:
        return await self._async_redis.cf().exists(key, value)

    async def add_refresh_token(self, key: str, value: str):
        await self._async_redis.hset(key, mapping=value)

    async def get_refresh_token(self, key: str) -> dict:
        return await self._async_redis.hgetall(key)

    async def increment_clicks(self, key: str, ttl: int):
        await self._async_redis.incr(key)
        await self._async_redis.expire(key, ttl)

    async def delete_refresh_token(self, key: str):
        await self._async_redis.delete(key)

    async def delete_filter_value(self, key: str, value: str):
        await self._async_redis.cf().delete(key, value)

    def get_clicks_keys(self, prefix_key: str):
        return self._sync_redis.keys(prefix_key)

    def get_clicks(self, key: str):
        return self._sync_redis.getdel(key)
