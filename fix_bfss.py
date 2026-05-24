#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schema = "bfss"
        print(f"Fixing schema: {schema}")
        await conn.execute(f'SET search_path TO "{schema}"')
        
        # Check current columns
        cols = await conn.fetch("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='users' ORDER BY ordinal_position
        """)
        print("Current columns:", [c['column_name'] for c in cols])
        
        # Add missing columns one by one (with IF NOT EXISTS)
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        # Set is_active for all existing users
        await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
        
        # Ensure admin role has all permissions
        admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
        if admin_role_id:
            perms = await conn.fetch("SELECT id FROM permissions")
            for p in perms:
                await conn.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                """, admin_role_id, p['id'])
            print(f"Assigned {len(perms)} permissions to admin role")
        
        # Ensure first user (admin) has admin role
        first_user = await conn.fetchval("SELECT id FROM users ORDER BY id LIMIT 1")
        if first_user and admin_role_id:
            await conn.execute("""
                INSERT INTO user_roles (user_id, role_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, first_user, admin_role_id)
            print("Assigned admin role to first user")
        
        print(f"✅ Fixed {schema}")
    
    await pool.close()
    print("\n✨ bfss schema fixed. Restart your server and test admin login.")

if __name__ == "__main__":
    asyncio.run(main())
