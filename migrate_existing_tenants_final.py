#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate():
    if not DATABASE_URL:
        print("DATABASE_URL not set")
        return
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            schema = school['subdomain']
            print(f"Fixing {schema}...")
            await conn.execute(f'SET search_path TO "{schema}"')
            
            # Ensure permissions table and default entries exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    description TEXT
                );
                INSERT INTO permissions (name, resource, action, description) VALUES
                    ('pos_access', 'pos', 'read', 'Access POS billing page'),
                    ('inventory_read', 'inventory', 'read', 'View inventory'),
                    ('inventory_write', 'inventory', 'write', 'Add/edit inventory items'),
                    ('sales_read', 'sales', 'read', 'View sales history'),
                    ('customers_read', 'customers', 'read', 'View customers'),
                    ('analytics_read', 'analytics', 'read', 'View analytics reports'),
                    ('users_manage', 'users', 'manage', 'Manage users and roles')
                ON CONFLICT (name) DO NOTHING
            """)
            
            # Ensure roles exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO roles (name, description) VALUES
                    ('admin', 'Full access to all features'),
                    ('manager', 'Can manage inventory and view sales'),
                    ('cashier', 'Can only process sales at POS'),
                    ('viewer', 'Read-only access to reports')
                ON CONFLICT (name) DO NOTHING
            """)
            
            # Get ids
            admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
            pos_perm_id = await conn.fetchval("SELECT id FROM permissions WHERE name = 'pos_access'")
            all_perm_ids = await conn.fetch("SELECT id FROM permissions")
            
            # Admin gets all permissions
            if admin_role_id:
                for perm in all_perm_ids:
                    await conn.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """, admin_role_id, perm['id'])
            
            # Non-admin roles: delete all existing and add only pos_access
            if pos_perm_id:
                for role_name in ['manager', 'cashier', 'viewer']:
                    role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", role_name)
                    if role_id:
                        await conn.execute("DELETE FROM role_permissions WHERE role_id = $1", role_id)
                        await conn.execute("""
                            INSERT INTO role_permissions (role_id, permission_id)
                            VALUES ($1, $2) ON CONFLICT DO NOTHING
                        """, role_id, pos_perm_id)
            
            # Ensure the first user (school admin) has admin role
            first_user = await conn.fetchval("SELECT id FROM users ORDER BY id LIMIT 1")
            if first_user and admin_role_id:
                await conn.execute("""
                    INSERT INTO user_roles (user_id, role_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                """, first_user, admin_role_id)
            
            await conn.execute('SET search_path TO public')
            print(f"  ✅ {schema} fixed")
    await pool.close()
    print("\n✨ All tenants migrated successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
