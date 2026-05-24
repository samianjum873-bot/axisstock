#!/usr/bin/env python3
import os
import re
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate_tenant_schema(conn, schema):
    """Add missing columns (is_active, created_by) to users table in a tenant schema."""
    await conn.execute(f'SET search_path TO "{schema}"')
    # Add is_active if not exists
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
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            sub = school['subdomain']
            print(f"Migrating tenant: {sub}")
            await migrate_tenant_schema(conn, sub)
    await pool.close()

def patch_files():
    # 1. Update app/database.py – add is_active/created_by to create_tenant_schema
    db_path = "app/database.py"
    with open(db_path, "r") as f:
        content = f.read()
    
    # Find the create_tenant_schema function and modify the users table creation
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
        with open(db_path, "w") as f:
            f.write(content)
        print("✅ Updated app/database.py - added is_active & created_by columns")
    else:
        print("⚠️  app/database.py users table definition not found or already modified")
    
    # 2. Update app/middleware.py – detect subuser subdomain
    mw_path = "app/middleware.py"
    with open(mw_path, "r") as f:
        mw_content = f.read()
    
    # Replace the dispatch method logic
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
        # Check for subuser subdomain pattern: school.subuser.localhost
        is_subuser_domain = False
        subdomain = None
        if ".subuser." in host:
            is_subuser_domain = True
            subdomain = host.split(".subuser.")[0]
        else:
            parts = host.split(".")
            if len(parts) >= 2:
                subdomain = parts[0]
        if subdomain and await tenant_exists(subdomain):
            request.state.tenant = subdomain
            request.state.is_subuser_domain = is_subuser_domain
            pool = await get_pool()
            conn = await pool.acquire()
            await conn.execute(f'SET search_path TO "{subdomain}"')
            request.state.db_conn = conn
            response = await call_next(request)
            await conn.execute('SET search_path TO public')
            await pool.release(conn)
            return response
        raise HTTPException(status_code=404, detail="School not found")"""
    
    if old_dispatch in mw_content:
        mw_content = mw_content.replace(old_dispatch, new_dispatch)
        with open(mw_path, "w") as f:
            f.write(mw_content)
        print("✅ Updated app/middleware.py - added subuser domain detection")
    else:
        print("⚠️  app/middleware.py dispatch method not found – manual check needed")
    
    # 3. Update app/main.py – modify login logic to restrict based on domain type
    main_path = "app/main.py"
    with open(main_path, "r") as f:
        main_content = f.read()
    
    # Replace do_login function
    old_login_func = """@app.post("/login")
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
    return RedirectResponse(url="/login?error=1", status_code=303)"""
    
    new_login_func = """@app.post("/login")
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
        # Subuser domain: only allow non-admin roles
        if role == 'admin':
            return RedirectResponse(url="/login?error=admin_not_allowed", status_code=303)
    else:
        # Main school domain: only allow admin role
        if role != 'admin':
            return RedirectResponse(url="/login?error=subuser_not_allowed", status_code=303)
    
    request.session["user"] = username
    request.session["user_id"] = user['id']
    request.session["role"] = role
    return RedirectResponse(url="/", status_code=303)"""
    
    if old_login_func in main_content:
        main_content = main_content.replace(old_login_func, new_login_func)
        # Also update the create_user endpoint to use created_by
        # Find the create_user endpoint and add created_by handling
        old_create_user = """@app.post("/api/users/create")
async def create_user(request: Request, username: str = Form(...), password: str = Form(...), role_id: int = Form(...)):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
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
    return {"status": "success"}"""
        
        if old_create_user in main_content:
            main_content = main_content.replace(old_create_user, old_create_user)  # already correct? Actually the old version might not have created_by. Let's replace with version that includes created_by.
            # The old version we see in the provided file does have created_by and is_active. Let's check: In the provided main.py, create_user already uses created_by and is_active? Actually looking at the provided code, the create_user endpoint already uses created_by and is_active (since we added those columns). But we need to ensure that the users table has those columns. We'll keep as is, but we need to ensure the INSERT includes created_by. The existing code does include it. So no change needed for create_user.
            pass
        
        with open(main_path, "w") as f:
            f.write(main_content)
        print("✅ Updated app/main.py - login domain restrictions added")
    else:
        print("⚠️  app/main.py login function not found - manual patch required")
    
    # 4. Update login.html template to show specific error messages
    login_html_path = "app/templates/login.html"
    with open(login_html_path, "r") as f:
        login_content = f.read()
    
    # Add more error messages
    error_span = """<div id="errorAlert" class="hidden bg-rose-50 border-2 border-rose-500 p-3 rounded-xl mb-4 flex items-center space-x-2 text-rose-700 animate-pulse">
            <i class="fas fa-exclamation-triangle"></i>
            <span class="text-xs font-black uppercase">Invalid Terminal Credentials!</span>
        </div>"""
    
    new_error_span = """<div id="errorAlert" class="hidden bg-rose-50 border-2 border-rose-500 p-3 rounded-xl mb-4 flex items-center space-x-2 text-rose-700 animate-pulse">
            <i class="fas fa-exclamation-triangle"></i>
            <span id="errorMsg" class="text-xs font-black uppercase">Invalid Terminal Credentials!</span>
        </div>"""
    
    if error_span in login_content:
        login_content = login_content.replace(error_span, new_error_span)
        # Also update JS to show different messages
        old_js = """const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('error') === '1') {
                const alertBox = document.getElementById('errorAlert');
                alertBox.classList.remove('hidden');
            }"""
        new_js = """const urlParams = new URLSearchParams(window.location.search);
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
            }"""
        if old_js in login_content:
            login_content = login_content.replace(old_js, new_js)
            with open(login_html_path, "w") as f:
                f.write(login_content)
            print("✅ Updated login.html with better error messages")
        else:
            print("⚠️  Could not update login.html JS – manual edit may be needed")
    else:
        print("⚠️  login.html error div not found")
    
    print("\n✅ File patches completed.")

async def main():
    print("🚀 Starting multi-tenant sub-user patcher...")
    patch_files()
    
    if DATABASE_URL:
        print("\n📦 Running database migrations for existing tenants...")
        await migrate_all_tenants()
        print("✅ Migrations complete.")
    else:
        print("⚠️  DATABASE_URL not found – skipping migrations. Please run migrations manually.")
    
    print("\n✨ All done! Restart your uvicorn server and test.")
    print("   - School admin: http://school.localhost:8000")
    print("   - Sub-user:    http://school.subuser.localhost:8000")
    print("   (Make sure to configure /etc/hosts or use dnsmasq for wildcard subdomains)")

if __name__ == "__main__":
    asyncio.run(main())
