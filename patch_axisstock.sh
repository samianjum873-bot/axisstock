#!/bin/bash
# AxisStock Security & Stability Patcher
# Run this script from the project root (where app/ folder lives)

set -e  # stop on error

echo "=========================================="
echo "AxisStock Patcher – Applying critical fixes"
echo "=========================================="

# Backup function
backup_file() {
    if [ -f "$1" ] && [ ! -f "$1.bak" ]; then
        cp "$1" "$1.bak"
        echo "  Backed up $1"
    fi
}

# 1. Backup files that will be changed
echo "Creating backups..."
backup_file "app/database.py"
backup_file "app/main.py"
backup_file "app/middleware.py"
backup_file "app/templates/product_detail.html"

# 2. Remove broken seed script
echo "Removing broken seed script..."
rm -f "app/database/seed.py"

# 3. Delete unused templates
echo "Removing unused/duplicate templates..."
rm -f "app/templates/pos.html"
rm -f "app/templates/main.py"

# 4. Patch database.py – rename password column and add hash function
echo "Patching app/database.py..."
sed -i 's/password TEXT NOT NULL/password_hash TEXT NOT NULL/g' app/database.py
sed -i 's/password = \$2/password_hash = \$2/g' app/database.py
# Add bcrypt import and hash helper at the top of database.py (after imports)
awk '/^load_dotenv\(\)/ {print; print "\nimport bcrypt"; next}1' app/database.py > app/database.py.tmp && mv app/database.py.tmp app/database.py

# 5. Patch main.py – major changes (using Python inline for precision)
echo "Patching app/main.py (requires bcrypt, session auth, stock validation)..."
python3 << 'EOF'
import re
import sys

main_file = "app/main.py"
with open(main_file, "r") as f:
    content = f.read()

# 1. Add bcrypt import at top (after existing imports)
if "import bcrypt" not in content:
    content = content.replace("from app.middleware import TenantMiddleware", "from app.middleware import TenantMiddleware\nimport bcrypt")

# 2. Helper function to hash password
hash_func = """
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
"""
if "def hash_password" not in content:
    # Insert after the generate_professional_sku function
    content = content.replace("def generate_professional_sku(", hash_func + "\ndef generate_professional_sku(")

# 3. Modify create_tenant_schema call to use hash (currently called from lifespan and create-school)
# In lifespan: create_tenant_schema("demo", "admin", "admin") -> hash "admin"
# Replace the INSERT INTO users line in database.py? Actually the hash happens in create_tenant_schema.
# We'll change database.py's create_tenant_schema to accept plain password and hash it.
# But database.py already patched? We'll patch database.py as well.
# Instead, we modify the call in main.py to pass hashed password? Better to keep create_tenant_schema unchanged and let it hash.
# We need to modify database.py's create_tenant_schema to hash the password. Let's do that now.

# Modify database.py: inside create_tenant_schema, replace the INSERT statement to use bcrypt.
db_file = "app/database.py"
with open(db_file, "r") as f:
    db_content = f.read()
# Add bcrypt import if not present
if "import bcrypt" not in db_content:
    db_content = db_content.replace("from dotenv import load_dotenv", "from dotenv import load_dotenv\nimport bcrypt")
# Replace the INSERT line
db_content = re.sub(
    r'await conn\.execute\(\s*"INSERT INTO users \(username, password\) VALUES \(\$1, \$2\)"',
    'await conn.execute(\n            "INSERT INTO users (username, password_hash) VALUES ($1, $2)",\n            admin_username, bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()',
    db_content
)
# Remove the original second argument line that follows
db_content = re.sub(r', admin_username, admin_password\)', '', db_content)
with open(db_file, "w") as f:
    f.write(db_content)
print("  Updated database.py to hash passwords")

# 4. Modify do_login to use verify_password
login_pattern = r'user = await conn\.fetchrow\("SELECT \* FROM users WHERE username = \$1 AND password = \$2", username, password\)'
replacement = '''user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if user and verify_password(password, user['password_hash']):'''
content = re.sub(login_pattern, replacement, content)

# Also remove the fallback admin/admin plaintext logic and replace with proper hashed check
fallback_pattern = r'if not user and username == "admin" and password == "admin":\s+await conn\.execute\("INSERT INTO users \(username, password\) VALUES \('admin', 'admin'\) ON CONFLICT DO NOTHING"\)\s+user = \{"username": "admin"\}'
content = re.sub(fallback_pattern, '', content)

# 5. Switch from cookie auth to session auth
# Replace is_logged_in function
content = re.sub(
    r'def is_logged_in\(request: Request\):\s+return request\.cookies\.get\("active_user"\) is not None',
    'def is_logged_in(request: Request):\n    return request.session.get("user") is not None',
    content
)

# Modify login route to set session instead of cookie
login_set_cookie = r'resp = RedirectResponse\(url="/", status_code=303\)\s+resp\.set_cookie\(key="active_user", value=username\)\s+return resp'
content = re.sub(login_set_cookie, 'request.session["user"] = username\n        return RedirectResponse(url="/", status_code=303)', content)

# Modify logout to clear session
logout_cookie = r'resp = RedirectResponse\(url="/login", status_code=303\)\s+resp\.delete_cookie\("active_user"\)\s+return resp'
content = re.sub(logout_cookie, 'request = Request(scope={"type": "http"})\n    # clear session\n    return RedirectResponse(url="/login", status_code=303)', content)
# Simpler: just redirect and let session expire? We'll implement proper session clearing.
logout_clear = """
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
"""
content = re.sub(r'@app\.get\("/logout"\)(.+?)(?=@app\.get|\Z)', logout_clear, content, flags=re.DOTALL)

# 6. Add subdomain validation in create_school
create_school_func = r'@app\.post\("/super-admin/create-school"\)(.+?)subdomain = subdomain\.lower\(\)\.strip\(\)'
def add_validation(match):
    prefix = match.group(0)
    return prefix + '\n    import re\n    if not re.match(r"^[a-z0-9-]+$", subdomain):\n        raise HTTPException(status_code=400, detail="Invalid subdomain. Use only letters, numbers, and hyphens.")\n'
content = re.sub(create_school_func, add_validation, content, flags=re.DOTALL)

# 7. Add stock validation in checkout endpoint
checkout_update = r'await conn\.execute\("UPDATE products SET stock = stock - \$1 WHERE id = \$2", i\['qty'\], i\['id'\]\)'
checkout_replacement = '''result = await conn.execute("UPDATE products SET stock = stock - $1 WHERE id = $2 AND stock >= $1", i['qty'], i['id'])
                if result == "UPDATE 0":
                    raise Exception(f"Insufficient stock for product {i['id']}")'''
content = re.sub(checkout_update, checkout_replacement, content)

# 8. Add created_at column to products table (in create_tenant_schema)
# We'll add a migration later, but also add to the CREATE TABLE statement in database.py
with open(db_file, "r") as f:
    db_content = f.read()
db_content = db_content.replace(
    "variation TEXT\n            );",
    "variation TEXT,\n                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n            );"
)
with open(db_file, "w") as f:
    f.write(db_content)

# 9. For existing tenants, we need to add the created_at column. We'll add a startup check in lifespan.
# Add a function to migrate existing schemas
migration_func = """
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
"""
# Insert after the pool = await get_pool() line in lifespan
content = content.replace(
    "pool = await get_pool()",
    "pool = await get_pool()\n    await migrate_existing_tenants()"
)
content = content.replace(
    "async def lifespan(app: FastAPI):",
    migration_func + "\nasync def lifespan(app: FastAPI):"
)

# Write back main.py
with open(main_file, "w") as f:
    f.write(content)
print("  Main.py patched with bcrypt, session auth, stock validation, subdomain validation, and migration.")

EOF

# 6. Patch middleware.py – fix connection leak
echo "Patching app/middleware.py..."
sed -i '/response = await call_next(request)/a\
                try:\
                    response = await call_next(request)\
                finally:\
                    await conn.execute("SET search_path TO public")\
                    await pool.release(conn)\
                return response\
                # Remove old lines after this' app/middleware.py
# More precise: replace the block from 'response = await call_next' to end of function
python3 << 'EOF'
mid_file = "app/middleware.py"
with open(mid_file, "r") as f:
    content = f.read()
# Find the dispatch method and replace the response handling part
import re
pattern = r'(response = await call_next\(request\))\s+await conn\.execute\("SET search_path TO public"\)\s+await pool\.release\(conn\)\s+return response'
replacement = r'''try:
                    response = await call_next(request)
                finally:
                    await conn.execute('SET search_path TO public')
                    await pool.release(conn)
                return response'''
content = re.sub(pattern, replacement, content, flags=re.DOTALL)
with open(mid_file, "w") as f:
    f.write(content)
print("  Middleware patched with try/finally for connection release.")
EOF

# 7. Rewrite product_detail.html to extend index.html
echo "Rewriting product_detail.html to extend index.html..."
python3 << 'EOF'
template_file = "app/templates/product_detail.html"
with open(template_file, "r") as f:
    old_content = f.read()

# Extract body content between <body> tags (roughly)
import re
body_match = re.search(r'<body[^>]*>(.*?)</body>', old_content, re.DOTALL)
if body_match:
    body_content = body_match.group(1)
else:
    body_content = old_content

# Create new template extending index.html
new_template = '''{% extends "index.html" %}

{% block title %}{{ product.name }} Profile | AXIS{% endblock %}
{% block header_title %}Product Details & Analytics{% endblock %}

{% block page_content %}
<!-- The original product detail content goes here, but must not include <body> or <head> tags -->
''' + body_content + '''
{% endblock %}
'''
# Remove any script duplication? The original has its own chart.js etc - keep as is.
# Also ensure no duplicate <html> tags.
with open(template_file, "w") as f:
    f.write(new_template)
print("  product_detail.html now extends index.html")
EOF

# 8. Update requirements.txt (if exists) or print reminder
echo "Checking for bcrypt in requirements..."
if [ -f "requirements.txt" ]; then
    if ! grep -q "bcrypt" requirements.txt; then
        echo "bcrypt" >> requirements.txt
        echo "  Added bcrypt to requirements.txt"
    fi
else
    echo "  No requirements.txt found. Please install bcrypt manually: pip install bcrypt"
fi

# 9. Final instructions
echo ""
echo "=========================================="
echo "Patching completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Install bcrypt if not already: pip install bcrypt"
echo "2. Restart the FastAPI application (uvicorn app.main:app --reload)"
echo "3. Existing tenants will have 'created_at' column added automatically on next startup."
echo "4. Existing user passwords are stored in plaintext – you must migrate them."
echo "   To migrate, run the following Python snippet once:"
echo ""
echo "   python3 -c \"
import asyncio, bcrypt
from app.database import get_pool
async def migrate():
    pool = await get_pool()
    async with pool.acquire() as conn:
        schools = await conn.fetch('SELECT subdomain FROM public.schools')
        for s in schools:
            await conn.execute(f'SET search_path TO \"{s['subdomain']}\"')
            rows = await conn.fetch('SELECT id, password FROM users')
            for row in rows:
                hashed = bcrypt.hashpw(row['password'].encode(), bcrypt.gensalt()).decode()
                await conn.execute('UPDATE users SET password_hash = $1 WHERE id = $2', hashed, row['id'])
            await conn.execute('ALTER TABLE users DROP COLUMN password')
            await conn.execute('SET search_path TO public')
asyncio.run(migrate())
\""
echo ""
echo "Backups of original files are saved as .bak in the same directories."
echo "You can restore any file by copying the .bak over the original."
