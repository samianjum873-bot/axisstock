#!/usr/bin/env python3
import os
import re
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ----------------------------------------------------------------------
# Database migration for existing tenants (add missing columns)
# ----------------------------------------------------------------------
async def migrate_tenant_schema(conn, schema):
    await conn.execute(f'SET search_path TO "{schema}"')
    # Add is_active, created_by, created_at to users table if missing
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
        END
        $$;
    """)
    await conn.execute('SET search_path TO public')

async def migrate_all_tenants():
    if not DATABASE_URL:
        print("⚠️  DATABASE_URL not set – skipping tenant migration.")
        return
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            sub = school['subdomain']
            print(f"Migrating tenant: {sub}")
            await migrate_tenant_schema(conn, sub)
    await pool.close()

# ----------------------------------------------------------------------
# File patching functions
# ----------------------------------------------------------------------
def patch_database():
    path = "app/database.py"
    with open(path, "r") as f:
        content = f.read()
    old_users_table = """            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );"""
    new_users_table = """            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );"""
    if old_users_table in content:
        content = content.replace(old_users_table, new_users_table)
        with open(path, "w") as f:
            f.write(content)
        print("✅ Patched app/database.py – added user columns")
    else:
        # Maybe already patched or different formatting
        print("⚠️  app/database.py users table definition not found – manual check required")

def patch_middleware():
    path = "app/middleware.py"
    with open(path, "r") as f:
        content = f.read()
    # Replace the dispatch method with subuser detection
    old_dispatch = """    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static") or request.url.path == "/favicon.ico":
            request.state.tenant = None
            return await call_next(request)

        host = request.headers.get("host", "")
        host = host.split(":")[0]
        parts = host.split(".")
        if len(parts) >= 2:
            subdomain = parts[0]
            if await tenant_exists(subdomain):
                request.state.tenant = subdomain
                pool = await get_pool()
                conn = await pool.acquire()
                await conn.execute(f'SET search_path TO "{subdomain}"')
                request.state.db_conn = conn
                response = await call_next(request)
                await conn.execute('SET search_path TO public')
                await pool.release(conn)
                return response
        raise HTTPException(status_code=404, detail="School not found")"""
    new_dispatch = """    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static") or request.url.path == "/favicon.ico":
            request.state.tenant = None
            return await call_next(request)

        host = request.headers.get("host", "")
        host = host.split(":")[0]
        # Detect subuser domain: school.subuser.localhost
        is_subuser = ".subuser." in host
        if is_subuser:
            subdomain = host.split(".subuser.")[0]
        else:
            parts = host.split(".")
            subdomain = parts[0] if len(parts) >= 2 else None
        if subdomain and await tenant_exists(subdomain):
            request.state.tenant = subdomain
            request.state.is_subuser_domain = is_subuser
            pool = await get_pool()
            conn = await pool.acquire()
            await conn.execute(f'SET search_path TO "{subdomain}"')
            request.state.db_conn = conn
            response = await call_next(request)
            await conn.execute('SET search_path TO public')
            await pool.release(conn)
            return response
        raise HTTPException(status_code=404, detail="School not found")"""
    if old_dispatch in content:
        content = content.replace(old_dispatch, new_dispatch)
        with open(path, "w") as f:
            f.write(content)
        print("✅ Patched app/middleware.py – subuser domain detection")
    else:
        print("⚠️  app/middleware.py dispatch method not found – manual patch needed")

def patch_main_login():
    path = "app/main.py"
    with open(path, "r") as f:
        content = f.read()
    # Replace the /login POST handler
    old_login_func = '''@app.post("/login")
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
    new_login_func = '''@app.post("/login")
async def do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow("SELECT id, username, password_hash, is_active FROM users WHERE username = $1", username)
    if not user or not verify_password(password, user['password_hash']):
        return RedirectResponse(url="/login?error=1", status_code=303)
    if not user['is_active']:
        return RedirectResponse(url="/login?error=inactive", status_code=303)
    # Fetch user role
    role = await conn.fetchval("""
        SELECT r.name FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = $1
    """, user['id'])
    is_subuser_domain = getattr(request.state, 'is_subuser_domain', False)
    if is_subuser_domain:
        if role == 'admin':
            return RedirectResponse(url="/login?error=admin_not_allowed", status_code=303)
    else:
        if role != 'admin':
            return RedirectResponse(url="/login?error=subuser_not_allowed", status_code=303)
    request.session["user"] = username
    request.session["user_id"] = user['id']
    request.session["role"] = role
    return RedirectResponse(url="/", status_code=303)'''
    if old_login_func in content:
        content = content.replace(old_login_func, new_login_func)
        with open(path, "w") as f:
            f.write(content)
        print("✅ Patched app/main.py – login role/domain restrictions")
    else:
        print("⚠️  app/main.py login function not found – manual patch needed")

def patch_login_template():
    path = "app/templates/login.html"
    with open(path, "r") as f:
        content = f.read()
    # Enhance error alert to show different messages
    old_alert = '''        <div id="errorAlert" class="hidden bg-rose-50 border-2 border-rose-500 p-3 rounded-xl mb-4 flex items-center space-x-2 text-rose-700 animate-pulse">
            <i class="fas fa-exclamation-triangle"></i>
            <span class="text-xs font-black uppercase">Invalid Terminal Credentials!</span>
        </div>'''
    new_alert = '''        <div id="errorAlert" class="hidden bg-rose-50 border-2 border-rose-500 p-3 rounded-xl mb-4 flex items-center space-x-2 text-rose-700 animate-pulse">
            <i class="fas fa-exclamation-triangle"></i>
            <span id="errorMsg" class="text-xs font-black uppercase">Invalid Terminal Credentials!</span>
        </div>'''
    if old_alert in content:
        content = content.replace(old_alert, new_alert)
        # Also replace the JavaScript error parsing
        old_js = '''        document.addEventListener("DOMContentLoaded", function() {
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('error') === '1') {
                const alertBox = document.getElementById('errorAlert');
                alertBox.classList.remove('hidden');
            }
        });'''
        new_js = '''        document.addEventListener("DOMContentLoaded", function() {
            const urlParams = new URLSearchParams(window.location.search);
            const errorCode = urlParams.get('error');
            if (errorCode) {
                const alertBox = document.getElementById('errorAlert');
                const msgSpan = document.getElementById('errorMsg');
                if (errorCode === '1') msgSpan.innerText = 'Invalid Username or Password!';
                else if (errorCode === 'inactive') msgSpan.innerText = 'Account Disabled! Contact Admin.';
                else if (errorCode === 'admin_not_allowed') msgSpan.innerText = 'Admin cannot login from subuser domain.';
                else if (errorCode === 'subuser_not_allowed') msgSpan.innerText = 'Sub-users must login via subuser domain.';
                else msgSpan.innerText = 'Access Denied!';
                alertBox.classList.remove('hidden');
            }
        });'''
        if old_js in content:
            content = content.replace(old_js, new_js)
        with open(path, "w") as f:
            f.write(content)
        print("✅ Patched app/templates/login.html – detailed error messages")
    else:
        print("⚠️  login.html error div not found – manual edit needed")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
async def main():
    print("🚀 Starting multi‑tenant sub‑user patcher (final)...")
    patch_database()
    patch_middleware()
    patch_main_login()
    patch_login_template()
    print("\n📦 Running database migrations for existing tenants...")
    await migrate_all_tenants()
    print("\n✨ All done! Restart uvicorn and test.")
    print("   - School admin:  http://school.localhost:8000")
    print("   - Sub‑user:      http://school.subuser.localhost:8000")
    print("   (Make sure /etc/hosts has wildcard entries or use dnsmasq)")

if __name__ == "__main__":
    asyncio.run(main())
