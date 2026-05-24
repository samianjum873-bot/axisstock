#!/usr/bin/env python3
import asyncio
import bcrypt
from app.database import get_pool, init_db_pool

async def setup_rbac():
    await init_db_pool()
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get all schools
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            sub = school['subdomain']
            print(f"Setting up RBAC for {sub}...")
            await conn.execute(f'SET search_path TO "{sub}"')

            # Create tables if not exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    description TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                    PRIMARY KEY (user_id, role_id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
                    PRIMARY KEY (role_id, permission_id)
                )
            """)

            # Insert default roles
            await conn.execute("""
                INSERT INTO roles (name, description) VALUES
                    ('admin', 'Full access to all features'),
                    ('manager', 'Can manage inventory and view sales'),
                    ('cashier', 'Can only process sales at POS'),
                    ('viewer', 'Read-only access to reports')
                ON CONFLICT (name) DO NOTHING
            """)

            # Insert default permissions
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

            # Assign admin role to the 'admin' user if exists
            await conn.execute("""
                INSERT INTO user_roles (user_id, role_id)
                SELECT u.id, r.id FROM users u, roles r
                WHERE u.username = 'admin' AND r.name = 'admin'
                ON CONFLICT DO NOTHING
            """)

            await conn.execute('SET search_path TO public')
    print("✅ RBAC tables created for all tenants.")

# Also patch database.py to include RBAC tables for new tenants
print("Patching database.py to include RBAC tables in new tenant schemas...")
db_file = "app/database.py"
with open(db_file, "r") as f:
    content = f.read()

# Add RBAC table creation after the products table
rbac_tables = """
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
"""
# Insert after the sale_items table creation (or before it)
content = content.replace(
    "CREATE TABLE IF NOT EXISTS sale_items (",
    rbac_tables + "\n            CREATE TABLE IF NOT EXISTS sale_items ("
)

# Also add default role/permission inserts after user creation
defaults = """
        # Insert default roles and permissions for new tenant
        await conn.execute(\"\"\"
            INSERT INTO roles (name, description) VALUES
                ('admin', 'Full access to all features'),
                ('manager', 'Can manage inventory and view sales'),
                ('cashier', 'Can only process sales at POS'),
                ('viewer', 'Read-only access to reports')
            ON CONFLICT (name) DO NOTHING
        \"\"\")
        await conn.execute(\"\"\"
            INSERT INTO permissions (name, resource, action, description) VALUES
                ('pos_access', 'pos', 'read', 'Access POS billing page'),
                ('inventory_read', 'inventory', 'read', 'View inventory'),
                ('inventory_write', 'inventory', 'write', 'Add/edit inventory items'),
                ('sales_read', 'sales', 'read', 'View sales history'),
                ('customers_read', 'customers', 'read', 'View customers'),
                ('analytics_read', 'analytics', 'read', 'View analytics reports'),
                ('users_manage', 'users', 'manage', 'Manage users and roles')
            ON CONFLICT (name) DO NOTHING
        \"\"\")
        # Assign admin role to the first user
        await conn.execute(\"\"\"
            INSERT INTO user_roles (user_id, role_id)
            SELECT u.id, r.id FROM users u, roles r
            WHERE u.username = $1 AND r.name = 'admin'
            ON CONFLICT DO NOTHING
        \"\"\", admin_username)
"""
old_insert = 'await conn.execute("""\n            INSERT INTO users (username, password_hash) VALUES ($1, $2)\n            ON CONFLICT (username) DO NOTHING;\n        """, admin_username, hashed_pw)'
new_insert = old_insert + "\n" + defaults
content = content.replace(old_insert, new_insert)

with open(db_file, "w") as f:
    f.write(content)
print("✅ database.py updated to create RBAC tables for new tenants.")

# Run the setup
asyncio.run(setup_rbac())

print("\n🎉 Done! Restart your app: uvicorn app.main:app --reload")
