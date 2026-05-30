from redis.asyncio import Redis


class RedisRepository:
    def __init__(self, redis: Redis):
        self._redis = redis

    async def filter_exists(self, key) -> int:
        return await self._redis.exists(key)

    async def create_filter(self, key: str, capacity: int = 200, expansion: int = 2):
        await self._redis.cf().reserve(key, capacity, expansion=expansion)

    async def add_to_filter(self, key: str, value: str):
        await self._redis.cf().add(key, value)

    async def filter_value_exists(self, key: str, value: str) -> bool:
        return await self._redis.cf().exists(key, value)

    async def add_refresh_token(self, key: str, value: str):
        await self._redis.hset(key, mapping=value)

    async def get_refresh_token(self, key: str) -> dict:
        return await self._redis.hgetall(key)

    async def increment_clicks(self, key: str, ttl: int):
        await self._redis.incr(key)
        await self._redis.expire(key, ttl)

    async def delete_refresh_token(self, key: str):
        await self._redis.delete(key)

    async def delete_filter_value(self, key: str, value: str):
        await self._redis.cf().delete(key, value)
