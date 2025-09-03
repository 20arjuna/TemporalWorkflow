"""
Database connection management for Trellis Takehome.
Provides connection pooling and database utilities.
"""

import asyncio
import asyncpg
import json
import os
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

# Database configuration from docker-compose.yml
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "user": os.getenv("DB_USER", "trellis"),
    "password": os.getenv("DB_PASSWORD", "trellis"),
    "database": os.getenv("DB_NAME", "trellis"),
    "min_size": 5,  # Minimum connections in pool
    "max_size": 20,  # Maximum connections in pool
}

# Global connection pool
_connection_pool: Optional[asyncpg.Pool] = None

async def init_db_pool():
    """Initialize the database connection pool."""
    global _connection_pool
    
    if _connection_pool is None:
        print(f"🔌 Initializing DB pool: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        
        try:
            _connection_pool = await asyncpg.create_pool(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                min_size=DB_CONFIG["min_size"],
                max_size=DB_CONFIG["max_size"],
                command_timeout=30,
            )
            print("✅ Database connection pool initialized")
            
        except Exception as e:
            print(f"❌ Failed to initialize DB pool: {e}")
            raise

async def close_db_pool():
    """Close the database connection pool."""
    global _connection_pool
    
    if _connection_pool:
        print("🔌 Closing database connection pool...")
        await _connection_pool.close()
        _connection_pool = None
        print("✅ Database pool closed")

@asynccontextmanager
async def get_db_connection():
    """Get a database connection from the pool."""
    global _connection_pool
    
    if _connection_pool is None:
        await init_db_pool()
    
    async with _connection_pool.acquire() as connection:
        yield connection

async def execute_query(query: str, *args) -> str:
    """Execute a query and return the status."""
    async with get_db_connection() as conn:
        result = await conn.execute(query, *args)
        return result

async def fetch_one(query: str, *args) -> Optional[Dict[str, Any]]:
    """Fetch a single row as a dictionary."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None

async def fetch_all(query: str, *args) -> List[Dict[str, Any]]:
    """Fetch all rows as a list of dictionaries."""
    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]

async def fetch_value(query: str, *args) -> Any:
    """Fetch a single value."""
    async with get_db_connection() as conn:
        return await conn.fetchval(query, *args)

class DatabaseManager:
    """High-level database operations manager."""
    
    @staticmethod
    async def health_check() -> Dict[str, Any]:
        """Check database health and connection."""
        try:
            async with get_db_connection() as conn:
                # Test basic query
                version = await conn.fetchval("SELECT version()")
                
                # Check table counts
                table_counts = {}
                for table in ['orders', 'payments', 'events']:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    table_counts[table] = count
                
                return {
                    "status": "healthy",
                    "version": version,
                    "table_counts": table_counts,
                    "pool_size": _connection_pool.get_size() if _connection_pool else 0,
                    "pool_idle": _connection_pool.get_idle_size() if _connection_pool else 0,
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "pool_size": _connection_pool.get_size() if _connection_pool else 0,
            }
    
    @staticmethod
    def parse_json_field(value: Any) -> Any:
        """Parse JSON field from database (handles string/dict conversion)."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
    
    @staticmethod
    def prepare_json_field(value: Any) -> str:
        """Prepare JSON field for database insertion."""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

# Lifecycle management
async def startup_db():
    """Initialize database on application startup."""
    await init_db_pool()

async def shutdown_db():
    """Cleanup database on application shutdown."""
    await close_db_pool()

# For backwards compatibility and direct usage
async def get_connection():
    """Get a raw database connection (for advanced usage)."""
    global _connection_pool
    
    if _connection_pool is None:
        await init_db_pool()
    
    return await _connection_pool.acquire()

async def release_connection(conn):
    """Release a raw database connection."""
    global _connection_pool
    
    if _connection_pool:
        await _connection_pool.release(conn)