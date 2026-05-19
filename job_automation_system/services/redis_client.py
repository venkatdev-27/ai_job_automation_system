"""
Redis Client - Job Automation System
====================================
Singleton Redis connection pool for all services.
Optimized for high concurrency with 40+ students.
"""

from __future__ import annotations
import redis
from typing import Optional
from config import settings
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Singleton Redis client with connection pool."""
    
    _instance: Optional[redis.Redis] = None
    _pool: Optional[redis.ConnectionPool] = None
    
    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pool = None
            cls._instance._client = None
        return cls._instance
    
    def _create_pool(self) -> redis.ConnectionPool:
        """Create optimized connection pool for high concurrency."""
        return redis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None,
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    
    @property
    def client(self) -> redis.Redis:
        if self._pool is None:
            self._pool = self._create_pool()
        if self._client is None:
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client
    
    @property
    def pool(self) -> redis.ConnectionPool:
        if self._pool is None:
            self._pool = self._create_pool()
        return self._pool
    
    def __getattr__(self, name: str):
        return getattr(self.client, name)
    
    def get_connection(self) -> redis.Redis:
        """Get a fresh connection from pool for long-running ops."""
        return redis.Redis(connection_pool=self.pool)
    
    def close(self):
        if self._client:
            self._client = None
        if self._pool:
            self._pool.disconnect()
            self._pool = None
        logger.info("Redis connection pool closed")
    
    def health_check(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False


redis_client = RedisClient()