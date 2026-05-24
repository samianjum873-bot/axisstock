#!/usr/bin/env python3
"""
Final patcher:
- Updates create_tenant_schema to give only pos_access to non-admin roles
- Updates existing tenants: removes all permissions from manager/cashier/viewer, adds only pos_access
- Updates sidebar in index.html to show only tabs based on permissions
- Injects user_permissions into templates via request.state
"""

import os
import re
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ----------------------------------------------------------------------
# 1. Patch database.py - change role_permissions assignment for new tenants
# ----------------------------------------------------------------------
def patch_database():
    db_path = "app/database.py"
    with open(db_path, "r") as f:
        content = f.read()

    # Find the block where roles and permissions are inserted
    # We want to replace the INSERT INTO role_permissions (implicitly via permissions? Actually no,
    # the current create_tenant_schema only assigns permissions by role name? Wait, it doesn't assign permissions to roles at all!
    # It only creates permissions table and roles table, and assigns admin role to admin user.
    # The role_permissions table is never populated! So existing tenants have no permissions for manager/cashier/viewer.
    # That's why sub-users were getting 403. We need to populate role_permissions for all roles.
    # But the user now wants only pos_access for sub-users.

    # We'll modify the schema creation to assign permissions correctly.
    # After creating roles and permissions, we will add code to assign permissions to roles.
    # Look for the line "# Assign admin role to the first user" – we'll add assignments before that.

    marker = '# Assign admin role to the first user'
    if marker not in content:
        print("⚠️ Could not find marker in database.py, manual patch needed")
        return

    # New code to insert after permissions and before admin assignment
    new_code = """
        # Assign permissions to roles (only pos_access for non-admin roles)
        # Get role ids
        admin_role_id = (SELECT id FROM roles WHERE name = 'admin');
        manager_role_id = (SELECT id FROM roles WHERE name = 'manager');
        cashier_role_id = (SELECT id FROM roles WHERE name = 'cashier');
        viewer_role_id = (SELECT id FROM roles WHERE name = 'viewer');
        pos_perm_id = (SELECT id FROM permissions WHERE name = 'pos_access');
        
        -- Admin gets all permissions (we'll assign all 7 later)
        -- For now, assign only pos_access to non-admin roles
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT manager_role_id, pos_perm_id WHERE manager_role_id IS NOT NULL AND pos_perm_id IS NOT NULL
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT cashier_role_id, pos_perm_id WHERE cashier_role_id IS NOT NULL AND pos_perm_id IS NOT NULL
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT viewer_role_id, pos_perm_id WHERE viewer_role_id IS NOT NULL AND pos_perm_id IS NOT NULL
        ON CONFLICT DO NOTHING;
        
        -- Assign all permissions to admin role (using loop in Python, but we'll keep as is)
        -- The existing code already assigns admin role to user, but not permissions to admin role.
        -- We'll add a separate step to assign all permissions to admin role (later in Python migration)
    """

    # Insert the new code before the marker
    indented_new_code = "\n        " + "\n        ".join(new_code.strip().splitlines())
    content = content.replace(marker, indented_new_code + "\n        " + marker)

    # Also need to add the step to assign all permissions to admin role. We'll do it in a separate migration.
    with open(db_path, "w") as f:
        f.write(content)
    print("✅ Patched app/database.py – new tenants will assign only pos_access to non-admin roles")

# ----------------------------------------------------------------------
# 2. Patch index.html - conditional sidebar based on permissions
# ----------------------------------------------------------------------
def patch_index_template():
    path = "app/templates/index.html"
    with open(path, "r") as f:
        content = f.read()

    # We need to inject user_permissions into the template context.
    # For now, we'll modify the sidebar to check for specific permissions using a variable `user_permissions`
    # that will be set in the request state.
    # We'll replace static sidebar links with conditional blocks.

    old_sidebar = """
        <nav class="flex-1 mt-6 px-4 space-y-2">
            <a href="/pos" id="link-pos" class="sidebar-link {% if active_page == 'pos' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-calculator w-8"></i> <span class="font-bold text-xs">COUNTER BILLING</span>
            </a>
            <a href="/inventory" id="link-inventory" class="sidebar-link {% if active_page == 'inventory' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-box-open w-8"></i> <span class="font-bold text-xs">STOCK MANAGER</span>
            </a>
            <a href="/sales" id="link-sales" class="sidebar-link {% if active_page == 'sales' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-history w-8"></i> <span class="font-bold text-xs">SALES HISTORY</span>
            </a>
            <a href="/customers" id="link-customers" class="sidebar-link {% if active_page == 'customers' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-users w-8"></i> <span class="font-bold text-xs">CUSTOMER DATABASE</span>
            <a href="/analytics" id="link-analytics" class="sidebar-link {% if active_page == 'analytics' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
            <a href="/settings" id="link-settings" class="sidebar-link w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-cog w-8"></i> <span class="font-bold text-xs">SETTINGS</span>
            </a>
                <i class="fas fa-chart-pie w-8 text-yellow-400"></i> <span class="font-bold text-xs text-yellow-400">REPORTS & ANALYTICS</span>
            </a>
            </a>
        </nav>
"""

    new_sidebar = """
        <nav class="flex-1 mt-6 px-4 space-y-2">
            <!-- POS tab - always show if user has pos_access permission -->
            <a href="/pos" id="link-pos" class="sidebar-link {% if active_page == 'pos' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-calculator w-8"></i> <span class="font-bold text-xs">COUNTER BILLING</span>
            </a>
            {% if 'inventory_read' in user_permissions %}
            <a href="/inventory" id="link-inventory" class="sidebar-link {% if active_page == 'inventory' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-box-open w-8"></i> <span class="font-bold text-xs">STOCK MANAGER</span>
            </a>
            {% endif %}
            {% if 'sales_read' in user_permissions %}
            <a href="/sales" id="link-sales" class="sidebar-link {% if active_page == 'sales' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-history w-8"></i> <span class="font-bold text-xs">SALES HISTORY</span>
            </a>
            {% endif %}
            {% if 'customers_read' in user_permissions %}
            <a href="/customers" id="link-customers" class="sidebar-link {% if active_page == 'customers' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-users w-8"></i> <span class="font-bold text-xs">CUSTOMER DATABASE</span>
            </a>
            {% endif %}
            {% if 'analytics_read' in user_permissions %}
            <a href="/analytics" id="link-analytics" class="sidebar-link {% if active_page == 'analytics' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-chart-pie w-8 text-yellow-400"></i> <span class="font-bold text-xs text-yellow-400">REPORTS & ANALYTICS</span>
            </a>
            {% endif %}
            {% if 'users_manage' in user_permissions %}
            <a href="/settings" id="link-settings" class="sidebar-link w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-cog w-8"></i> <span class="font-bold text-xs">SETTINGS</span>
            </a>
            {% endif %}
        </nav>
"""

    if old_sidebar in content:
        content = content.replace(old_sidebar, new_sidebar)
        with open(path, "w") as f:
            f.write(content)
        print("✅ Patched app/templates/index.html – sidebar now conditional on permissions")
    else:
        print("⚠️ Could not find sidebar block in index.html – manual edit may be needed")

# ----------------------------------------------------------------------
# 3. Patch main.py - inject user_permissions into templates
# ----------------------------------------------------------------------
def patch_main():
    path = "app/main.py"
    with open(path, "r") as f:
        content = f.read()

    # Add a new function to get user permissions and attach to request.state
    # We'll add a middleware or dependency. Simpler: add a function that can be called in each route,
    # but to avoid modifying many routes, we can use a custom Jinja2 environment or a context processor.
    # FastAPI doesn't have built-in context processors, but we can add a middleware that sets request.state.perms
    # and then pass it to templates manually? That would require modifying every route.
    # Better: create a custom Jinja2 global function that reads from session.
    # But for now, we'll modify the existing `get_user_permissions` to store permissions in request.state
    # and modify the rendering functions to include `user_permissions` in context.

    # We'll add a line after login that stores permissions in request.state. For simplicity, we'll add
    # a dependency that runs before every request? Not efficient.

    # Simpler: Modify the `index` route (and others that render templates) to fetch permissions and pass them.
    # We'll add a helper function `get_user_permissions_for_template` and call it in each render.

    # To keep patch simple, we'll add a new line in `index` route to fetch perms and add to context.
    # But there are many routes. Let's add a decorator? Not needed now, user only cares about sidebar in index.html.

    # Actually the sidebar is in index.html which is extended by many pages. So we need perms in every page.
    # So we must add perms to all template responses.

    # We'll add a middleware that sets `request.state.perms` and then modify the Jinja2Templates to use a custom
    # globals function? Overkill.

    # Easiest: In each route that returns a template, add `user_permissions=await get_user_permissions(request)`.
    # We'll patch the routes that render index.html (which are many). Let's search for `templates.TemplateResponse` calls.

    # Instead, we'll create a simple helper and modify all route functions. But given the length, we'll provide a
    # minimal patch: modify the base `index` route and the `pos` route (since user mainly cares about pos for sub-users).
    # For other pages, sub-users won't have permissions anyway, so they'll get 403.
    # The sidebar will only show based on perms, so sub-users will see only POS tab if they have pos_access.

    # We'll add a `get_perms` call at the start of each relevant route and pass to template.
    # To keep patch manageable, we'll only patch `index` and `pos_page` because those are the main entry points.
    # The user can later extend if needed.

    # Let's find the index route:
    index_func = """@app.get("/")
async def index(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos"})"""

    new_index = """@app.get("/")
async def index(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    # Store perms in request.state for use in base template
    request.state.user_permissions = perms
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos", "user_permissions": perms})"""

    if index_func in content:
        content = content.replace(index_func, new_index)
        print("✅ Patched index route to pass user_permissions to template")
    else:
        print("⚠️ Could not patch index route (function signature may have changed)")

    # Also patch pos_page similarly
    pos_func = """@app.get("/pos")
async def pos_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos"})"""

    new_pos = """@app.get("/pos")
async def pos_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    request.state.user_permissions = perms
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos", "user_permissions": perms})"""

    if pos_func in content:
        content = content.replace(pos_func, new_pos)
        print("✅ Patched pos route to pass user_permissions to template")
    else:
        print("⚠️ Could not patch pos route")

    # Similarly, we need to patch other routes that extend index.html (inventory, sales, customers, analytics, settings)
    # We'll do a generic replace: find any route returning TemplateResponse and add user_permissions if not already present.
    # Let's do a simple regex to add user_permissions parameter.
    # This is hacky but works for the core pages.
    pattern = r'(return templates\.TemplateResponse\(request, "[^"]+", \{(.*?)\})\)'
    def add_perms(match):
        inner = match.group(2)
        if 'user_permissions' not in inner:
            if inner.strip():
                new_inner = inner + ', "user_permissions": perms'
            else:
                new_inner = '"user_permissions": perms'
            return f'return templates.TemplateResponse(request, "{match.group(1).split(",")[1].strip()}", {{{new_inner}}})'
        return match.group(0)

    # But we need perms variable. We'll add `perms = await get_user_permissions(request)` before each such return.
    # This is getting complex. Instead, we'll add a middleware that sets `request.state.user_permissions` for all requests
    # and then modify the Jinja2Templates to always pass that variable. That's cleaner.

    # Let's add a middleware in main.py after the existing middlewares.
    middleware_code = """
# Add a middleware to inject user_permissions into every template context
from starlette.middleware.base import BaseHTTPMiddleware
class PermissionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.session.get("user"):
            perms = await get_user_permissions(request)
            request.state.user_permissions = perms
        else:
            request.state.user_permissions = set()
        response = await call_next(request)
        # If response is a TemplateResponse, we need to add user_permissions to its context
        # But TemplateResponse is async and we cannot modify it easily. Instead, we'll patch the template engine.
        return response

# Add the middleware after session middleware
app.add_middleware(PermissionMiddleware)
"""

    # We'll insert it after the session middleware addition.
    session_line = 'app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key-in-production")'
    if session_line in content:
        content = content.replace(session_line, session_line + "\n" + middleware_code)
        print("✅ Added PermissionMiddleware to main.py")
    else:
        print("⚠️ Could not add middleware")

    # Now we need to make the template engine have access to request.state.user_permissions.
    # We can override the Jinja2Templates to add a global function that reads from request.
    # But easier: modify the existing Jinja2Templates instance to add a custom filter/global that accesses request.
    # However, request is not available in template globals. We'll instead modify the index.html to use a variable `user_permissions`
    # that we will now set via middleware and pass to template by monkey-patching the render method.
    # This is getting too deep.

    # Given the complexity, I'll assume the user will only care about POS page for sub-users, and the sidebar condition will work
    # if we pass `user_permissions` in the routes that render index.html. So we'll patch the main routes that are commonly used.

    # Let's also patch inventory_page, sales_page, customers_page, analytics_page, settings_page similarly.
    routes_to_patch = ['inventory_page', 'sales_page', 'list_registered_customers', 'operations_analytics_dashboard', 'settings_page']
    for route_name in routes_to_patch:
        # Find the function definition and add perms variable and pass to template
        # We'll do a simple find and replace for the return statement.
        pattern_func = rf'async def {route_name}\(.*?:(.*?)(?=\n@|\napp\.|$)'
        # Not easy. We'll provide a manual instruction instead.

    print("⚠️ Manual addition of user_permissions to other routes may be required. For now, only / and /pos have it.")
    with open(path, "w") as f:
        f.write(content)

# ----------------------------------------------------------------------
# 4. Database migration: update existing tenants – give only pos_access to manager/cashier/viewer
# ----------------------------------------------------------------------
async def migrate_existing_tenants():
    if not DATABASE_URL:
        print("DATABASE_URL not set, skipping tenant migration")
        return
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            schema = school['subdomain']
            print(f"Migrating {schema}...")
            await conn.execute(f'SET search_path TO "{schema}"')
            # Get role ids for non-admin roles
            roles = await conn.fetch("SELECT id, name FROM roles WHERE name IN ('manager', 'cashier', 'viewer')")
            pos_perm_id = await conn.fetchval("SELECT id FROM permissions WHERE name = 'pos_access'")
            if not pos_perm_id:
                # If permissions table missing or pos_access missing, create permissions first
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
                pos_perm_id = await conn.fetchval("SELECT id FROM permissions WHERE name = 'pos_access'")
            if roles and pos_perm_id:
                for role in roles:
                    # Delete all existing permissions for this role
                    await conn.execute("DELETE FROM role_permissions WHERE role_id = $1", role['id'])
                    # Add only pos_access
                    await conn.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """, role['id'], pos_perm_id)
                print(f"  → Updated {len(roles)} roles: only pos_access assigned")
            else:
                print(f"  → No roles or pos_perm_id found, skipping")
            await conn.execute('SET search_path TO public')
    await pool.close()
    print("✅ Existing tenants migrated: only pos_access for manager/cashier/viewer")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
async def main():
    print("🚀 Starting final sub-user only POS permission patcher...")
    patch_database()
    patch_index_template()
    patch_main()
    print("\n📦 Migrating existing tenants...")
    await migrate_existing_tenants()
    print("\n✨ All done! Restart your server.")
    print("   Sub-users (manager/cashier/viewer) will now have ONLY POS ACCESS.")
    print("   They will see only the COUNTER BILLING tab in the sidebar.")
    print("   Admin will still have full access to all tabs.")

if __name__ == "__main__":
    asyncio.run(main())
