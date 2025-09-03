#!/usr/bin/env python3
"""
Database migration runner for Trellis Takehome.
Applies SQL migration files to the PostgreSQL database.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Database connection settings from docker-compose.yml
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "user": "trellis", 
    "password": "trellis",
    "database": "trellis"
}

async def run_migration_file(conn, migration_file: Path):
    """Run a single migration file."""
    print(f"🔄 Running migration: {migration_file.name}")
    
    try:
        with open(migration_file, 'r') as f:
            sql_content = f.read()
        
        # Execute the migration
        await conn.execute(sql_content)
        print(f"✅ Successfully applied: {migration_file.name}")
        
    except Exception as e:
        print(f"❌ Failed to apply {migration_file.name}: {e}")
        raise

async def create_migrations_table(conn):
    """Create a table to track applied migrations."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

async def get_applied_migrations(conn):
    """Get list of already applied migrations."""
    try:
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        return {row['version'] for row in rows}
    except:
        return set()

async def mark_migration_applied(conn, version: str):
    """Mark a migration as applied."""
    await conn.execute(
        "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
        version
    )

async def run_migrations():
    """Run all pending migrations."""
    print("🚀 Starting database migrations...")
    
    # Get migrations directory
    migrations_dir = Path(__file__).parent / "migrations"
    
    if not migrations_dir.exists():
        print("❌ Migrations directory not found!")
        return False
    
    # Get all .sql files
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    if not migration_files:
        print("⚠️  No migration files found!")
        return True
    
    try:
        # Connect to database
        print(f"🔌 Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Create migrations tracking table
        await create_migrations_table(conn)
        
        # Get already applied migrations
        applied = await get_applied_migrations(conn)
        
        # Run pending migrations
        for migration_file in migration_files:
            version = migration_file.stem  # e.g., "001_init"
            
            if version in applied:
                print(f"⏭️  Skipping already applied: {migration_file.name}")
                continue
            
            await run_migration_file(conn, migration_file)
            await mark_migration_applied(conn, version)
        
        await conn.close()
        print("🎉 All migrations completed successfully!")
        return True
        
    except asyncpg.exceptions.ConnectionError as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure PostgreSQL is running: docker compose up -d")
        return False
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

async def test_connection():
    """Test database connection and show table info."""
    print("🧪 Testing database connection...")
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        
        # Test basic query
        result = await conn.fetchval("SELECT version()")
        print(f"✅ Connected to: {result}")
        
        # Show tables
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        
        if tables:
            print("📊 Tables in database:")
            for table in tables:
                print(f"   - {table['tablename']}")
        else:
            print("📭 No tables found (run migrations first)")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test connection only
        success = asyncio.run(test_connection())
    else:
        # Run migrations
        success = asyncio.run(run_migrations())
    
    sys.exit(0 if success else 1)