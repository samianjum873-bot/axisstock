#!/usr/bin/env python3
import re
import os

# 1. Restore database.py to a known working version (with correct role_permissions)
db_content = '''import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

import bcrypt

pool = None

async def init_db_pool():
    global pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable not set")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return pool

async def get_pool():
    global pool
    if pool is None:
        await init_db_pool()
    return pool

async def create_tenant_schema(schema_name: str, admin_username: str, admin_password: str):
    global pool
    if pool is None:
        await init_db_pool()
    async with pool.acquire() as conn:
        safe_schema = schema_name.replace('"', '').replace("'", "")
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{safe_schema}"')
        await conn.execute(f'SET search_path TO "{safe_schema}"')
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
        hashed_pw = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        await conn.execute("""
            INSERT INTO users (username, password_hash) VALUES ($1, $2)
            ON CONFLICT (username) DO NOTHING;
        """, admin_username, hashed_pw)

        # Insert default roles and permissions
        await conn.execute("""
            INSERT INTO roles (name, description) VALUES
                ('admin', 'Full access to all features'),
                ('manager', 'Can manage inventory and view sales'),
                ('cashier', 'Can only process sales at POS'),
                ('viewer', 'Read-only access to reports')
            ON CONFLICT (name) DO NOTHING
        """)
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
        
        # Assign permissions: admin gets all, others get only pos_access
        admin_role = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
        pos_perm = await conn.fetchval("SELECT id FROM permissions WHERE name = 'pos_access'")
        if admin_role:
            all_perms = await conn.fetch("SELECT id FROM permissions")
            for perm in all_perms:
                await conn.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                """, admin_role, perm['id'])
        if pos_perm:
            for role_name in ['manager', 'cashier', 'viewer']:
                role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", role_name)
                if role_id:
                    await conn.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """, role_id, pos_perm)
        
        # Assign admin role to the first user (school admin)
        await conn.execute("""
            INSERT INTO user_roles (user_id, role_id)
            SELECT u.id, r.id FROM users u, roles r
            WHERE u.username = $1 AND r.name = 'admin'
            ON CONFLICT DO NOTHING
        """, admin_username)

        await conn.execute('SET search_path TO public')

async def tenant_exists(subdomain: str) -> bool:
    global pool
    if pool is None:
        await init_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT 1 FROM public.schools WHERE subdomain = $1", subdomain) is not None
'''

with open("app/database.py", "w") as f:
    f.write(db_content)
print("✅ Restored database.py")

# 2. Restore main.py – remove any custom middleware and add role to templates
with open("app/main.py", "r") as f:
    main_content = f.read()

# Remove any PermissionMiddleware class and its addition
lines = main_content.splitlines()
new_lines = []
skip = False
for line in lines:
    if "class PermissionMiddleware" in line or "app.add_middleware(PermissionMiddleware)" in line:
        skip = True
        continue
    if skip and line.strip() == "":
        skip = False
        continue
    if skip:
        continue
    new_lines.append(line)
main_content = "\n".join(new_lines)

# Also remove any other added middleware that might cause issues
# Ensure session middleware is present and TenantMiddleware is after it? Actually order should be: TenantMiddleware first, then SessionMiddleware.
# But the original order was correct: TenantMiddleware then SessionMiddleware. We'll keep as is.

# Now ensure that routes that render templates pass the user's role.
# We'll add code after login to store role in session and then pass to templates.

# Find the do_login function and ensure role is stored in session (already does)
# Then find each route that returns TemplateResponse and add "role": request.session.get("role") to context.

def add_role_to_template(content, route_name):
    # Find the function definition for route_name and modify its return to include role
    pattern = rf'(@app\.(get|post)\("[^"]*"\)\s+async def {route_name}\(request: Request\):.*?return templates\.TemplateResponse\(request,\s*"[^"]+",\s*\{{(.*?)\}}\)'
    def replacer(match):
        func = match.group(0)
        dict_part = match.group(2)
        if 'role' not in dict_part:
            if dict_part.strip():
                new_dict = dict_part + ', "role": request.session.get("role")'
            else:
                new_dict = '"role": request.session.get("role")'
            return func.replace('{' + dict_part + '}', '{' + new_dict + '}')
        return func
    new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    return new_content

routes_to_fix = ['index', 'pos_page', 'inventory_page', 'sales_page', 'list_registered_customers', 'operations_analytics_dashboard', 'settings_page']
for route in routes_to_fix:
    main_content = add_role_to_template(main_content, route)

# Also handle the base index route (the one with @app.get("/"))
# The above pattern should catch that.

with open("app/main.py", "w") as f:
    f.write(main_content)
print("✅ Patched main.py – removed bad middleware and added role to template contexts")

# 3. Update index.html sidebar to show based on role (admin vs non-admin)
with open("app/templates/index.html", "r") as f:
    html = f.read()

# Replace the nav block with conditional based on role
new_nav = '''
        <nav class="flex-1 mt-6 px-4 space-y-2">
            <!-- POS tab - always show -->
            <a href="/pos" id="link-pos" class="sidebar-link {% if active_page == 'pos' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-calculator w-8"></i> <span class="font-bold text-xs">COUNTER BILLING</span>
            </a>
            {% if role == 'admin' %}
            <a href="/inventory" id="link-inventory" class="sidebar-link {% if active_page == 'inventory' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-box-open w-8"></i> <span class="font-bold text-xs">STOCK MANAGER</span>
            </a>
            <a href="/sales" id="link-sales" class="sidebar-link {% if active_page == 'sales' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-history w-8"></i> <span class="font-bold text-xs">SALES HISTORY</span>
            </a>
            <a href="/customers" id="link-customers" class="sidebar-link {% if active_page == 'customers' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-users w-8"></i> <span class="font-bold text-xs">CUSTOMER DATABASE</span>
            </a>
            <a href="/analytics" id="link-analytics" class="sidebar-link {% if active_page == 'analytics' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-chart-pie w-8 text-yellow-400"></i> <span class="font-bold text-xs text-yellow-400">REPORTS & ANALYTICS</span>
            </a>
            <a href="/settings" id="link-settings" class="sidebar-link w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-cog w-8"></i> <span class="font-bold text-xs">SETTINGS</span>
            </a>
            {% endif %}
        </nav>
'''

html = re.sub(r'<nav class="flex-1 mt-6 px-4 space-y-2">.*?</nav>', new_nav, html, flags=re.DOTALL)

with open("app/templates/index.html", "w") as f:
    f.write(html)
print("✅ Updated index.html – sidebar conditional on role (admin vs others)")

print("\n✨ All fixes applied. Restart the server with: uvicorn app.main:app --reload")
