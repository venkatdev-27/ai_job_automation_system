"""
MongoDB Client - Job Automation System
======================================
Singleton MongoDB connection for all database operations.
Includes retry logic for unstable network connections (e.g. Atlas free tier).
"""

from __future__ import annotations
import time
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# Connection constants
MAX_CONNECT_RETRIES = 3
RETRY_DELAY_SECONDS = 3
SERVER_SELECTION_TIMEOUT_MS = 30000
CONNECT_TIMEOUT_MS = 20000
SOCKET_TIMEOUT_MS = 30000


from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pymongo import MongoClient
    from pymongo.database import Database
    from pymongo.collection import Collection

class MongoDBClient:
    """Singleton MongoDB client with retry logic for unstable networks."""
    
    _instance: Optional["MongoDBClient"] = None
    _client: Optional[Any] = None
    
    def __new__(cls) -> "MongoDBClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance
    
    def _create_client(self) -> Any:
        """Create a MongoClient with generous timeouts for Atlas."""
        try:
            from pymongo import MongoClient
            return MongoClient(
                settings.mongo_uri,
                serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=CONNECT_TIMEOUT_MS,
                socketTimeoutMS=SOCKET_TIMEOUT_MS,
                retryReads=True,
                retryWrites=True,
            )
        except ImportError:
            logger.error("pymongo not installed. Please run 'pip install pymongo'")
            raise ImportError("pymongo is required for database operations. Install with 'pip install pymongo'")
    
    @property
    def client(self) -> Any:
        if self._client is None:
            from pymongo.errors import ServerSelectionTimeoutError, ConfigurationError
            last_error = None
            for attempt in range(1, MAX_CONNECT_RETRIES + 1):
                try:
                    self._client = self._create_client()
                    # Verify connectivity with a ping
                    self._client.admin.command("ping")
                    logger.info("MongoDB connected (attempt %d)", attempt)
                    return self._client
                except (ServerSelectionTimeoutError, ConfigurationError) as e:
                    last_error = e
                    logger.warning(
                        "MongoDB connection attempt %d/%d failed: %s",
                        attempt, MAX_CONNECT_RETRIES, e
                    )
                    if self._client:
                        try:
                            self._client.close()
                        except Exception:
                            pass
                        self._client = None
                    if attempt < MAX_CONNECT_RETRIES:
                        delay = RETRY_DELAY_SECONDS * attempt
                        logger.info("Retrying in %ds...", delay)
                        time.sleep(delay)
            
            # Final attempt — return client without ping and let caller handle errors
            logger.warning("All %d connect attempts failed, creating client without ping", MAX_CONNECT_RETRIES)
            self._client = self._create_client()
        return self._client
    
    @property
    def database(self) -> Any:
        """Get the default database."""
        return self.client[settings.mongo_db]
    
    def get_collection(self, name: str) -> Any:
        """Get a specific collection."""
        return self.database[name]
    
    def close(self):
        """Close the connection."""
        if self._client:
            self._client.close()
            self._client = None


# Global client instance
mongodb_client = MongoDBClient()


# Convenience accessors
def get_database() -> Any:
    """Get the database instance."""
    return mongodb_client.database


def get_collection(name: str) -> Any:
    """Get a collection by name."""
    return mongodb_client.get_collection(name)


def close_database():
    """Close the database connection."""
    mongodb_client.close()