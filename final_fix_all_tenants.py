#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def fix_tenant(conn, schema):
    print(f"\n🔧 Fixing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Add missing columns to users table (if not exist)
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name='users' AND column_name='is_active') THEN
                ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name='users' AND column_name='created_by') THEN
                ALTER TABLE users ADD COLUMN created_by INTEGER REFERENCES users(id);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name='users' AND column_name='created_at') THEN
                ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END
        $$;
    """)
    
    # 2. Set all users active
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 3. Get admin role id
    admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
    if not admin_role_id:
        # Create admin role if missing (should not happen)
        admin_role_id = await conn.fetchval("""
            INSERT INTO roles (name, description) VALUES ('admin', 'Full access')
            ON CONFLICT (name) DO UPDATE SET name = 'admin' RETURNING id
        """)
    
    # 4. Assign all permissions to admin role
    permission_ids = await conn.fetch("SELECT id FROM permissions")
    for perm in permission_ids:
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, admin_role_id, perm['id'])
    
    # 5. Ensure the first user (admin) has admin role
    # Get the admin user (usually the one created with the schema)
    admin_user = await conn.fetchrow("SELECT id FROM users ORDER BY id LIMIT 1")
    if admin_user:
        await conn.execute("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, admin_user['id'], admin_role_id)
    
    # Also ensure any user with username 'admin' or the given admin username gets the role
    # But we already covered the first user.
    
    print(f"  ✅ Fixed for {schema} – assigned {len(permission_ids)} permissions to admin role")
    await conn.execute('SET search_path TO public')

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found! Please set .env file")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        # Get all schools
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        if not schools:
            print("No schools found in public.schools table.")
            return
        
        for school in schools:
            await fix_tenant(conn, school['subdomain'])
    
    await pool.close()
    print("\n✨ All tenants fixed! Restart your server and login as admin – now permissions should work.")

if __name__ == "__main__":
    asyncio.run(main())
