#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os
import sys

# Load .env manually to avoid assertion error
load_dotenv(dotenv_path=".env", override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found. Check .env file")
    sys.exit(1)

async def fix_tenant(conn, schema, admin_username_from_school):
    print(f"\n🔧 Fixing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Ensure users table has is_active, created_by, created_at
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    # Set all users active
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 2. Create missing RBAC tables
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        );
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        );
    """)
    
    # 3. Insert default permissions
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
    
    # 4. Insert default roles
    await conn.execute("""
        INSERT INTO roles (name, description) VALUES
            ('admin', 'Full access to all features'),
            ('manager', 'Can manage inventory and view sales'),
            ('cashier', 'Can only process sales at POS'),
            ('viewer', 'Read-only access to reports')
        ON CONFLICT (name) DO NOTHING
    """)
    
    # 5. Get role ids
    admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
    pos_perm_id = await conn.fetchval("SELECT id FROM permissions WHERE name = 'pos_access'")
    all_perm_ids = await conn.fetch("SELECT id FROM permissions")
    
    # 6. Assign permissions to admin role (all permissions)
    if admin_role_id:
        for perm in all_perm_ids:
            await conn.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, admin_role_id, perm['id'])
        print(f"  → Assigned {len(all_perm_ids)} permissions to admin role")
    
    # 7. Assign only pos_access to manager, cashier, viewer (remove any other permissions)
    if pos_perm_id:
        for role_name in ['manager', 'cashier', 'viewer']:
            role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", role_name)
            if role_id:
                # Delete any existing permissions for this role
                await conn.execute("DELETE FROM role_permissions WHERE role_id = $1", role_id)
                # Add only pos_access
                await conn.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                """, role_id, pos_perm_id)
        print("  → Non-admin roles now have ONLY pos_access")
    
    # 8. Assign admin role to the appropriate user
    # Priority: 1) user with username = admin_username_from_school, 2) user 'admin', 3) first user
    admin_user_id = None
    if admin_username_from_school:
        admin_user_id = await conn.fetchval("SELECT id FROM users WHERE username = $1", admin_username_from_school)
    if not admin_user_id:
        admin_user_id = await conn.fetchval("SELECT id FROM users WHERE username = 'admin'")
    if not admin_user_id:
        admin_user_id = await conn.fetchval("SELECT id FROM users ORDER BY id LIMIT 1")
    
    if admin_user_id and admin_role_id:
        await conn.execute("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, admin_user_id, admin_role_id)
        print(f"  → Assigned admin role to user ID {admin_user_id}")
    else:
        print("  ⚠️ Could not find a user to assign admin role")
    
    await conn.execute('SET search_path TO public')
    print(f"✅ Schema {schema} fixed")

async def main():
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain, admin_username FROM public.schools")
        if not schools:
            print("No schools found in public.schools")
            return
        for school in schools:
            await fix_tenant(conn, school['subdomain'], school['admin_username'])
    await pool.close()
    print("\n✨ All tenants have been fully repaired!")
    print("\n📌 Next steps:")
    print("   1. Restart your server: uvicorn app.main:app --reload")
    print("   2. Clear browser cache or use incognito mode")
    print("   3. Login as admin at http://<school-subdomain>.localhost:8000/login")
    print("   4. Admin will see all tabs; sub-users (cashier etc.) will see only POS tab and have only pos_access permission")

if __name__ == "__main__":
    asyncio.run(main())
