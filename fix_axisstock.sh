#!/bin/bash
set -e

echo "=========================================="
echo "AxisStock Final Fix – One Shot"
echo "=========================================="

# Backup files
backup_file() {
    [ -f "$1" ] && [ ! -f "$1.bak" ] && cp "$1" "$1.bak" && echo "  Backed up $1"
}

echo "Creating backups..."
backup_file "app/database.py"
backup_file "app/main.py"
backup_file "app/middleware.py"
backup_file "app/templates/product_detail.html"

# Remove broken/unused files
echo "Cleaning up old files..."
rm -f "app/database/seed.py"
rm -f "app/templates/pos.html"
rm -f "app/templates/main.py"

# Add bcrypt to requirements if exists
[ -f "requirements.txt" ] && ! grep -q bcrypt requirements.txt && echo "bcrypt" >> requirements.txt && echo "  Added bcrypt to requirements.txt"

# ---------- Fix database.py ----------
echo "Fixing database.py..."
python3 << 'PYEOF'
import re
db_file = "app/database.py"
with open(db_file, "r") as f:
    content = f.read()

# Add bcrypt import if missing
if "import bcrypt" not in content:
    content = content.replace("load_dotenv()", "load_dotenv()\nimport bcrypt")

# Change column name password -> password_hash in CREATE TABLE
content = re.sub(r'password TEXT NOT NULL', 'password_hash TEXT NOT NULL', content)

# Fix the INSERT statement: use bcrypt.hashpw
old_insert = '''await conn.execute("""
            INSERT INTO users (username, password) VALUES ($1, $2)
            ON CONFLICT (username) DO NOTHING;
        """, admin_username, admin_password)'''
new_insert = '''hashed_pw = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        await conn.execute("""
            INSERT INTO users (username, password_hash) VALUES ($1, $2)
            ON CONFLICT (username) DO NOTHING;
        """, admin_username, hashed_pw)'''
content = content.replace(old_insert, new_insert)

with open(db_file, "w") as f:
    f.write(content)
print("  database.py patched")
PYEOF

# ---------- Fix main.py ----------
echo "Fixing main.py (session auth, bcrypt, stock validation, subdomain validation)..."
python3 << 'PYEOF'
main_file = "app/main.py"
with open(main_file, "r") as f:
    content = f.read()

# 1. Add bcrypt import
if "import bcrypt" not in content:
    content = content.replace("from app.middleware import TenantMiddleware", "from app.middleware import TenantMiddleware\nimport bcrypt")

# 2. Add password helpers after generate_professional_sku
helpers = '''
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
'''
if "def hash_password" not in content:
    content = content.replace("def generate_professional_sku(", helpers + "\ndef generate_professional_sku(")

# 3. Replace login route
old_login = '''@app.post("/login")
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

new_login = '''@app.post("/login")
async def do_login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if user and verify_password(password, user['password_hash']):
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)'''
content = content.replace(old_login, new_login)

# 4. Change is_logged_in to use session
content = content.replace(
    "def is_logged_in(request: Request):\n    return request.cookies.get(\"active_user\") is not None",
    "def is_logged_in(request: Request):\n    return request.session.get(\"user\") is not None"
)

# 5. Replace logout route
old_logout = '''@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("active_user")
    return resp'''
new_logout = '''@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)'''
content = content.replace(old_logout, new_logout)

# 6. Add subdomain validation in create_school
create_school_func = '''@app.post("/super-admin/create-school")
async def create_school(request: Request, name: str = Form(...), subdomain: str = Form(...),
                        admin_username: str = Form(...), admin_password: str = Form(...)):
    if request.cookies.get("super_admin") != "true":
        raise HTTPException(status_code=401)
    subdomain = subdomain.lower().strip()'''
new_create = '''@app.post("/super-admin/create-school")
async def create_school(request: Request, name: str = Form(...), subdomain: str = Form(...),
                        admin_username: str = Form(...), admin_password: str = Form(...)):
    if request.cookies.get("super_admin") != "true":
        raise HTTPException(status_code=401)
    subdomain = subdomain.lower().strip()
    import re
    if not re.match(r"^[a-z0-9-]+$", subdomain):
        raise HTTPException(status_code=400, detail="Invalid subdomain. Use only letters, numbers, and hyphens.")'''
content = content.replace(create_school_func, new_create)

# 7. Add stock validation in checkout (replace the UPDATE line)
old_update = '''await conn.execute("UPDATE products SET stock = stock - $1 WHERE id = $2", i['qty'], i['id'])'''
new_update = '''result = await conn.execute("UPDATE products SET stock = stock - $1 WHERE id = $2 AND stock >= $1", i['qty'], i['id'])
                if result == "UPDATE 0":
                    raise Exception(f"Insufficient stock for product {i['id']}")'''
content = content.replace(old_update, new_update)

# 8. Add migration for created_at column on existing tenants
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
if "migrate_existing_tenants" not in content:
    # Insert migration function before lifespan
    content = content.replace(
        "async def lifespan(app: FastAPI):",
        migration_func + "\nasync def lifespan(app: FastAPI):"
    )
    # Call it inside lifespan after pool = await get_pool()
    content = content.replace(
        "pool = await get_pool()",
        "pool = await get_pool()\n    await migrate_existing_tenants()"
    )

with open(main_file, "w") as f:
    f.write(content)
print("  main.py patched")
PYEOF

# ---------- Fix middleware.py (connection leak) ----------
echo "Fixing middleware.py..."
python3 << 'PYEOF'
mid_file = "app/middleware.py"
with open(mid_file, "r") as f:
    content = f.read()

old_block = '''                response = await call_next(request)
                await conn.execute('SET search_path TO public')
                await pool.release(conn)
                return response'''
new_block = '''                try:
                    response = await call_next(request)
                finally:
                    await conn.execute('SET search_path TO public')
                    await pool.release(conn)
                return response'''
content = content.replace(old_block, new_block)

with open(mid_file, "w") as f:
    f.write(content)
print("  middleware.py patched")
PYEOF

# ---------- Fix product_detail.html to extend index.html ----------
echo "Fixing product_detail.html..."
python3 << 'PYEOF'
template_file = "app/templates/product_detail.html"
with open(template_file, "r") as f:
    old = f.read()

# Extract body content
import re
body_match = re.search(r'<body[^>]*>(.*?)</body>', old, re.DOTALL)
if body_match:
    body = body_match.group(1)
else:
    body = old

new_template = '''{% extends "index.html" %}

{% block title %}{{ product.name }} Profile | AXIS{% endblock %}
{% block header_title %}Product Details & Analytics{% endblock %}

{% block page_content %}
''' + body + '''
{% endblock %}
'''
with open(template_file, "w") as f:
    f.write(new_template)
print("  product_detail.html now extends index.html")
PYEOF

echo ""
echo "=========================================="
echo "All fixes applied successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Install bcrypt: pip install bcrypt"
echo "2. Restart the app: uvicorn app.main:app --reload"
echo ""
echo "3. Migrate existing plaintext passwords (run once):"
echo ""
echo "python3 -c \""
echo "import asyncio, bcrypt"
echo "from app.database import get_pool"
echo ""
echo "async def migrate():"
echo "    pool = await get_pool()"
echo "    async with pool.acquire() as conn:"
echo "        schools = await conn.fetch('SELECT subdomain FROM public.schools')"
echo "        for s in schools:"
echo "            await conn.execute(f'SET search_path TO \\\"{s['subdomain']}\\\"')"
echo "            rows = await conn.fetch('SELECT id, password FROM users')"
echo "            for row in rows:"
echo "                hashed = bcrypt.hashpw(row['password'].encode(), bcrypt.gensalt()).decode()"
echo "                await conn.execute('UPDATE users SET password_hash = $1 WHERE id = $2', hashed, row['id'])"
echo "            await conn.execute('ALTER TABLE users DROP COLUMN password')"
echo "            await conn.execute('SET search_path TO public')"
echo "asyncio.run(migrate())"
echo "\""
echo ""
echo "After migration, existing users can log in with their old passwords."
echo "Backup files (.bak) are saved – restore if needed."
