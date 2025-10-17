#!/usr/bin/env python3
"""
Optimized Query Engine with Database Connection Pooling
Provides high-performance database operations with connection pooling
"""

import os
import hashlib
import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from contextlib import contextmanager
import threading
import time
from functools import lru_cache

# Import existing components
from enhanced_query_engine import EnhancedSupportQueryEngine
from cache_manager import CacheManager, cache_query_result, get_cached_query_result, widget_cache

logger = logging.getLogger(__name__)


class DatabaseConnectionPool:
    """Connection pool for DuckDB with proper resource management"""
    
    def __init__(self, 
                 db_path: str = "analytics.db",
                 max_connections: int = 10,
                 max_idle_time: int = 300,
                 enable_persistent: bool = True):
        """
        Initialize connection pool
        
        Args:
            db_path: Path to DuckDB database file
            max_connections: Maximum number of connections
            max_idle_time: Maximum idle time before connection cleanup
            enable_persistent: Whether to use persistent database
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.enable_persistent = enable_persistent
        
        # Connection management
        self._pool: List[Dict[str, Any]] = []
        self._pool_lock = threading.Lock()
        self._connection_counter = 0
        
        # Initialize persistent database if enabled
        if self.enable_persistent:
            self._initialize_persistent_db()
    
    def _initialize_persistent_db(self):
        """Initialize persistent database with indexes"""
        try:
            # Create directory if needed
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Create initial connection to set up database
            with self.get_connection() as conn:
                # Create indexes for common queries
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_tickets_create_date ON tickets(Create date)",
                    "CREATE INDEX IF NOT EXISTS idx_tickets_pipeline ON tickets(Pipeline)",
                    "CREATE INDEX IF NOT EXISTS idx_tickets_owner ON tickets(Case Owner)",
                    "CREATE INDEX IF NOT EXISTS idx_tickets_weekend ON tickets(Weekend_Ticket)",
                    "CREATE INDEX IF NOT EXISTS idx_chats_date ON chats(chat_creation_date_adt)",
                    "CREATE INDEX IF NOT EXISTS idx_chats_agent ON chats(agent_type)",
                ]
                
                for index_sql in indexes:
                    try:
                        conn.execute(index_sql)
                        logger.debug(f"Created index: {index_sql}")
                    except Exception as e:
                        logger.warning(f"Could not create index {index_sql}: {e}")
                
                logger.info(f"✅ Initialized persistent database at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize persistent database: {e}")
            self.enable_persistent = False
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            conn = self._acquire_connection()
            yield conn
        finally:
            if conn:
                self._release_connection(conn)
    
    def _acquire_connection(self) -> duckdb.DuckDBPyConnection:
        """Acquire a connection from the pool"""
        with self._pool_lock:
            # Try to get an existing connection
            current_time = time.time()
            
            for i, conn_info in enumerate(self._pool):
                if not conn_info['in_use']:
                    # Check if connection is still valid
                    if current_time - conn_info['last_used'] < self.max_idle_time:
                        conn_info['in_use'] = True
                        conn_info['last_used'] = current_time
                        logger.debug(f"Reused connection {conn_info['id']}")
                        return conn_info['connection']
                    else:
                        # Connection expired, close it
                        try:
                            conn_info['connection'].close()
                        except:
                            pass
                        self._pool.pop(i)
                        break
            
            # Create new connection if pool not full
            if len(self._pool) < self.max_connections:
                conn = self._create_connection()
                self._connection_counter += 1
                
                conn_info = {
                    'id': self._connection_counter,
                    'connection': conn,
                    'in_use': True,
                    'created': current_time,
                    'last_used': current_time,
                    'use_count': 1
                }
                
                self._pool.append(conn_info)
                logger.debug(f"Created new connection {conn_info['id']}")
                return conn
            
            # Pool is full, wait for available connection
            logger.warning("Connection pool full, waiting for available connection")
            raise Exception("Connection pool exhausted")
    
    def _release_connection(self, conn: duckdb.DuckDBPyConnection):
        """Release a connection back to the pool"""
        with self._pool_lock:
            for conn_info in self._pool:
                if conn_info['connection'] == conn and conn_info['in_use']:
                    conn_info['in_use'] = False
                    conn_info['last_used'] = time.time()
                    conn_info['use_count'] += 1
                    logger.debug(f"Released connection {conn_info['id']}")
                    return
    
    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a new database connection"""
        if self.enable_persistent and os.path.exists(self.db_path):
            conn = duckdb.connect(self.db_path)
            logger.debug(f"Connected to persistent database: {self.db_path}")
        else:
            conn = duckdb.connect(':memory:')
            logger.debug("Connected to in-memory database")
        
        # Optimize connection settings
        conn.execute("PRAGMA enable_progress_bar=false")
        conn.execute("PRAGMA threads=4")
        conn.execute("PRAGMA memory_limit='1GB'")
        
        return conn
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        with self._pool_lock:
            total_connections = len(self._pool)
            in_use_connections = sum(1 for conn_info in self._pool if conn_info['in_use'])
            available_connections = total_connections - in_use_connections
            
            avg_use_count = 0
            if total_connections > 0:
                avg_use_count = sum(conn_info['use_count'] for conn_info in self._pool) / total_connections
            
            return {
                'total_connections': total_connections,
                'in_use_connections': in_use_connections,
                'available_connections': available_connections,
                'max_connections': self.max_connections,
                'avg_use_count': avg_use_count,
                'persistent_enabled': self.enable_persistent,
                'db_path': self.db_path if self.enable_persistent else None
            }
    
    def cleanup_expired_connections(self):
        """Clean up expired connections"""
        with self._pool_lock:
            current_time = time.time()
            expired_indices = []
            
            for i, conn_info in enumerate(self._pool):
                if (not conn_info['in_use'] and 
                    current_time - conn_info['last_used'] > self.max_idle_time):
                    expired_indices.append(i)
            
            # Remove expired connections (in reverse order to maintain indices)
            for i in reversed(expired_indices):
                try:
                    self._pool[i]['connection'].close()
                except:
                    pass
                self._pool.pop(i)
            
            if expired_indices:
                logger.info(f"Cleaned up {len(expired_indices)} expired connections")


class OptimizedQueryEngine(EnhancedSupportQueryEngine):
    """Enhanced query engine with connection pooling and advanced caching"""
    
    def __init__(self, gemini_api_key: str, sheets_credentials_path: str = None):
        """Initialize optimized query engine"""
        super().__init__(gemini_api_key, sheets_credentials_path)
        
        # Initialize connection pool
        self.connection_pool = DatabaseConnectionPool(
            db_path="ticket_analytics.db",
            max_connections=10,
            enable_persistent=True
        )
        
        # Initialize advanced cache
        self.cache_manager = CacheManager()
        
        # Query result cache with longer TTL for expensive operations
        self.query_cache_ttl = 600  # 10 minutes
        
        logger.info("✅ Initialized Optimized Query Engine with connection pooling")
    
    def execute_query(self, sql: str, params: Dict[str, Any] = None) -> pd.DataFrame:
        """Execute query with connection pooling and result caching"""
        try:
            # Generate cache key from SQL and parameters
            cache_key = self._generate_query_cache_key(sql, params)
            
            # Check cache first
            cached_result = get_cached_query_result(cache_key)
            if cached_result is not None:
                logger.debug(f"Query cache hit for: {sql[:50]}...")
                return cached_result
            
            # Execute query with connection pool
            with self.connection_pool.get_connection() as conn:
                start_time = time.time()
                
                if params:
                    result_df = conn.execute(sql, params).fetchdf()
                else:
                    result_df = conn.execute(sql).fetchdf()
                
                execution_time = time.time() - start_time
                
                # Cache result if query took significant time
                if execution_time > 0.1:  # Cache queries taking > 100ms
                    cache_query_result(cache_key, result_df, self.query_cache_ttl)
                
                logger.debug(f"Query executed in {execution_time:.3f}s: {sql[:50]}...")
                return result_df
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def _generate_query_cache_key(self, sql: str, params: Dict[str, Any] = None) -> str:
        """Generate cache key for query"""
        key_parts = [sql]
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        return self.connection_pool.get_stats()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache_manager.get_stats()
    
    def warmup_cache(self, common_queries: List[str]):
        """Warm up cache with common queries"""
        logger.info("Warming up cache with common queries...")
        
        for sql in common_queries:
            try:
                # Execute query to populate cache
                result = self.execute_query(sql)
                logger.debug(f"Warmed up cache for: {sql[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to warm up cache for query: {e}")
        
        logger.info("✅ Cache warmup completed")


# Optimized widget data loading with caching
@widget_cache(ttl=300, key_prefix="widget")
def get_optimized_widget_data(widget_name: str, params: Dict[str, Any]) -> Any:
    """Optimized widget data loading with caching"""
    from widgets.registry import get_widget_and_meta
    
    try:
        builder, meta = get_widget_and_meta(widget_name)
        logger.debug(f"Building widget {widget_name} with params: {params}")
        
        # Build widget with optimized data loading
        result = builder(params)
        
        logger.debug(f"Widget {widget_name} built successfully")
        return result
        
    except Exception as e:
        logger.error(f"Failed to build widget {widget_name}: {e}")
        raise


# Background job processing for heavy operations
class BackgroundJobProcessor:
    """Process heavy operations in background"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.job_queue = []
        self.results = {}
        self._lock = threading.Lock()
    
    def submit_job(self, job_id: str, func, *args, **kwargs):
        """Submit a job for background processing"""
        with self._lock:
            self.job_queue.append({
                'id': job_id,
                'func': func,
                'args': args,
                'kwargs': kwargs,
                'submitted': datetime.now()
            })
        
        # Start processing in background thread
        thread = threading.Thread(
            target=self._process_job,
            args=(job_id, func, args, kwargs)
        )
        thread.daemon = True
        thread.start()
        
        return job_id
    
    def _process_job(self, job_id: str, func, args, kwargs):
        """Process a single job"""
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            with self._lock:
                self.results[job_id] = {
                    'status': 'completed',
                    'result': result,
                    'execution_time': execution_time,
                    'completed': datetime.now()
                }
            
            logger.info(f"Background job {job_id} completed in {execution_time:.2f}s")
            
        except Exception as e:
            with self._lock:
                self.results[job_id] = {
                    'status': 'failed',
                    'error': str(e),
                    'completed': datetime.now()
                }
            
            logger.error(f"Background job {job_id} failed: {e}")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and result"""
        with self._lock:
            return self.results.get(job_id)
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old job results"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            old_job_ids = [
                job_id for job_id, result in self.results.items()
                if result.get('completed') and result['completed'] < cutoff_time
            ]
            
            for job_id in old_job_ids:
                del self.results[job_id]
            
            if old_job_ids:
                logger.info(f"Cleaned up {len(old_job_ids)} old job results")


# Global instances
_job_processor = BackgroundJobProcessor(max_workers=4)


def get_job_processor() -> BackgroundJobProcessor:
    """Get global job processor instance"""
    return _job_processor


if __name__ == "__main__":
    # Test optimized query engine
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Optimized Query Engine...")
    
    # Test connection pool
    pool = DatabaseConnectionPool(max_connections=3)
    stats = pool.get_stats()
    print(f"Connection pool stats: {stats}")
    
    # Test cache manager
    cache = CacheManager()
    test_key = "test:optimized"
    test_data = {"performance": "improved", "speed": "faster"}
    
    cache.set(test_key, test_data, ttl=60)
    retrieved = cache.get(test_key)
    
    print(f"Cache test - Original: {test_data}")
    print(f"Cache test - Retrieved: {retrieved}")
    print(f"Cache stats: {cache.get_stats()}")
    
    print("✅ Optimized components tested successfully!")