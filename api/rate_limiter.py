import asyncio
import time
from typing import Optional

import redis


class RateLimiter:
    """
    Sliding-window rate limiter with Redis backend and in-memory fallback.

    The Redis path uses a sorted set of timestamps (score = timestamp,
    member = timestamp string) so old entries can be pruned with
    ZREMRANGEBYSCORE in a single pipeline round-trip.

    IMPORTANT — blocking I/O model
    --------------------------------
    The underlying redis.Redis client is synchronous. All Redis calls are
    dispatched via asyncio.get_running_loop().run_in_executor() so they
    execute in the default thread-pool executor instead of on the event loop
    thread. This prevents the blocking network round-trip from stalling the
    event loop, which previously caused WebSocket heartbeats to time out and
    triggered EPIPE / ECONNRESET errors in the Vite proxy.

    The rate limiter owns its OWN Redis connection (not shared with
    RedisStateManager) to avoid cross-caller interference on the sync client.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
    ) -> None:
        self._client: Optional[redis.Redis] = None
        try:
            client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            client.ping()
            self._client = client
        except Exception:
            pass  # Fall through to in-memory mode

        self._memory: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def is_allowed(self, client_ip: str, limit: int, window_seconds: int = 1) -> bool:
        """Return True if this IP is within the rate limit, False if exceeded."""
        if self._client is not None:
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, self._redis_check, client_ip, limit, window_seconds
                )
            except Exception:
                pass  # Redis hiccup — fall through to memory

        return self._memory_check(client_ip, limit, window_seconds)

    async def clear(self) -> None:
        """Wipe all rate-limit keys. Used in tests to reset state between runs."""
        if self._client is not None:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._redis_clear)
            except Exception:
                pass
        self._memory.clear()

    # ------------------------------------------------------------------
    # Synchronous helpers (run in thread-pool executor)
    # ------------------------------------------------------------------

    def _redis_check(self, client_ip: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        key = f"rate_limit:{client_ip}"
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)   # prune stale
        pipe.zadd(key, {str(now): now})                        # record this hit
        pipe.zcard(key)                                        # count in window
        pipe.expire(key, window_seconds + 1)                   # auto-cleanup
        _, _, count, _ = pipe.execute()
        return int(count) <= limit

    def _redis_clear(self) -> None:
        keys = self._client.keys("rate_limit:*")
        if keys:
            self._client.delete(*keys)

    # ------------------------------------------------------------------
    # In-memory fallback (used when Redis is unavailable)
    # ------------------------------------------------------------------

    def _memory_check(self, client_ip: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        hits = [ts for ts in self._memory.get(client_ip, []) if ts > cutoff]
        if len(hits) < limit:
            hits.append(now)
            self._memory[client_ip] = hits
            return True
        self._memory[client_ip] = hits
        return False
