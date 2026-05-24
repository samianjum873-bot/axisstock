#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Complete table definitions (same as in create_tenant_schema)
TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "products": """
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            barcode TEXT UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            student_class TEXT,
            subject TEXT,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            tag TEXT,
            variation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "sales": """
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            receipt_number TEXT NOT NULL UNIQUE,
            student_name TEXT NOT NULL,
            father_name TEXT NOT NULL,
            cnic TEXT,
            student_class TEXT NOT NULL,
            phone_no TEXT NOT NULL,
            address TEXT,
            sale_type TEXT NOT NULL,
            total_amount REAL NOT NULL,
            cash_paid REAL DEFAULT 0.0,
            profit REAL DEFAULT 0.0,
            payment_status TEXT DEFAULT 'Paid',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "roles": """
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "permissions": """
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT
        )
    """,
    "user_roles": """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        )
    """,
    "role_permissions": """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )
    """,
    "sale_items": """
        CREATE TABLE IF NOT EXISTS sale_items (
            id SERIAL PRIMARY KEY,
            sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL
        )
    """
}

PERMISSIONS = [
    ('pos_access', 'pos', 'read', 'Access POS billing page'),
    ('inventory_read', 'inventory', 'read', 'View inventory'),
    ('inventory_write', 'inventory', 'write', 'Add/edit inventory items'),
    ('sales_read', 'sales', 'read', 'View sales history'),
    ('customers_read', 'customers', 'read', 'View customers'),
    ('analytics_read', 'analytics', 'read', 'View analytics reports'),
    ('users_manage', 'users', 'manage', 'Manage users and roles')
]

ROLES = {
    'admin': [p[0] for p in PERMISSIONS],
    'manager': ['pos_access', 'inventory_read', 'inventory_write', 'sales_read', 'customers_read', 'analytics_read'],
    'cashier': ['pos_access', 'sales_read'],
    'viewer': ['analytics_read']
}

async def repair_schema(conn, schema, admin_username_from_school=None):
    print(f"\n🔧 Repairing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Create all missing tables
    for table_name, ddl in TABLES.items():
        await conn.execute(ddl)
        print(f"  → Ensured table: {table_name}")
    
    # 2. Add missing columns to users (idempotent)
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 3. Add created_at to products if missing (some old tenants)
    await conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    # 4. Insert permissions
    for name, resource, action, desc in PERMISSIONS:
        await conn.execute("""
            INSERT INTO permissions (name, resource, action, description)
            VALUES ($1, $2, $3, $4) ON CONFLICT (name) DO NOTHING
        """, name, resource, action, desc)
    
    # 5. Insert roles
    for role_name in ROLES.keys():
        await conn.execute("""
            INSERT INTO roles (name, description) VALUES ($1, $2)
            ON CONFLICT (name) DO NOTHING
        """, role_name, f'{role_name.capitalize()} role')
    
    # 6. Assign permissions to roles
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
    
    # 7. Assign admin role to the correct user
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
        print(f"  ⚠️ No user found in this tenant")
    
    await conn.execute('SET search_path TO public')
    print(f"✅ Schema {schema} fully repaired")

async def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain, admin_username FROM public.schools")
        if not schools:
            print("No schools found.")
            return
        for school in schools:
            await repair_schema(conn, school['subdomain'], school['admin_username'])
    await pool.close()
    print("\n✨ All tenants have been fully repaired!")
    print("\n📌 RESTART YOUR SERVER NOW (Ctrl+C then uvicorn app.main:app --reload)")

if __name__ == "__main__":
    asyncio.run(main())
