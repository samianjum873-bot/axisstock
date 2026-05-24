#!/bin/bash
set -e  # stop on error

echo "============================================="
echo "AxisStock Final Patcher – Security & Stability"
echo "============================================="

# Backup function
backup_file() {
    if [ -f "$1" ] && [ ! -f "$1.bak" ]; then
        cp "$1" "$1.bak"
        echo "  Backed up $1"
    fi
}

# 1. Backup files
echo "Creating backups..."
backup_file "app/database.py"
backup_file "app/main.py"
backup_file "app/middleware.py"
backup_file "app/templates/product_detail.html"

# 2. Remove broken / unused files
echo "Removing obsolete files..."
rm -f "app/database/seed.py"
rm -f "app/templates/pos.html"
rm -f "app/templates/main.py"

# 3. Add bcrypt to requirements.txt (if it exists)
if [ -f "requirements.txt" ]; then
    if ! grep -q "bcrypt" requirements.txt; then
        echo "bcrypt" >> requirements.txt
        echo "  Added bcrypt to requirements.txt"
    fi
fi

# 4. Fix database.py – INSERT statement must use bcrypt hash
echo "Fixing database.py (INSERT with hashed password)..."
python3 << 'EOF'
import re
db_file = "app/database.py"
with open(db_file, "r") as f:
    content = f.read()

# Replace the old INSERT line (still uses 'password' column and plaintext)
old_insert = r'await conn\.execute\(\s*"INSERT INTO users \(username, password\) VALUES \(\$1, \$2\)",\s*admin_username,\s*admin_password\s*\)'
new_insert = '''await conn.execute(
            "INSERT INTO users (username, password_hash) VALUES ($1, $2)",
            admin_username, bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        )'''
content = re.sub(old_insert, new_insert, content, flags=re.DOTALL)

with open(db_file, "w") as f:
    f.write(content)
print("  database.py INSERT fixed")
EOF

# 5. Patch main.py (comprehensive)
echo "Patching main.py (bcrypt, session auth, stock validation, subdomain validation)..."
python3 << 'EOF'
import re
main_file = "app/main.py"
with open(main_file, "r") as f:
    content = f.read()

# 5.1 Add bcrypt import if missing
if "import bcrypt" not in content:
    content = content.replace("from app.middleware import TenantMiddleware", "from app.middleware import TenantMiddleware\nimport bcrypt")

# 5.2 Add hash helper functions
hash_helpers = """
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
"""
if "def hash_password" not in content:
    content = content.replace("def generate_professional_sku(", hash_helpers + "\ndef generate_professional_sku(")

# 5.3 Replace login route entirely
login_pattern = r'@app\.post\("/login"\)\s+async def do_login\(.*?\):.*?(?=@app\.get|\Z)'
def login_repl(match):
    return '''@app.post("/login")
async def do_login(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if user and verify_password(password, user['password_hash']):
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)'''
content = re.sub(login_pattern, login_repl, content, flags=re.DOTALL)

# 5.4 Remove the insecure admin/admin fallback code if still present
content = re.sub(r'if not user and username == "admin".*?user = \{"username": "admin"\}', '', content, flags=re.DOTALL)

# 5.5 Change is_logged_in to use session
content = re.sub(
    r'def is_logged_in\(request: Request\):\s+return request\.cookies\.get\("active_user"\) is not None',
    'def is_logged_in(request: Request):\n    return request.session.get("user") is not None',
    content
)

# 5.6 Replace logout to clear session
logout_func = '''@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)'''
content = re.sub(r'@app\.get\("/logout"\).*?(?=@app\.get|\Z)', logout_func, content, flags=re.DOTALL)

# 5.7 Add subdomain validation in create_school
create_school_func = r'(@app\.post\("/super-admin/create-school"\)[\s\S]+?subdomain = subdomain\.lower\(\)\.strip\(\))'
def add_subdomain_validation(match):
    prefix = match.group(1)
    return prefix + '\n    import re\n    if not re.match(r"^[a-z0-9-]+$", subdomain):\n        raise HTTPException(status_code=400, detail="Invalid subdomain. Use only letters, numbers, and hyphens.")'
content = re.sub(create_school_func, add_subdomain_validation, content, flags=re.DOTALL)

# 5.8 Add stock validation in checkout endpoint
checkout_update_pattern = r'await conn\.execute\("UPDATE products SET stock = stock - \$1 WHERE id = \$2", i\['qty'\], i\['id'\]\)'
checkout_replacement = '''result = await conn.execute("UPDATE products SET stock = stock - $1 WHERE id = $2 AND stock >= $1", i['qty'], i['id'])
                if result == "UPDATE 0":
                    raise Exception(f"Insufficient stock for product {i['id']}")'''
content = re.sub(checkout_update_pattern, checkout_replacement, content)

# 5.9 Add migration function for 'created_at' column on existing tenants
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
    # Insert after the first pool = await get_pool() line in lifespan
    content = content.replace(
        "pool = await get_pool()",
        "pool = await get_pool()\n    await migrate_existing_tenants()"
    )
    content = content.replace(
        "async def lifespan(app: FastAPI):",
        migration_func + "\nasync def lifespan(app: FastAPI):"
    )

with open(main_file, "w") as f:
    f.write(content)
print("  main.py patched")
EOF

# 6. Patch middleware.py – fix connection leak (try/finally)
echo "Patching middleware.py..."
python3 << 'EOF'
mid_file = "app/middleware.py"
with open(mid_file, "r") as f:
    content = f.read()

old_block = r'(response = await call_next\(request\))\s+await conn\.execute\("SET search_path TO public"\)\s+await pool\.release\(conn\)\s+return response'
new_block = r'''try:
                    response = await call_next(request)
                finally:
                    await conn.execute('SET search_path TO public')
                    await pool.release(conn)
                return response'''
content = re.sub(old_block, new_block, content, flags=re.DOTALL)

with open(mid_file, "w") as f:
    f.write(content)
print("  middleware.py patched")
EOF

# 7. Rewrite product_detail.html to extend index.html
echo "Rewriting product_detail.html..."
python3 << 'EOF'
template_file = "app/templates/product_detail.html"
with open(template_file, "r") as f:
    old_content = f.read()

import re
body_match = re.search(r'<body[^>]*>(.*?)</body>', old_content, re.DOTALL)
if body_match:
    body_content = body_match.group(1)
else:
    body_content = old_content

new_template = '''{% extends "index.html" %}

{% block title %}{{ product.name }} Profile | AXIS{% endblock %}
{% block header_title %}Product Details & Analytics{% endblock %}

{% block page_content %}
''' + body_content + '''
{% endblock %}
'''
with open(template_file, "w") as f:
    f.write(new_template)
print("  product_detail.html now extends index.html")
EOF

echo ""
echo "============================================="
echo "Patching completed successfully!"
echo "============================================="
echo ""
echo "Next steps:"
echo "1. Install bcrypt: pip install bcrypt"
echo "2. Restart the FastAPI application: uvicorn app.main:app --reload"
echo ""
echo "3. Migrate existing plaintext passwords (run exactly once):"
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
echo "After migration, all existing users can log in with their old passwords."
echo "Backup files (.bak) are saved – restore if needed."
