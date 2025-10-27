"""Quick test to verify Postgres connection without loading embedding models."""
import os
os.environ["USE_SQLITE"] = "false"

import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=15432,
        user="postgres",
        password="postgres",
        dbname="ecm_rag"
    )
    print("✅ Connected to Postgres successfully!")
    
    # Test creating tables
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"✅ Postgres version: {version[0][:50]}...")
    
    # List tables
    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public';")
    tables = cursor.fetchall()
    print(f"✅ Tables in database: {tables if tables else 'None yet (fresh DB)'}")
    
    cursor.close()
    conn.close()
    print("\n🎉 Database connection test PASSED!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
