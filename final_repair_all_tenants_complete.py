#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Permission definitions
PERMISSIONS = [
    ('pos_access', 'pos', 'read', 'Access POS billing page'),
    ('inventory_read', 'inventory', 'read', 'View inventory'),
    ('inventory_write', 'inventory', 'write', 'Add/edit inventory items'),
    ('sales_read', 'sales', 'read', 'View sales history'),
    ('customers_read', 'customers', 'read', 'View customers'),
    ('analytics_read', 'analytics', 'read', 'View analytics reports'),
    ('users_manage', 'users', 'manage', 'Manage users and roles'),
]

ROLES = {
    'admin': ['pos_access', 'inventory_read', 'inventory_write', 'sales_read', 'customers_read', 'analytics_read', 'users_manage'],
    'manager': ['pos_access', 'inventory_read', 'inventory_write', 'sales_read', 'customers_read', 'analytics_read'],
    'cashier': ['pos_access', 'sales_read'],
    'viewer': ['analytics_read'],
}

async def repair_tenant(conn, schema, admin_username_from_school=None):
    print(f"\n🔧 Repairing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Create missing RBAC tables
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
    
    # 2. Add missing columns to users table
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 3. Insert permissions (if not exist)
    for name, resource, action, desc in PERMISSIONS:
        await conn.execute("""
            INSERT INTO permissions (name, resource, action, description)
            VALUES ($1, $2, $3, $4) ON CONFLICT (name) DO NOTHING
        """, name, resource, action, desc)
    
    # 4. Insert roles
    for role_name in ROLES.keys():
        await conn.execute("""
            INSERT INTO roles (name, description) VALUES ($1, $2)
            ON CONFLICT (name) DO NOTHING
        """, role_name, f'{role_name.capitalize()} role')
    
    # 5. Assign permissions to roles
    for role_name, perms in ROLES.items():
        role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", role_name)
        if role_id:
            for perm_name in perms:
                perm_id = await conn.fetchval("SELECT id FROM permissions WHERE name = $1", perm_name)
                if perm_id:
                    await conn.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """, role_id, perm_id)
    
    # 6. Assign admin role to the appropriate user
    # First try: user with username 'admin' (common for demo)
    # Second: first user in the tenant
    # Third: if admin_username_from_school provided, use that
    admin_user_id = await conn.fetchval("SELECT id FROM users WHERE username = 'admin'")
    if not admin_user_id:
        admin_user_id = await conn.fetchval("SELECT id FROM users ORDER BY id LIMIT 1")
    if not admin_user_id and admin_username_from_school:
        admin_user_id = await conn.fetchval("SELECT id FROM users WHERE username = $1", admin_username_from_school)
    
    if admin_user_id:
        admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
        if admin_role_id:
            await conn.execute("""
                INSERT INTO user_roles (user_id, role_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, admin_user_id, admin_role_id)
            print(f"  → Assigned admin role to user ID {admin_user_id}")
    else:
        print(f"  ⚠️ No user found in this tenant!")
    
    # 7. Optional: ensure the creator (super admin) also has admin role in each tenant? Not needed.
    
    await conn.execute('SET search_path TO public')
    print(f"✅ Schema {schema} fixed")

async def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        # Get all schools with their admin username (from public.schools)
        schools = await conn.fetch("SELECT subdomain, admin_username FROM public.schools")
        if not schools:
            print("No schools found in public.schools.")
            return
        
        for school in schools:
            await repair_tenant(conn, school['subdomain'], school['admin_username'])
    
    await pool.close()
    print("\n✨ All tenants repaired successfully!")
    print("\n📌 RESTART YOUR SERVER NOW: Press Ctrl+C then run:")
    print("   uvicorn app.main:app --reload")
    print("\n✅ After restart, admin and sub-users will have correct permissions.")
    print("   Cashier will be able to access POS page.\n")

if __name__ == "__main__":
    asyncio.run(main())
