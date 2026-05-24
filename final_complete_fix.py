#!/usr/bin/env python3
"""
Final comprehensive fix for all tenants:
- Creates missing RBAC tables (permissions, roles, user_roles, role_permissions)
- Inserts default roles and permissions
- Assigns all permissions to admin role
- Assigns admin role to the first user (admin)
- Adds missing columns to users table
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def fix_tenant(conn, schema):
    print(f"\n🔧 Repairing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Create permissions table if not exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT
        )
    """)
    
    # 2. Create roles table if not exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. Create user_roles table if not exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        )
    """)
    
    # 4. Create role_permissions table if not exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )
    """)
    
    # 5. Add missing columns to users table
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 6. Insert default roles (if not exist)
    await conn.execute("""
        INSERT INTO roles (name, description) VALUES
            ('admin', 'Full access to all features'),
            ('manager', 'Can manage inventory and view sales'),
            ('cashier', 'Can only process sales at POS'),
            ('viewer', 'Read-only access to reports')
        ON CONFLICT (name) DO NOTHING
    """)
    
    # 7. Insert default permissions (if not exist)
    await conn.execute("""
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
    
    # 8. Get admin role id
    admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
    if not admin_role_id:
        print(f"  ❌ Admin role not found – something is wrong")
        return
    
    # 9. Assign ALL permissions to admin role
    perm_ids = await conn.fetch("SELECT id FROM permissions")
    for p in perm_ids:
        await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, admin_role_id, p['id'])
    print(f"  → Assigned {len(perm_ids)} permissions to admin role")
    
    # 10. Ensure the admin user (first user) has admin role
    # Try to find user named 'admin' or the first user
    admin_user = await conn.fetchrow("SELECT id FROM users WHERE username = 'admin'")
    if not admin_user:
        admin_user = await conn.fetchrow("SELECT id FROM users ORDER BY id LIMIT 1")
    if admin_user:
        await conn.execute("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, admin_user['id'], admin_role_id)
        print(f"  → Assigned admin role to user ID {admin_user['id']}")
    else:
        print(f"  ⚠️ No user found in this tenant – cannot assign admin role")
    
    await conn.execute('SET search_path TO public')
    print(f"✅ Schema {schema} fixed successfully")

async def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env file")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        if not schools:
            print("No schools found in public.schools. Are there any tenants?")
            return
        
        for school in schools:
            await fix_tenant(conn, school['subdomain'])
    
    await pool.close()
    print("\n✨ All tenants fixed successfully!")
    print("\n📌 Restart your uvicorn server now:")
    print("   Press Ctrl+C then run: uvicorn app.main:app --reload")
    print("\n✅ Admin should now have full access to all pages.")

if __name__ == "__main__":
    asyncio.run(main())
