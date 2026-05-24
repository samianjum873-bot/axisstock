#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def fix_all_tenants():
    if not DATABASE_URL:
        print("DATABASE_URL not found!")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with pool.acquire() as conn:
        # Get all schools
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        
        for school in schools:
            schema = school['subdomain']
            print(f"\n🔧 Fixing schema: {schema}")
            
            # Set search path to tenant schema
            await conn.execute(f'SET search_path TO "{schema}"')
            
            # Check if is_active column exists
            col_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='is_active'
                )
            """)
            
            if not col_exists:
                print(f"  ➕ Adding is_active column to {schema}.users")
                await conn.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
            else:
                print(f"  ✅ is_active already exists in {schema}")
            
            # Check if created_by column exists
            col_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='created_by'
                )
            """)
            
            if not col_exists:
                print(f"  ➕ Adding created_by column to {schema}.users")
                await conn.execute("ALTER TABLE users ADD COLUMN created_by INTEGER REFERENCES users(id)")
            else:
                print(f"  ✅ created_by already exists in {schema}")
            
            # Check if created_at column exists
            col_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='created_at'
                )
            """)
            
            if not col_exists:
                print(f"  ➕ Adding created_at column to {schema}.users")
                await conn.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            else:
                print(f"  ✅ created_at already exists in {schema}")
            
            # Also update any existing NULL is_active to TRUE
            await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
            
            print(f"  ✅ Completed for {schema}")
        
        # Reset search path
        await conn.execute('SET search_path TO public')
    
    await pool.close()
    print("\n✨ All tenant schemas fixed!")

if __name__ == "__main__":
    asyncio.run(fix_all_tenants())
