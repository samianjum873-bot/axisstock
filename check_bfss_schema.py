#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def check_bfss():
    if not DATABASE_URL:
        print("DATABASE_URL not found!")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with pool.acquire() as conn:
        # Set search path to bfss schema
        await conn.execute('SET search_path TO "bfss"')
        
        # Check columns
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            ORDER BY ordinal_position
        """)
        
        print("\n📊 Columns in bfss.users:")
        for col in columns:
            print(f"  - {col['column_name']} ({col['data_type']})")
        
        # Check if is_active column actually exists by trying a simple query
        try:
            result = await conn.fetch("SELECT is_active FROM users LIMIT 1")
            print(f"\n✅ is_active column exists and query works!")
        except Exception as e:
            print(f"\n❌ Error querying is_active: {e}")
        
        # Reset search path
        await conn.execute('SET search_path TO public')
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(check_bfss())
