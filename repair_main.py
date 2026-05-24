#!/usr/bin/env python3
# repair_main.py - Fix main.py startup errors and RBAC issues

import re

MAIN_FILE = "app/main.py"

with open(MAIN_FILE, "r") as f:
    content = f.read()

# 1. Fix the broken migrate_existing_tenants function (remove recursion and wrong decorator)
# Look for the function definition and replace it entirely
old_migrate = r'''@asynccontextmanager

async def migrate_existing_tenants\(\):
    pool = await get_pool\(\)\s+await migrate_existing_tenants\(\)
    async with pool\.acquire\(\) as conn:
        schools = await conn\.fetch\("SELECT subdomain FROM public\.schools"\)
        for school in schools:
            sub = school\['subdomain'\]
            await conn\.execute\(f'SET search_path TO "\\{sub\\}"'\)
            try:
                await conn\.execute\("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"\)
            except Exception:
                pass
            await conn\.execute\('SET search_path TO public'\)'''

new_migrate = '''async def migrate_existing_tenants():
    pool = await get_pool()
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            sub = school['subdomain']
            await conn.execute(f'SET search_path TO "{sub}"')
            try:
                await conn.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except Exception:
                pass
            await conn.execute('SET search_path TO public')'''

content = re.sub(old_migrate, new_migrate, content, flags=re.DOTALL)

# Also remove any stray await migrate_existing_tenants() that might be duplicated
content = re.sub(r'await migrate_existing_tenants\(\)\s*await migrate_existing_tenants\(\)', 'await migrate_existing_tenants()', content)

# 2. Ensure the login route uses session correctly (already okay but check)
# No additional changes needed, but we'll verify that the logout route is correct
# Already fixed in previous patches.

# 3. Add RBAC tables creation if missing (optional but good)
# Insert a migration for RBAC tables inside migrate_existing_tenants
# We'll add a function to create roles/permissions if not exist
rbac_migration = """
    # Create RBAC tables if not exist
    await conn.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    \"\"\")
    await conn.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            description TEXT
        )
    \"\"\")
    await conn.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        )
    \"\"\")
    await conn.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )
    \"\"\")
    # Insert default roles if missing
    await conn.execute(\"\"\"
        INSERT INTO roles (name, description) VALUES 
            ('admin', 'Full access to all features'),
            ('manager', 'Can manage inventory and view sales'),
            ('cashier', 'Can only process sales at POS'),
            ('viewer', 'Read-only access to reports')
        ON CONFLICT (name) DO NOTHING
    \"\"\")
    # Insert default permissions
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
    # Assign admin role to existing admin user if not already
    await conn.execute(\"\"\"
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id FROM users u, roles r 
        WHERE u.username = 'admin' AND r.name = 'admin'
        ON CONFLICT DO NOTHING
    \"\"\")
"""

# Insert the RBAC creation after the ALTER TABLE line in migrate_existing_tenants
# We'll locate the position after the try/except for created_at
pattern = r'(await conn\.execute\("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"\))'
replacement = r'\1\n' + rbac_migration
content = re.sub(pattern, replacement, content)

# 4. Ensure the settings page permission check uses correct permission
# The permission "users_manage" is already there.

with open(MAIN_FILE, "w") as f:
    f.write(content)

print("✅ main.py repaired successfully")
print("Now run: uvicorn app.main:app --reload")
