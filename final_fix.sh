#!/bin/bash
echo "========================================="
echo "AxisStock Final Fix – RBAC + Auth Fix"
echo "========================================="

cd ~/axisstock
source venv/bin/activate

python3 << 'PYEOF'
import re

main_file = "app/main.py"
with open(main_file, "r") as f:
    content = f.read()

# 1. Add password helper functions if missing
if "def verify_password" not in content:
    helpers = '''
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
'''
    # Insert after the last import or before generate_professional_sku
    content = content.replace("def generate_professional_sku(", helpers + "\ndef generate_professional_sku(")
    print("✓ Added password helpers")

# 2. Fix is_logged_in to use session (instead of cookie)
content = re.sub(
    r'def is_logged_in\(request: Request\):\s+return request\.cookies\.get\("active_user"\) is not None',
    'def is_logged_in(request: Request):\n    return request.session.get("user") is not None',
    content
)
print("✓ Fixed is_logged_in to use session")

# 3. Fix logout route to clear session
old_logout = r'@app\.get\("/logout"\)\s+async def logout\(\):\s+resp = RedirectResponse\(url="/login", status_code=303\)\s+resp\.delete_cookie\("active_user"\)\s+return resp'
new_logout = '''@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)'''
content = re.sub(old_logout, new_logout, content, flags=re.DOTALL)
print("✓ Fixed logout to clear session")

# 4. Fix login route – ensure it uses verify_password and sets session correctly
# First, find the whole login function
login_pattern = r'@app\.post\("/login"\)\s+async def do_login\(.*?\):.*?(?=@app\.get|\Z)'
def replace_login(match):
    return '''@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow("SELECT id, username, password_hash FROM users WHERE username = $1", username)
    if user and verify_password(password, user['password_hash']):
        request.session["user"] = username
        request.session["user_id"] = user['id']
        # Fetch user role
        role = await conn.fetchval("""
            SELECT r.name FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = $1
        """, user['id'])
        request.session["role"] = role
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)'''
content = re.sub(login_pattern, replace_login, content, flags=re.DOTALL)
print("✓ Fixed login route to use verify_password and session")

# 5. Remove any duplicate @app.get("/logout") that might be stuck after login
content = content.replace("return RedirectResponse(url=\"/login?error=1\", status_code=303)@app.get(\"/logout\")", 
                          "return RedirectResponse(url=\"/login?error=1\", status_code=303)\n\n@app.get(\"/logout\")")

# 6. Ensure get_user_permissions uses the fixed is_logged_in (already, but okay)

# 7. Fix the permission checks in routes – they had duplicate returns
# Remove redundant "return RedirectResponse" lines after 403
content = content.replace("return templates.TemplateResponse(request, \"403.html\", status_code=403)\n        return RedirectResponse(url=\"/login\", status_code=303)",
                          "return templates.TemplateResponse(request, \"403.html\", status_code=403)")

# 8. Fix the incorrect permission checks in API endpoints – they used inventory_write for everything
# Change recent_sales permission to sales_read
content = content.replace(
    'perms = await get_user_permissions(request)\n    if "inventory_write" not in perms:',
    'perms = await get_user_permissions(request)\n    if "sales_read" not in perms:'
)
# Fix analytics endpoint
content = content.replace(
    '@app.get("/api/v2/analytics")\nasync def get_fast_stats(request: Request):\n    if not is_logged_in(request):\n        raise HTTPException(status_code=401)\n    perms = await get_user_permissions(request)\n    if "inventory_write" not in perms:\n        raise HTTPException(status_code=403)',
    '@app.get("/api/v2/analytics")\nasync def get_fast_stats(request: Request):\n    if not is_logged_in(request):\n        raise HTTPException(status_code=401)\n    perms = await get_user_permissions(request)\n    if "analytics_read" not in perms:\n        raise HTTPException(status_code=403)'
)
# Fix receipt endpoint permission
content = content.replace(
    'perms = await get_user_permissions(request)\n    if "inventory_write" not in perms:\n        raise HTTPException(status_code=403)',
    'perms = await get_user_permissions(request)\n    if "sales_read" not in perms:\n        raise HTTPException(status_code=403)'
)

# 9. Add missing created_at column to products for existing tenants (already done earlier, but ensure migration runs)
if "migrate_existing_tenants" not in content:
    migration_func = '''
async def migrate_existing_tenants():
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
            await conn.execute('SET search_path TO public')
'''
    content = content.replace("async def lifespan(app: FastAPI):", migration_func + "\nasync def lifespan(app: FastAPI):")
    content = content.replace("pool = await get_pool()", "pool = await get_pool()\n    await migrate_existing_tenants()")
    print("✓ Added created_at migration")

with open(main_file, "w") as f:
    f.write(content)

print("✅ main.py fully patched")
PYEOF

echo "Restarting uvicorn..."
fuser -k 8000/tcp 2>/dev/null
uvicorn app.main:app --reload
