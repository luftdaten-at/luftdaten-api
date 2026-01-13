"""
In-memory response cache for API endpoints.

This module provides a thread-safe in-memory cache for caching serialized
API responses to avoid repeated database queries and serialization overhead.
"""

import time
import threading
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ResponseCache:
    """Thread-safe in-memory cache for API responses"""
    
    def __init__(self, ttl: int = 300):
        """
        Initialize the cache.
        
        Args:
            ttl: Time to live in seconds (default: 300 = 5 minutes)
        """
        self.cache: Dict[str, Tuple[bytes, float]] = {}
        self.lock = threading.RLock()
        self.ttl = ttl  # Time to live in seconds
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[bytes]:
        """
        Get cached response if valid, None otherwise.
        
        Args:
            key: Cache key (e.g., "cities_all" or "stations_all:json")
        
        Returns:
            Cached response bytes if valid and not expired, None otherwise
        """
        with self.lock:
            if key not in self.cache:
                self._misses += 1
                return None
            
            data, timestamp = self.cache[key]
            age = time.time() - timestamp
            
            if age > self.ttl:
                # Expired, remove from cache
                del self.cache[key]
                self._misses += 1
                logger.debug(f"Cache expired for key: {key} (age: {age:.2f}s)")
                return None
            
            self._hits += 1
            logger.debug(f"Cache hit for key: {key} (age: {age:.2f}s)")
            return data
    
    def set(self, key: str, data: bytes):
        """
        Store response in cache.
        
        Args:
            key: Cache key
            data: Response data as bytes
        """
        with self.lock:
            self.cache[key] = (data, time.time())
            logger.debug(f"Cached response for key: {key} (size: {len(data)} bytes)")
    
    def invalidate(self, pattern: str = None):
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match in cache keys. If None, clears all cache.
        """
        with self.lock:
            if pattern is None:
                cleared = len(self.cache)
                self.cache.clear()
                logger.info(f"Cache cleared: {cleared} entries removed")
            else:
                keys_to_remove = [k for k in self.cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self.cache[key]
                logger.info(f"Cache invalidated: {len(keys_to_remove)} entries matching '{pattern}' removed")
    
    def stats(self) -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self.lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "size": len(self.cache),
                "keys": list(self.cache.keys()),
                "ttl": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "total_requests": total_requests
            }
    
    def clear_stats(self):
        """Reset hit/miss statistics."""
        with self.lock:
            self._hits = 0
            self._misses = 0


# Global cache instances with 5 minutes default TTL
_cities_cache = ResponseCache(ttl=300)  # 5 minutes
_stations_cache = ResponseCache(ttl=300)  # 5 minutes


def get_cities_cache() -> ResponseCache:
    """
    Get the global cities cache instance.
    
    Returns:
        The global ResponseCache instance for cities
    """
    return _cities_cache


def get_stations_cache() -> ResponseCache:
    """
    Get the global stations cache instance.
    
    Returns:
        The global ResponseCache instance for stations
    """
    return _stations_cache
