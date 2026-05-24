#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ============================================================
# Complete repair: create missing tables & set permissions
# ============================================================

async def repair_tenant(conn, schema, admin_username_from_school):
    print(f"\n🔧 Repairing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Create all tables if they don't exist (idempotent)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
        );
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
        );
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT
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
        CREATE TABLE IF NOT EXISTS sale_items (
            id SERIAL PRIMARY KEY,
            sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL
        );
    """)
    
    # 2. Add missing columns to users (just in case)
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 3. Insert default roles (if not exist)
    await conn.execute("""
        INSERT INTO roles (name, description) VALUES
            ('admin', 'Full access to all features'),
            ('manager', 'Can manage inventory and view sales'),
            ('cashier', 'Can only process sales at POS'),
            ('viewer', 'Read-only access to reports')
        ON CONFLICT (name) DO NOTHING
    """)
    
    # 4. Insert default permissions (if not exist)
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
    
    # 5. Get role ids
    admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
    pos_perm_id = await conn.fetchval("SELECT id FROM permissions WHERE name = 'pos_access'")
    all_perms = await conn.fetch("SELECT id FROM permissions")
    
    # 6. Assign all permissions to admin role
    if admin_role_id:
        for perm in all_perms:
            await conn.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, admin_role_id, perm['id'])
        print(f"  → Assigned {len(all_perms)} permissions to admin role")
    
    # 7. Assign only pos_access to manager, cashier, viewer (remove any other permissions)
    if pos_perm_id:
        for role_name in ['manager', 'cashier', 'viewer']:
            role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", role_name)
            if role_id:
                await conn.execute("DELETE FROM role_permissions WHERE role_id = $1", role_id)
                await conn.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                """, role_id, pos_perm_id)
        print("  → Non-admin roles now have ONLY pos_access")
    
    # 8. Assign admin role to the correct user
    # Priority: 1) admin_username_from_school, 2) 'admin', 3) first user
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
    print(f"✅ Schema {schema} fully repaired")

async def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found. Check .env file")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain, admin_username FROM public.schools")
        if not schools:
            print("No schools found in public.schools")
            return
        for school in schools:
            await repair_tenant(conn, school['subdomain'], school['admin_username'])
    await pool.close()
    print("\n✨ All tenants have been fully repaired!")
    print("\n📌 Next steps:")
    print("   1. Restart your server: uvicorn app.main:app --reload")
    print("   2. Clear browser cache or use incognito mode")
    print("   3. Login as admin – you will see all tabs")
    print("   4. Sub‑users (cashier, manager, viewer) will see only the COUNTER BILLING tab")
    print("   5. Only one active session per browser (already handled by session cookies)")

if __name__ == "__main__":
    asyncio.run(main())
