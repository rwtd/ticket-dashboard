#!/usr/bin/env python3
"""
Advanced Cache Manager for Ticket Dashboard
Provides Redis-based caching with fallback to memory cache
"""

import os
import json
import pickle
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from pathlib import Path

# Redis support (optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Memory cache fallback
from threading import Lock
import functools

logger = logging.getLogger(__name__)


class CacheManager:
    """Advanced caching system with Redis and memory fallback"""
    
    def __init__(self, 
                 redis_host: str = None,
                 redis_port: int = 6379,
                 redis_db: int = 0,
                 default_ttl: int = 300,
                 memory_cache_size: int = 1000):
        """
        Initialize cache manager
        
        Args:
            redis_host: Redis host (uses env var REDIS_HOST if None)
            redis_port: Redis port
            redis_db: Redis database number
            default_ttl: Default cache TTL in seconds
            memory_cache_size: Maximum memory cache entries
        """
        self.default_ttl = default_ttl
        self.memory_cache_size = memory_cache_size
        
        # Redis configuration
        redis_host = redis_host or os.environ.get('REDIS_HOST', 'localhost')
        
        # Initialize Redis if available
        self.redis_client = None
        if REDIS_AVAILABLE and redis_host:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    health_check_interval=30
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e}. Using memory cache only.")
                self.redis_client = None
        
        # Memory cache fallback
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._memory_cache_lock = Lock()
        
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True))
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        for key, value in sorted(kwargs.items()):
            if isinstance(value, (dict, list)):
                key_parts.append(f"{key}:{json.dumps(value, sort_keys=True)}")
            else:
                key_parts.append(f"{key}:{value}")
        
        # Create hash of the combined key
        combined = "|".join(key_parts)
        return hashlib.md5(combined.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            # Try Redis first
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    return pickle.loads(value)
            
            # Fallback to memory cache
            with self._memory_cache_lock:
                if key in self._memory_cache:
                    entry = self._memory_cache[key]
                    if entry['expires'] > datetime.now():
                        return entry['value']
                    else:
                        # Remove expired entry
                        del self._memory_cache[key]
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        try:
            ttl = ttl or self.default_ttl
            expires = datetime.now() + timedelta(seconds=ttl)
            
            # Try Redis first
            if self.redis_client:
                serialized = pickle.dumps(value)
                return self.redis_client.setex(key, ttl, serialized)
            
            # Fallback to memory cache
            with self._memory_cache_lock:
                # Clean up old entries if cache is full
                if len(self._memory_cache) >= self.memory_cache_size:
                    self._cleanup_memory_cache()
                
                self._memory_cache[key] = {
                    'value': value,
                    'expires': expires,
                    'created': datetime.now()
                }
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            # Remove from Redis
            if self.redis_client:
                self.redis_client.delete(key)
            
            # Remove from memory cache
            with self._memory_cache_lock:
                self._memory_cache.pop(key, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear cache entries matching pattern"""
        try:
            count = 0
            
            # Clear from Redis
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    count += self.redis_client.delete(*keys)
            
            # Clear from memory cache
            with self._memory_cache_lock:
                keys_to_delete = [
                    key for key in self._memory_cache.keys()
                    if pattern.replace('*', '') in key
                ]
                for key in keys_to_delete:
                    del self._memory_cache[key]
                    count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """Clear all cache entries"""
        try:
            # Clear Redis
            if self.redis_client:
                self.redis_client.flushdb()
            
            # Clear memory cache
            with self._memory_cache_lock:
                self._memory_cache.clear()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return False
    
    def _cleanup_memory_cache(self):
        """Clean up expired entries from memory cache"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._memory_cache.items()
            if entry['expires'] <= now
        ]
        
        for key in expired_keys:
            del self._memory_cache[key]
        
        # If still full, remove oldest entries
        if len(self._memory_cache) >= self.memory_cache_size:
            sorted_entries = sorted(
                self._memory_cache.items(),
                key=lambda x: x[1]['created']
            )
            # Remove 10% of oldest entries
            remove_count = max(1, self.memory_cache_size // 10)
            for key, _ in sorted_entries[:remove_count]:
                del self._memory_cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'redis_available': self.redis_client is not None,
            'memory_entries': len(self._memory_cache),
            'memory_size': sum(
                len(pickle.dumps(entry['value']))
                for entry in self._memory_cache.values()
            )
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats['redis_keys'] = info.get('db0', {}).get('keys', 0)
                stats['redis_memory'] = info.get('used_memory_human', '0B')
            except:
                pass
        
        return stats


# Widget-specific cache decorators
def widget_cache(ttl: int = 300, key_prefix: str = "widget"):
    """Decorator for caching widget function results"""
    def decorator(func):
        cache_manager = CacheManager()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = cache_manager._generate_key(key_prefix, func.__name__, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                cache_manager.set(cache_key, result, ttl)
                logger.debug(f"Cached result for {func.__name__}")
            
            return result
        
        # Add cache invalidation method
        wrapper.cache_clear = lambda: cache_manager.clear_pattern(f"{key_prefix}*{func.__name__}*")
        wrapper.cache_stats = lambda: cache_manager.get_stats()
        
        return wrapper
    return decorator


# Data-specific cache functions
def cache_widget_data(widget_name: str, params: dict, data: Any, ttl: int = 300) -> bool:
    """Cache widget data with specific key structure"""
    cache = CacheManager()
    key = cache._generate_key("widget", widget_name, **params)
    return cache.set(key, data, ttl)


def get_cached_widget_data(widget_name: str, params: dict) -> Optional[Any]:
    """Get cached widget data"""
    cache = CacheManager()
    key = cache._generate_key("widget", widget_name, **params)
    return cache.get(key)


def invalidate_widget_cache(widget_name: str = None):
    """Invalidate widget cache entries"""
    cache = CacheManager()
    if widget_name:
        return cache.clear_pattern(f"widget*{widget_name}*")
    else:
        return cache.clear_pattern("widget*")


# Query result caching
def cache_query_result(query_hash: str, result: Any, ttl: int = 600) -> bool:
    """Cache database query results"""
    cache = CacheManager()
    key = f"query:{query_hash}"
    return cache.set(key, result, ttl)


def get_cached_query_result(query_hash: str) -> Optional[Any]:
    """Get cached query result"""
    cache = CacheManager()
    key = f"query:{query_hash}"
    return cache.get(key)


if __name__ == "__main__":
    # Test cache manager
    logging.basicConfig(level=logging.INFO)
    
    cache = CacheManager()
    
    # Test basic operations
    test_key = "test:widget:response_time"
    test_data = {"avg_response": 2.5, "count": 150}
    
    print("Testing cache operations...")
    cache.set(test_key, test_data, ttl=60)
    retrieved = cache.get(test_key)
    
    print(f"Original: {test_data}")
    print(f"Retrieved: {retrieved}")
    print(f"Match: {test_data == retrieved}")
    
    # Test stats
    print(f"\nCache stats: {cache.get_stats()}")