#!/bin/bash
echo "=========================================="
echo "Adding RBAC (User Management) System"
echo "=========================================="

# Activate virtual environment if needed
if [[ -z "$VIRTUAL_ENV" ]]; then
    source venv/bin/activate
fi

# Create migration and new routes
python3 << 'PYEOF'
import asyncio
import bcrypt
from app.database import get_pool

async def setup_rbac():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get all schools
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            sub = school['subdomain']
            print(f"Setting up RBAC for {sub}...")
            await conn.execute(f'SET search_path TO "{sub}"')
            
            # Create roles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create permissions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    description TEXT
                )
            """)
            
            # Create user_roles junction
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                    PRIMARY KEY (user_id, role_id)
                )
            """)
            
            # Create role_permissions junction
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
                    PRIMARY KEY (role_id, permission_id)
                )
            """)
            
            # Add extra columns to users if not exist
            await conn.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='users' AND column_name='is_active') THEN
                        ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='users' AND column_name='created_by') THEN
                        ALTER TABLE users ADD COLUMN created_by INTEGER REFERENCES users(id);
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='users' AND column_name='created_at') THEN
                        ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                END $$;
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
            
            # Insert permissions
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
            
            # Assign permissions to roles
            await conn.execute("""
                -- Admin gets all permissions
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'admin'
                ON CONFLICT DO NOTHING;
                
                -- Manager permissions
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r, permissions p 
                WHERE r.name = 'manager' AND p.name IN ('pos_access', 'inventory_read', 'inventory_write', 'sales_read', 'customers_read', 'analytics_read')
                ON CONFLICT DO NOTHING;
                
                -- Cashier permissions
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r, permissions p 
                WHERE r.name = 'cashier' AND p.name IN ('pos_access')
                ON CONFLICT DO NOTHING;
                
                -- Viewer permissions
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r, permissions p 
                WHERE r.name = 'viewer' AND p.name IN ('sales_read', 'analytics_read')
                ON CONFLICT DO NOTHING;
            """)
            
            # Assign admin role to the first user (admin account) if not already
            await conn.execute("""
                INSERT INTO user_roles (user_id, role_id)
                SELECT u.id, r.id FROM users u, roles r 
                WHERE u.username = 'admin' AND r.name = 'admin'
                ON CONFLICT DO NOTHING
            """)
            
            await conn.execute('SET search_path TO public')
    print("RBAC setup complete for all schools.")

asyncio.run(setup_rbac())
PYEOF

# Now patch main.py to add RBAC routes and permission checking
echo "Patching app/main.py with RBAC routes..."
python3 << 'PYEOF'
import re
main_file = "app/main.py"
with open(main_file, "r") as f:
    content = f.read()

# Add permission checking helper function
perm_helper = '''
# ---------- RBAC HELPER ----------
async def get_user_permissions(request: Request):
    """Get permissions for current logged-in user"""
    if not is_logged_in(request):
        return set()
    conn = get_tenant_conn(request)
    username = request.session.get("user")
    perms = await conn.fetch("""
        SELECT DISTINCT p.name FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        JOIN users u ON ur.user_id = u.id
        WHERE u.username = $1 AND u.is_active = true
    """, username)
    return {p['name'] for p in perms}

def has_permission(permission_name: str):
    """Decorator to check permission"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            if not is_logged_in(request):
                return RedirectResponse(url="/login", status_code=303)
            perms = await get_user_permissions(request)
            if permission_name not in perms:
                return templates.TemplateResponse(request, "403.html", status_code=403)
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
'''

# Insert helper after existing functions
if "get_user_permissions" not in content:
    content = content.replace("def is_logged_in(request: Request):", perm_helper + "\ndef is_logged_in(request: Request):")

# Add settings route (admin only)
settings_routes = '''
@app.get("/settings")
async def settings_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    # Only admin can access settings
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)
    users = await conn.fetch("SELECT id, username, is_active, created_at FROM users ORDER BY id")
    roles = await conn.fetch("SELECT id, name, description FROM roles ORDER BY id")
    return templates.TemplateResponse(request, "settings.html", {
        "active_page": "settings",
        "users": users,
        "roles": roles
    })

@app.post("/api/users/create")
async def create_user(request: Request, username: str = Form(...), password: str = Form(...), role_id: int = Form(...)):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    # Check if user exists
    existing = await conn.fetchval("SELECT id FROM users WHERE username = $1", username)
    if existing:
        return {"status": "error", "message": "Username already exists"}
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    # Get current user id as creator
    current_user = request.session.get("user")
    creator = await conn.fetchval("SELECT id FROM users WHERE username = $1", current_user)
    user_id = await conn.fetchval("""
        INSERT INTO users (username, password_hash, created_by, is_active)
        VALUES ($1, $2, $3, true) RETURNING id
    """, username, hashed, creator)
    await conn.execute("INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)", user_id, role_id)
    return {"status": "success"}

@app.post("/api/users/toggle-status")
async def toggle_user_status(request: Request, user_id: int = Form(...)):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    await conn.execute("UPDATE users SET is_active = NOT is_active WHERE id = $1", user_id)
    return {"status": "success"}

@app.post("/api/users/delete")
async def delete_user(request: Request, user_id: int = Form(...)):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    # Prevent deleting yourself
    current_user = request.session.get("user")
    current_id = await conn.fetchval("SELECT id FROM users WHERE username = $1", current_user)
    if user_id == current_id:
        return {"status": "error", "message": "Cannot delete your own account"}
    await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    return {"status": "success"}

@app.post("/api/users/reset-password")
async def reset_user_password(request: Request, user_id: int = Form(...), new_password: str = Form(...)):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", hashed, user_id)
    return {"status": "success"}
'''

# Add routes after existing routes
if "/settings" not in content:
    # Insert before the last part (like favicon)
    content = content.replace("@app.get(\"/favicon.ico\")", settings_routes + "\n\n@app.get(\"/favicon.ico\")")

# Modify the route decorators to check permissions
# For each protected route, we need to add permission checks
# We'll modify the existing functions to call has_permission
# Simpler: inside each route, check permissions based on path

# Add permission checks inside each route
route_permissions = {
    "/": "pos_access",
    "/pos": "pos_access",
    "/inventory": "inventory_read",
    "/sales": "sales_read",
    "/customers": "customers_read",
    "/analytics": "analytics_read"
}

for path, perm in route_permissions.items():
    # Find the function definition and add permission check at start
    old_func = f'@app.get("{path}")\\nasync def.*?:\n    if not is_logged_in(request):'
    new_func = f'@app.get("{path}")\\nasync def \\1:\\n    if not is_logged_in(request):\\n        return RedirectResponse(url="/login", status_code=303)\\n    perms = await get_user_permissions(request)\\n    if "{perm}" not in perms:\\n        return templates.TemplateResponse(request, "403.html", status_code=403)'
    # Use regex with careful replacement
    pattern = re.compile(r'(@app\.get\("' + re.escape(path) + r'"\)\s+async def (\w+)\(request: Request\):\s+if not is_logged_in\(request\):)')
    def repl(m):
        return f'{m.group(1)}\n        return RedirectResponse(url="/login", status_code=303)\n    perms = await get_user_permissions(request)\n    if "{perm}" not in perms:\n        return templates.TemplateResponse(request, "403.html", status_code=403)'
    content = pattern.sub(repl, content)

# Also modify POST /api/products/smart-add to check inventory_write permission
content = content.replace(
    "if not is_logged_in(request):\n        raise HTTPException(status_code=401)",
    "if not is_logged_in(request):\n        raise HTTPException(status_code=401)\n    perms = await get_user_permissions(request)\n    if \"inventory_write\" not in perms:\n        raise HTTPException(status_code=403)"
)

# Add 403 template route
content = content.replace(
    "@app.get(\"/favicon.ico\")",
    "@app.get(\"/403\", response_class=HTMLResponse)\nasync def forbidden(request: Request):\n    return templates.TemplateResponse(request, \"403.html\")\n\n@app.get(\"/favicon.ico\")"
)

with open(main_file, "w") as f:
    f.write(content)
print("main.py patched with RBAC routes")
PYEOF

# Create settings.html template
echo "Creating settings.html template..."
cat > app/templates/settings.html << 'HTML'
{% extends "index.html" %}

{% block title %}User Management | AXIS{% endblock %}
{% block header_title %}User & Role Management{% endblock %}

{% block page_content %}
<div class="space-y-6">
    <!-- Create User Form -->
    <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
        <h3 class="text-lg font-black text-slate-800 mb-4">Create New User</h3>
        <form id="createUserForm" class="space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label class="block text-xs font-black text-slate-500 mb-1">Username</label>
                    <input type="text" id="newUsername" required class="w-full border p-3 rounded-xl font-bold">
                </div>
                <div>
                    <label class="block text-xs font-black text-slate-500 mb-1">Password</label>
                    <input type="password" id="newPassword" required class="w-full border p-3 rounded-xl font-bold">
                </div>
                <div>
                    <label class="block text-xs font-black text-slate-500 mb-1">Role</label>
                    <select id="newRoleId" class="w-full border p-3 rounded-xl font-bold">
                        {% for role in roles %}
                        <option value="{{ role.id }}">{{ role.name }} - {{ role.description }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            <button type="submit" class="bg-indigo-600 text-white px-6 py-2 rounded-xl font-black text-sm">Create User</button>
        </form>
    </div>

    <!-- Users List -->
    <div class="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div class="p-4 bg-slate-50 border-b">
            <h3 class="text-lg font-black text-slate-800">System Users</h3>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left">
                <thead class="bg-slate-100 text-slate-600 text-xs font-black uppercase">
                    <tr>
                        <th class="p-4">ID</th>
                        <th class="p-4">Username</th>
                        <th class="p-4">Status</th>
                        <th class="p-4">Created At</th>
                        <th class="p-4">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y">
                    {% for user in users %}
                    <tr class="hover:bg-slate-50">
                        <td class="p-4">{{ user.id }}</td>
                        <td class="p-4 font-bold">{{ user.username }}</td>
                        <td class="p-4">
                            <span class="px-2 py-1 rounded text-xs font-black {% if user.is_active %}bg-green-100 text-green-700{% else %}bg-red-100 text-red-700{% endif %}">
                                {{ "Active" if user.is_active else "Inactive" }}
                            </span>
                        </td>
                        <td class="p-4 text-sm">{{ user.created_at }}</td>
                        <td class="p-4 space-x-2">
                            <button onclick="toggleUserStatus({{ user.id }})" class="text-xs bg-amber-100 text-amber-700 px-3 py-1 rounded font-black">
                                {{ "Disable" if user.is_active else "Enable" }}
                            </button>
                            <button onclick="resetPassword({{ user.id }})" class="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded font-black">Reset Password</button>
                            <button onclick="deleteUser({{ user.id }})" class="text-xs bg-red-100 text-red-700 px-3 py-1 rounded font-black">Delete</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
document.getElementById('createUserForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('username', document.getElementById('newUsername').value);
    formData.append('password', document.getElementById('newPassword').value);
    formData.append('role_id', document.getElementById('newRoleId').value);
    const res = await fetch('/api/users/create', { method: 'POST', body: formData });
    const data = await res.json();
    if(data.status === 'success') {
        location.reload();
    } else {
        alert(data.message);
    }
});

async function toggleUserStatus(userId) {
    const formData = new FormData();
    formData.append('user_id', userId);
    await fetch('/api/users/toggle-status', { method: 'POST', body: formData });
    location.reload();
}

async function resetPassword(userId) {
    const newPass = prompt("Enter new password:");
    if(!newPass) return;
    const formData = new FormData();
    formData.append('user_id', userId);
    formData.append('new_password', newPass);
    await fetch('/api/users/reset-password', { method: 'POST', body: formData });
    alert("Password reset successfully");
}

async function deleteUser(userId) {
    if(!confirm("Are you sure? This action cannot be undone.")) return;
    const formData = new FormData();
    formData.append('user_id', userId);
    const res = await fetch('/api/users/delete', { method: 'POST', body: formData });
    const data = await res.json();
    if(data.status === 'success') {
        location.reload();
    } else {
        alert(data.message);
    }
}
</script>
{% endblock %}
HTML

# Add Settings link to sidebar in index.html
echo "Adding Settings link to sidebar..."
sed -i '/<a href=\"\/analytics\"/a \            <a href=\"/settings\" id=\"link-settings\" class=\"sidebar-link w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900\">\n                <i class=\"fas fa-cog w-8\"></i> <span class=\"font-bold text-xs\">SETTINGS</span>\n            </a>' app/templates/index.html

# Create 403 error page
echo "Creating 403.html template..."
cat > app/templates/403.html << 'HTML'
{% extends "index.html" %}
{% block title %}Access Denied{% endblock %}
{% block header_title %}Access Denied{% endblock %}
{% block page_content %}
<div class="flex flex-col items-center justify-center h-full">
    <div class="text-center">
        <h1 class="text-6xl font-black text-red-600 mb-4">403</h1>
        <p class="text-xl font-bold text-slate-700 mb-2">Access Denied</p>
        <p class="text-slate-500">You don't have permission to access this page.</p>
        <a href="/" class="mt-6 inline-block bg-indigo-600 text-white px-6 py-2 rounded-xl font-black">Go to Dashboard</a>
    </div>
</div>
{% endblock %}
HTML

# Also need to modify login to store user role in session (optional but useful)
echo "Updating login to store user role..."
python3 << 'EOF'
main_file = "app/main.py"
with open(main_file, "r") as f:
    content = f.read()

# Modify login to fetch and store user role in session
old_login_block = '''@app.post("/login")
async def do_login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow("SELECT * FROM users WHERE username = $1 AND password = $2", username, password)
    if not user and username == "admin" and password == "admin":
        await conn.execute("INSERT INTO users (username, password) VALUES ('admin', 'admin') ON CONFLICT DO NOTHING")
        user = {"username": "admin"}
    if user:
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(key="active_user", value=username)
        return resp
    return RedirectResponse(url="/login?error=1", status_code=303)'''

# Actually the login has been changed earlier, but we need to ensure session is set
# Let's replace with proper bcrypt + session + role fetch
new_login = '''@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow("SELECT id, username, password_hash FROM users WHERE username = $1", username)
    if user and verify_password(password, user['password_hash']):
        request.session["user"] = username
        request.session["user_id"] = user['id']
        # Fetch user role (optional)
        role = await conn.fetchval("""
            SELECT r.name FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = $1
        """, user['id'])
        request.session["role"] = role
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)'''

# Replace the login function if found
if "@app.post(\"/login\")" in content:
    # Find the function and replace
    import re
    pattern = r'@app\.post\("/login"\)\s+async def do_login\(.*?\):.*?(?=@app\.get)'
    content = re.sub(pattern, new_login, content, flags=re.DOTALL)

with open(main_file, "w") as f:
    f.write(content)
print("Login updated with role fetch")
EOF

echo "=========================================="
echo "RBAC system added successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart the application: uvicorn app.main:app --reload"
echo "2. Log in as admin (username: admin, password: admin)"
echo "3. Go to Settings page from sidebar"
echo "4. Create new users and assign roles (cashier, manager, viewer)"
echo "5. Test by logging in with those credentials - they will see only permitted pages"
