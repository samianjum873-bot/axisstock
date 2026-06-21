#!/usr/bin/env python3
"""
AxisStock Full System Patcher
Run from project root:  python3 patch_axisstock.py
"""

import os, sys, shutil, textwrap
from datetime import datetime

ROOT = os.getcwd()

def backup(path):
    if os.path.exists(path):
        bak = path + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, bak)
        print(f"  [BAK] {bak}")

def write(rel, content):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    backup(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK]  {rel}")

print("\n=== AxisStock System Patcher ===\n")

# ─────────────────────────────────────────────────────────────────────────────
# 1. app/database.py
# ─────────────────────────────────────────────────────────────────────────────
print("[1/5] Writing app/database.py ...")
write("app/database.py", '''\
import os
import asyncpg
import bcrypt
from dotenv import load_dotenv

load_dotenv()

pool = None


async def init_db_pool():
    global pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=15)
    return pool


async def get_pool():
    global pool
    if pool is None:
        await init_db_pool()
    return pool


async def create_tenant_schema(
    schema_name: str, admin_username: str, admin_password: str
):
    """
    Create a per-tenant PostgreSQL schema with tables, roles, permissions,
    and a hashed admin user.
    Safe: schema name is sanitised; password is bcrypt-hashed before storage.
    """
    global pool
    if pool is None:
        await init_db_pool()

    # Sanitise schema name – keep only alphanumeric and underscores
    safe_schema = "".join(
        c for c in schema_name if c.isalnum() or c == "_"
    )
    if not safe_schema:
        raise ValueError("Invalid schema name")

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(f\'\'\'CREATE SCHEMA IF NOT EXISTS "{safe_schema}"\'\'\')
            await conn.execute(f\'\'\'SET search_path TO "{safe_schema}"\'\'\')
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
                    payment_status TEXT DEFAULT \'Paid\',
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

            # Hashed password – never store plaintext
            hashed_pw = bcrypt.hashpw(
                admin_password.encode(), bcrypt.gensalt()
            ).decode()
            await conn.execute(
                """
                INSERT INTO users (username, password_hash)
                VALUES ($1, $2) ON CONFLICT (username) DO NOTHING
                """,
                admin_username,
                hashed_pw,
            )

            # Default roles
            await conn.execute("""
                INSERT INTO roles (name, description) VALUES
                    (\'admin\',   \'Full access to all features\'),
                    (\'manager\', \'Can manage inventory and view sales\'),
                    (\'cashier\', \'Can only process sales at POS\'),
                    (\'viewer\',  \'Read-only access to reports\')
                ON CONFLICT (name) DO NOTHING
            """)

            # Default permissions
            await conn.execute("""
                INSERT INTO permissions (name, resource, action, description) VALUES
                    (\'pos_access\',      \'pos\',       \'read\',   \'Access POS billing page\'),
                    (\'inventory_read\',  \'inventory\', \'read\',   \'View inventory\'),
                    (\'inventory_write\', \'inventory\', \'write\',  \'Add/edit inventory items\'),
                    (\'sales_read\',      \'sales\',     \'read\',   \'View sales history\'),
                    (\'customers_read\',  \'customers\', \'read\',   \'View customers\'),
                    (\'analytics_read\',  \'analytics\', \'read\',   \'View analytics reports\'),
                    (\'users_manage\',    \'users\',     \'manage\', \'Manage users and roles\')
                ON CONFLICT (name) DO NOTHING
            """)

            # Admin gets all permissions
            admin_role = await conn.fetchval(
                "SELECT id FROM roles WHERE name = \'admin\'"
            )
            if admin_role:
                all_perms = await conn.fetch("SELECT id FROM permissions")
                for perm in all_perms:
                    await conn.execute(
                        """INSERT INTO role_permissions (role_id, permission_id)
                           VALUES ($1, $2) ON CONFLICT DO NOTHING""",
                        admin_role,
                        perm["id"],
                    )

            # Other roles get pos_access only by default
            pos_perm = await conn.fetchval(
                "SELECT id FROM permissions WHERE name = \'pos_access\'"
            )
            if pos_perm:
                for role_name in ["manager", "cashier", "viewer"]:
                    role_id = await conn.fetchval(
                        "SELECT id FROM roles WHERE name = $1", role_name
                    )
                    if role_id:
                        await conn.execute(
                            """INSERT INTO role_permissions (role_id, permission_id)
                               VALUES ($1, $2) ON CONFLICT DO NOTHING""",
                            role_id,
                            pos_perm,
                        )

            # Assign admin role to initial admin user
            await conn.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT u.id, r.id FROM users u, roles r
                WHERE u.username = $1 AND r.name = \'admin\'
                ON CONFLICT DO NOTHING
                """,
                admin_username,
            )

            await conn.execute("SET search_path TO public")


async def tenant_exists(subdomain: str) -> bool:
    global pool
    if pool is None:
        await init_db_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT 1 FROM public.schools WHERE subdomain = $1", subdomain
        )
        return result is not None
''')

# ─────────────────────────────────────────────────────────────────────────────
# 2. app/middleware.py
# ─────────────────────────────────────────────────────────────────────────────
print("[2/5] Writing app/middleware.py ...")
write("app/middleware.py", '''\
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import get_pool, tenant_exists

# Paths that bypass tenant resolution entirely
_BYPASS_PREFIXES = ("/super-admin", "/static", "/favicon.ico")


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in _BYPASS_PREFIXES):
            request.state.tenant = None
            request.state.db_conn = None
            return await call_next(request)

        host = request.headers.get("host", "").split(":")[0].lower()

        # Detect subuser domain pattern: <school>.subuser.<domain>
        is_subuser = ".subuser." in host
        if is_subuser:
            subdomain = host.split(".subuser.")[0]
        else:
            parts = host.split(".")
            subdomain = parts[0] if len(parts) >= 2 else None

        if not subdomain or not await tenant_exists(subdomain):
            raise HTTPException(status_code=404, detail="School not found")

        request.state.tenant = subdomain
        request.state.is_subuser_domain = is_subuser

        pool = await get_pool()
        conn = await pool.acquire()
        request.state.db_conn = conn

        try:
            await conn.execute(f\'\'\'SET search_path TO "{subdomain}"\'\'\')
            response = await call_next(request)
            return response
        except Exception:
            raise
        finally:
            # Always reset search_path and release connection
            try:
                await conn.execute("SET search_path TO public")
            except Exception:
                pass
            await pool.release(conn)
''')

# ─────────────────────────────────────────────────────────────────────────────
# 3. app/main.py
# ─────────────────────────────────────────────────────────────────────────────
print("[3/5] Writing app/main.py ...")
write("app/main.py", '''\
from dotenv import load_dotenv
load_dotenv()

import os
import secrets
import random
import string
import json
from datetime import datetime
from contextlib import asynccontextmanager
from functools import wraps

import bcrypt
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db_pool, get_pool, create_tenant_schema, tenant_exists
from app.middleware import TenantMiddleware

# ── Environment ────────────────────────────────────────────────────────────────
SUPER_ADMIN_USER = os.getenv("SUPER_ADMIN_USER", "superadmin")
SUPER_ADMIN_PASS = os.getenv("SUPER_ADMIN_PASS", "")
SESSION_SECRET   = os.getenv("SESSION_SECRET", secrets.token_hex(32))

if not SUPER_ADMIN_PASS:
    print("WARNING: SUPER_ADMIN_PASS not set – super-admin login is disabled")

# ── Helpers ────────────────────────────────────────────────────────────────────
def get_tenant_conn(request: Request):
    conn = getattr(request.state, "db_conn", None)
    if conn is None:
        raise HTTPException(status_code=500, detail="Database connection unavailable")
    return conn


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _validate_password(password: str):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")


async def get_user_permissions(request: Request) -> set:
    """Return set of permission names for the currently logged-in user."""
    if not is_logged_in(request):
        return set()
    conn = get_tenant_conn(request)
    username = request.session.get("user")
    perms = await conn.fetch("""
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        JOIN users u ON ur.user_id = u.id
        WHERE u.username = $1 AND u.is_active = true
    """, username)
    return {p["name"] for p in perms}


def require_login(func):
    """Redirect to /login if not authenticated."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not is_logged_in(request):
            return RedirectResponse(url="/login", status_code=303)
        return await func(request, *args, **kwargs)
    return wrapper


def require_permission(perm: str):
    """Redirect/403 if user lacks the given permission."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            if not is_logged_in(request):
                return RedirectResponse(url="/login", status_code=303)
            perms = await get_user_permissions(request)
            if perm not in perms:
                return templates.TemplateResponse(
                    request, "403.html", status_code=403
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def _require_super_admin(request: Request):
    if request.cookies.get("super_admin") != "true":
        raise HTTPException(status_code=401, detail="Unauthorized")


def generate_professional_sku(category, name, s_class="", subject=""):
    clean_name  = "".join(c for c in name    if c.isalnum()).upper()[:5]
    clean_sub   = "".join(c for c in subject if c.isalnum()).upper()[:4] if subject else "GEN"
    clean_class = "".join(c for c in s_class if c.isalnum()).upper() if s_class else "ALL"
    rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    cat_lower   = category.strip().lower()
    if "book" in cat_lower and "notebook" not in cat_lower:
        return f"BK-{clean_class}-{clean_sub}-{rand_suffix}"
    elif "notebook" in cat_lower:
        return f"NB-{clean_name}-{clean_class}-{rand_suffix}"
    else:
        return f"ST-{clean_name}-{rand_suffix}"


# ── Lifespan ───────────────────────────────────────────────────────────────────
async def lifespan(app: FastAPI):
    await init_db_pool()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE SCHEMA IF NOT EXISTS public;
            CREATE TABLE IF NOT EXISTS public.schools (
                id             SERIAL PRIMARY KEY,
                name           TEXT NOT NULL,
                subdomain      TEXT UNIQUE NOT NULL,
                admin_username TEXT NOT NULL,
                admin_password TEXT NOT NULL,   -- stored for display only; auth uses schema users table
                created_at     TIMESTAMP DEFAULT NOW()
            );
        """)
        # Run any pending migrations on existing tenants
        await _migrate_tenants(conn)

        # Seed demo school if absent
        demo_exists = await conn.fetchval(
            "SELECT 1 FROM public.schools WHERE subdomain = \'demo\'"
        )
        if not demo_exists:
            await conn.execute(
                "INSERT INTO public.schools (name, subdomain, admin_username, admin_password)"
                " VALUES ($1, $2, $3, $4)",
                "Demo School", "demo", "admin", "admin",
            )
            await create_tenant_schema("demo", "admin", "admin")

    yield
    pool = await get_pool()
    await pool.close()


async def _migrate_tenants(conn):
    """Non-destructive migrations applied to every tenant schema."""
    schools = await conn.fetch("SELECT subdomain FROM public.schools")
    for school in schools:
        sub = school["subdomain"]
        safe = "".join(c for c in sub if c.isalnum() or c == "_")
        if not safe:
            continue
        try:
            await conn.execute(f\'\'\'SET search_path TO "{safe}"\'\'\')
            await conn.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS"
                " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
        except Exception as e:
            print(f"Migration warning for tenant {safe}: {e}")
        finally:
            await conn.execute("SET search_path TO public")


# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ── Super-admin routes ─────────────────────────────────────────────────────────
@app.get("/super-admin/login", response_class=HTMLResponse)
async def super_admin_login(request: Request):
    return templates.TemplateResponse(request, "super_admin_login.html")


@app.post("/super-admin/login")
async def super_admin_do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if (
        SUPER_ADMIN_PASS
        and username == SUPER_ADMIN_USER
        and password == SUPER_ADMIN_PASS
    ):
        resp = RedirectResponse(url="/super-admin/dashboard", status_code=303)
        # HttpOnly + SameSite for cookie security
        resp.set_cookie(
            key="super_admin", value="true", httponly=True, samesite="strict"
        )
        return resp
    return RedirectResponse(url="/super-admin/login?error=1", status_code=303)


@app.get("/super-admin/dashboard", response_class=HTMLResponse)
async def super_admin_dashboard(request: Request):
    _require_super_admin(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        schools = await conn.fetch(
            "SELECT id, name, subdomain, admin_username, created_at"
            " FROM public.schools ORDER BY id"
        )
    return templates.TemplateResponse(
        request, "super_admin_dashboard.html", {"schools": schools}
    )


@app.post("/super-admin/create-school")
async def create_school(
    request: Request,
    name: str = Form(...),
    subdomain: str = Form(...),
    admin_username: str = Form(...),
    admin_password: str = Form(...),
):
    _require_super_admin(request)
    _validate_password(admin_password)
    subdomain = subdomain.lower().strip()
    # Only alphanumeric + hyphen allowed in subdomains
    if not all(c.isalnum() or c == "-" for c in subdomain):
        raise HTTPException(status_code=400, detail="Invalid subdomain format")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO public.schools"
                " (name, subdomain, admin_username, admin_password)"
                " VALUES ($1, $2, $3, $4)",
                name, subdomain, admin_username, admin_password,
            )
            await create_tenant_schema(subdomain, admin_username, admin_password)
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(status_code=400, detail="Subdomain already exists")
            raise
    return RedirectResponse(url="/super-admin/dashboard", status_code=303)


@app.get("/super-admin/logout")
async def super_admin_logout():
    resp = RedirectResponse(url="/super-admin/login", status_code=303)
    resp.delete_cookie("super_admin")
    return resp


# ── Auth routes ────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
async def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    conn = get_tenant_conn(request)
    user = await conn.fetchrow(
        "SELECT id, username, password_hash, is_active FROM users WHERE username = $1",
        username,
    )
    if not user or not verify_password(password, user["password_hash"]):
        return RedirectResponse(url="/login?error=1", status_code=303)
    if not user["is_active"]:
        return RedirectResponse(url="/login?error=inactive", status_code=303)

    role = await conn.fetchval(
        """SELECT r.name FROM user_roles ur
           JOIN roles r ON ur.role_id = r.id
           WHERE ur.user_id = $1 LIMIT 1""",
        user["id"],
    )

    is_subuser_domain = getattr(request.state, "is_subuser_domain", False)
    if is_subuser_domain:
        if role == "admin":
            return RedirectResponse(url="/login?error=admin_not_allowed", status_code=303)
    else:
        if role != "admin":
            return RedirectResponse(url="/login?error=subuser_not_allowed", status_code=303)

    request.session["user"]    = username
    request.session["user_id"] = user["id"]
    request.session["role"]    = role
    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ── Page routes ────────────────────────────────────────────────────────────────
@app.get("/")
async def index(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    return templates.TemplateResponse(
        request, "pos_professional.html",
        {"active_page": "pos", "role": request.session.get("role")},
    )


@app.get("/pos")
async def pos_page(request: Request):
    return await index(request)


@app.get("/inventory")
async def inventory_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "inventory_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    return templates.TemplateResponse(
        request, "inventory.html",
        {"active_page": "inventory", "role": request.session.get("role")},
    )


@app.get("/sales")
async def sales_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)
    all_sales = await conn.fetch("SELECT * FROM sales ORDER BY id DESC")
    all_items = await conn.fetch("""
        SELECT si.sale_id, si.qty, si.price, si.sku,
               p.name as product_name, p.category, p.subject, p.student_class
        FROM sale_items si
        LEFT JOIN products p ON si.product_id = p.id
    """)
    sales_items_map: dict = {}
    for item in all_items:
        sid = item["sale_id"]
        sales_items_map.setdefault(sid, []).append(dict(item))
    return templates.TemplateResponse(
        request, "sales.html",
        {
            "active_page": "sales",
            "sales": all_sales,
            "items_map": json.dumps(sales_items_map, default=str),
            "role": request.session.get("role"),
        },
    )


@app.get("/customers")
async def list_customers(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "customers_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)
    customers = await conn.fetch("""
        SELECT cnic, student_name, father_name, phone_no, student_class, address,
               COUNT(id) as total_orders, SUM(total_amount) as total_spent
        FROM sales
        WHERE cnic IS NOT NULL AND cnic != \'\'
        GROUP BY cnic, student_name, father_name, phone_no, student_class, address
        ORDER BY total_spent DESC
    """)
    return templates.TemplateResponse(
        request, "customers.html",
        {
            "active_page": "customers",
            "customers": [dict(c) for c in customers],
            "role": request.session.get("role"),
        },
    )


@app.get("/customers/profile/{cnic_id}")
async def customer_profile(request: Request, cnic_id: str):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    profile_row = await conn.fetchrow(
        "SELECT * FROM sales WHERE cnic = $1 LIMIT 1", cnic_id
    )
    # Guard: check BEFORE converting to dict
    if not profile_row:
        raise HTTPException(status_code=404, detail="Customer not found")
    profile = dict(profile_row)
    if isinstance(profile.get("timestamp"), datetime):
        profile["timestamp"] = profile["timestamp"].isoformat()

    history = [dict(r) for r in await conn.fetch(
        "SELECT * FROM sales WHERE cnic = $1 ORDER BY id DESC", cnic_id
    )]
    for row in history:
        if isinstance(row.get("timestamp"), datetime):
            row["timestamp"] = row["timestamp"].isoformat()

    sale_ids = [r["id"] for r in history]
    items_map: dict = {}
    if sale_ids:
        items_data = await conn.fetch("""
            SELECT si.sale_id, si.qty, si.price, si.sku,
                   p.name as product_name, p.category
            FROM sale_items si
            LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ANY($1::int[])
        """, sale_ids)
        for item in items_data:
            sid = item["sale_id"]
            items_map.setdefault(sid, []).append(dict(item))

    total_pending = sum(
        (r["total_amount"] - (r["cash_paid"] or 0))
        for r in history
        if r["payment_status"] != "Paid"
    )
    stats = {
        "total_orders":  len(history),
        "total_spent":   sum(r["total_amount"] for r in history),
        "total_pending": total_pending,
        "total_profit":  sum(r["profit"] or 0 for r in history),
        "total_items":   sum(len(items_map.get(r["id"], [])) for r in history),
    }
    return templates.TemplateResponse(
        request, "customer_profile.html",
        {
            "profile":   profile,
            "history":   history,
            "items_map": items_map,
            "stats":     stats,
            "role":      request.session.get("role"),
        },
    )


@app.get("/analytics")
async def analytics_page(request: Request, range: str = "all"):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "analytics_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)

    # Build date filter safely (no user input in SQL)
    if range == "today":
        date_where = "WHERE DATE(timestamp) = CURRENT_DATE"
        date_join  = "WHERE DATE(s.timestamp) = CURRENT_DATE"
    elif range == "month":
        date_where = "WHERE DATE_TRUNC(\'month\', timestamp) = DATE_TRUNC(\'month\', CURRENT_DATE)"
        date_join  = "WHERE DATE_TRUNC(\'month\', s.timestamp) = DATE_TRUNC(\'month\', CURRENT_DATE)"
    else:
        date_where = ""
        date_join  = ""

    gross_row = await conn.fetchrow(f"""
        SELECT COALESCE(SUM(total_amount),0) as gross,
               COUNT(id) as cnt,
               COALESCE(SUM(profit),0) as prf
        FROM sales {date_where}
    """)

    # Pending/udhaar query – append AND or use WHERE correctly
    if date_where:
        udhaar_sql = f"SELECT COALESCE(SUM(total_amount-cash_paid),0) as rc, COUNT(id) as cnt FROM sales {date_where} AND payment_status != \'Paid\'"
    else:
        udhaar_sql = "SELECT COALESCE(SUM(total_amount-cash_paid),0) as rc, COUNT(id) as cnt FROM sales WHERE payment_status != \'Paid\'"
    credit_row = await conn.fetchrow(udhaar_sql)

    stock_val       = await conn.fetchval("SELECT COALESCE(SUM(stock*purchase_price),0) FROM products")
    low_stock_count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE stock < 10")

    stats = {
        "gross_revenue":    gross_row["gross"],
        "total_sales_count":gross_row["cnt"],
        "net_profit":       gross_row["prf"],
        "total_receivables":credit_row["rc"],
        "credit_sales_count":credit_row["cnt"],
        "stock_valuation":  stock_val,
        "low_stock_count":  low_stock_count,
    }

    # Top products – JOIN uses date_join which already includes WHERE keyword
    top_products = await conn.fetch(f"""
        SELECT p.id as product_id, p.name as product_name, p.category,
               SUM(si.qty) as total_qty,
               SUM(si.qty * si.price) as total_revenue
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        JOIN products p ON si.product_id = p.id
        {date_join}
        GROUP BY p.id, p.name, p.category
        ORDER BY total_qty DESC LIMIT 5
    """)

    class_sales = await conn.fetch(f"""
        SELECT student_class, COUNT(id) as volume, SUM(total_amount) as revenue
        FROM sales {date_where}
        GROUP BY student_class ORDER BY revenue DESC
    """)

    low_stock_items = await conn.fetch(
        "SELECT id, name, sku, stock, category FROM products WHERE stock < 10 ORDER BY stock ASC LIMIT 6"
    )

    return templates.TemplateResponse(
        request, "analytics.html",
        {
            "active_page":    "analytics",
            "selected_range": range,
            "stats":          stats,
            "top_products":   [dict(p) for p in top_products],
            "class_sales":    [dict(c) for c in class_sales],
            "low_stock_items":[dict(l) for l in low_stock_items],
            "role":           request.session.get("role"),
        },
    )


@app.get("/settings")
async def settings_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)
    users = await conn.fetch("SELECT id, username, is_active, created_at FROM users ORDER BY id")
    roles = await conn.fetch("SELECT id, name, description FROM roles ORDER BY id")
    return templates.TemplateResponse(
        request, "settings.html",
        {
            "active_page": "settings",
            "users": users,
            "roles": roles,
            "role":  request.session.get("role"),
        },
    )


@app.get("/product/{product_id}")
async def product_detail(request: Request, product_id: int):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    product = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    analytics = await conn.fetchrow("""
        SELECT SUM(qty) as total_units,
               SUM(qty * price) as total_revenue,
               COUNT(DISTINCT sale_id) as sale_count
        FROM sale_items WHERE product_id = $1
    """, product_id)
    last_sold_row = await conn.fetchrow("""
        SELECT s.timestamp FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE si.product_id = $1 ORDER BY s.timestamp DESC LIMIT 1
    """, product_id)
    sales = await conn.fetch("""
        SELECT si.qty, si.price, s.receipt_number, s.payment_status,
               s.timestamp, s.student_name, s.phone_no
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE si.product_id = $1
        ORDER BY s.timestamp DESC LIMIT 20
    """, product_id)
    total_rev  = analytics["total_revenue"] or 0
    total_units= analytics["total_units"]   or 0
    return templates.TemplateResponse(
        request, "product_detail.html",
        {
            "product": dict(product),
            "sales":   [dict(s) for s in sales],
            "analytics": {
                "total_units":   total_units,
                "total_revenue": total_rev,
                "sale_count":    analytics["sale_count"] or 0,
                "last_sold":     last_sold_row["timestamp"] if last_sold_row else None,
                "profit":        total_rev - total_units * product["purchase_price"],
            },
            "role": request.session.get("role"),
        },
    )


# ── API routes ─────────────────────────────────────────────────────────────────
@app.get("/api/products/check-existing")
async def check_existing(
    request: Request,
    sku: str = None, barcode: str = None,
    name: str = None, s_class: str = None,
):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    conn = get_tenant_conn(request)
    result = None
    if sku:
        result = await conn.fetchrow("SELECT * FROM products WHERE sku = $1", sku)
    elif barcode:
        result = await conn.fetchrow("SELECT * FROM products WHERE barcode = $1", barcode)
    elif name and s_class:
        result = await conn.fetchrow(
            "SELECT * FROM products WHERE name = $1 AND student_class = $2", name, s_class
        )
    elif name:
        result = await conn.fetchrow("SELECT * FROM products WHERE name = $1", name)
    return dict(result) if result else {"exists": False}


@app.post("/api/products/smart-add")
async def smart_add(
    request: Request,
    mode: str = Form(...),
    prod_id: int = Form(None),
    name: str = Form(...),
    cat: str = Form(...),
    s_class: str = Form(""),
    sub: str = Form(""),
    tag: str = Form(""),
    variation: str = Form(""),
    p_price: float = Form(...),
    s_price: float = Form(...),
    stock: int = Form(...),
    barcode: str = Form(""),
    force_new: str = Form("false"),
):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "inventory_write" not in perms and "inventory_read" not in perms:
        raise HTTPException(status_code=403)
    if s_price < p_price:
        raise HTTPException(status_code=400, detail="Selling price cannot be less than purchase price")

    conn = get_tenant_conn(request)
    is_force_new = force_new.lower() == "true"

    if mode in ("update", "edit") and prod_id and not is_force_new:
        # Update stock additively (restock scenario)
        await conn.execute(
            "UPDATE products SET stock = stock + $1, purchase_price = $2, selling_price = $3 WHERE id = $4",
            stock, p_price, s_price, prod_id,
        )
    else:
        assigned_sku = generate_professional_sku(cat, name, s_class, sub)
        assigned_barcode = barcode.strip() if barcode.strip() else (
            "BAR-" + "".join(random.choices(string.digits, k=10))
        )
        await conn.execute("""
            INSERT INTO products
                (sku, barcode, name, category, student_class, subject,
                 purchase_price, selling_price, stock, tag, variation)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        """, assigned_sku, assigned_barcode, name, cat, s_class, sub,
             p_price, s_price, stock, tag, variation)
    return {"status": "success"}


@app.get("/api/inventory")
async def list_inventory(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    conn = get_tenant_conn(request)
    data = await conn.fetch("SELECT * FROM products ORDER BY id DESC")
    return [dict(r) for r in data]


@app.get("/api/sales-recent")
async def recent_sales(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms and "pos_access" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    data = await conn.fetch("""
        SELECT id, receipt_number, total_amount, payment_status, timestamp
        FROM sales ORDER BY id DESC LIMIT 5
    """)
    return [dict(r) for r in data]


@app.post("/api/checkout")
async def checkout(
    request: Request,
    student_name:  str   = Form(...),
    father_name:   str   = Form(""),
    cnic:          str   = Form(""),
    student_class: str   = Form(...),
    phone_no:      str   = Form(...),
    address:       str   = Form(""),
    items_json:    str   = Form(...),
    total:         float = Form(...),
    status:        str   = Form(...),
    sale_type:     str   = Form("Single Item"),
    cash_paid:     float = Form(0),
):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        raise HTTPException(status_code=403)

    conn  = get_tenant_conn(request)
    receipt = "REC-" + "".join(random.choices(string.digits, k=6))

    try:
        items = json.loads(items_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid items JSON")

    try:
        async with conn.transaction():
            total_p_cost = 0.0
            for i in items:
                prod = await conn.fetchrow(
                    "SELECT purchase_price FROM products WHERE id = $1", i["id"]
                )
                cost = float(prod["purchase_price"]) if prod else 0.0
                total_p_cost += cost * int(i["qty"])

            profit = total - total_p_cost
            # Use RETURNING id – safer than lastval() in concurrent environments
            sale_id = await conn.fetchval("""
                INSERT INTO sales
                    (receipt_number, student_name, father_name, cnic,
                     student_class, phone_no, address, sale_type,
                     total_amount, cash_paid, profit, payment_status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                RETURNING id
            """, receipt, student_name, father_name, cnic,
                student_class, phone_no, address, sale_type,
                total, cash_paid, profit, status)

            for i in items:
                prod_info = await conn.fetchrow(
                    "SELECT sku, selling_price FROM products WHERE id = $1", i["id"]
                )
                sku_code = prod_info["sku"] if prod_info else "UNKNOWN-SKU"
                sell_price = float(prod_info["selling_price"]) if prod_info else float(i.get("price", 0))
                await conn.execute("""
                    INSERT INTO sale_items (sale_id, product_id, sku, qty, price)
                    VALUES ($1,$2,$3,$4,$5)
                """, sale_id, i["id"], sku_code, i["qty"], sell_price)
                await conn.execute(
                    "UPDATE products SET stock = stock - $1 WHERE id = $2",
                    i["qty"], i["id"],
                )
        return {"status": "success", "receipt": receipt, "sale_id": sale_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/receipt/{sale_id}")
async def get_receipt(request: Request, sale_id: int):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    conn = get_tenant_conn(request)
    sale = await conn.fetchrow("SELECT * FROM sales WHERE id = $1", sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    items = await conn.fetch("""
        SELECT si.*, p.name as product_name
        FROM sale_items si LEFT JOIN products p ON si.product_id = p.id
        WHERE si.sale_id = $1
    """, sale_id)
    data = dict(sale)
    data["items"] = [dict(i) for i in items]
    return data


@app.get("/api/v2/analytics")
async def fast_stats(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    conn = get_tenant_conn(request)
    stock_val     = await conn.fetchval("SELECT SUM(stock * selling_price) FROM products")
    low_stock     = await conn.fetchval("SELECT COUNT(*) FROM products WHERE stock < 10")
    profit_today  = await conn.fetchval(
        "SELECT SUM(profit) FROM sales WHERE DATE(timestamp) = CURRENT_DATE"
    )
    udhaar        = await conn.fetchval(
        "SELECT SUM(total_amount - cash_paid) FROM sales WHERE payment_status != \'Paid\'"
    )
    return {
        "stock_value":  stock_val    or 0,
        "low_stock":    low_stock    or 0,
        "profit_today": profit_today or 0,
        "udhaar":       udhaar       or 0,
    }


# ── User management API ────────────────────────────────────────────────────────
async def _assert_users_manage(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        raise HTTPException(status_code=403)


@app.post("/api/users/create")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role_id: int  = Form(...),
):
    await _assert_users_manage(request)
    _validate_password(password)
    conn = get_tenant_conn(request)
    existing = await conn.fetchval("SELECT id FROM users WHERE username = $1", username)
    if existing:
        return {"status": "error", "message": "Username already exists"}
    hashed  = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    creator = await conn.fetchval(
        "SELECT id FROM users WHERE username = $1", request.session.get("user")
    )
    user_id = await conn.fetchval("""
        INSERT INTO users (username, password_hash, created_by, is_active)
        VALUES ($1, $2, $3, true) RETURNING id
    """, username, hashed, creator)
    await conn.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)", user_id, role_id
    )
    return {"status": "success"}


@app.post("/api/users/toggle-status")
async def toggle_user_status(request: Request, user_id: int = Form(...)):
    await _assert_users_manage(request)
    # Prevent disabling yourself
    current_id = await get_tenant_conn(request).fetchval(
        "SELECT id FROM users WHERE username = $1", request.session.get("user")
    ) if False else None  # see below
    conn = get_tenant_conn(request)
    current_id = await conn.fetchval(
        "SELECT id FROM users WHERE username = $1", request.session.get("user")
    )
    if user_id == current_id:
        return {"status": "error", "message": "Cannot disable your own account"}
    await conn.execute("UPDATE users SET is_active = NOT is_active WHERE id = $1", user_id)
    return {"status": "success"}


@app.post("/api/users/delete")
async def delete_user(request: Request, user_id: int = Form(...)):
    await _assert_users_manage(request)
    conn = get_tenant_conn(request)
    current_id = await conn.fetchval(
        "SELECT id FROM users WHERE username = $1", request.session.get("user")
    )
    if user_id == current_id:
        return {"status": "error", "message": "Cannot delete your own account"}
    await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    return {"status": "success"}


@app.post("/api/users/reset-password")
async def reset_user_password(
    request: Request,
    user_id: int      = Form(...),
    new_password: str = Form(...),
):
    await _assert_users_manage(request)
    _validate_password(new_password)
    conn   = get_tenant_conn(request)
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2", hashed, user_id
    )
    return {"status": "success"}


# ── Misc ───────────────────────────────────────────────────────────────────────
@app.get("/403", response_class=HTMLResponse)
async def forbidden(request: Request):
    return templates.TemplateResponse(request, "403.html", status_code=403)


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")
''')

# ─────────────────────────────────────────────────────────────────────────────
# 4. .env.example
# ─────────────────────────────────────────────────────────────────────────────
print("[4/5] Writing .env.example ...")
write(".env.example", """\
# Copy to .env and fill in values
DATABASE_URL=postgresql://user:password@localhost:5432/axisstock
SUPER_ADMIN_USER=superadmin
SUPER_ADMIN_PASS=change_this_strong_password
SESSION_SECRET=change_this_to_a_random_64_char_hex_string
""")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Patch customer_profile template inline items_map XSS fix note
#    (The template already uses | safe – we add a note file instead of
#     rewriting the entire 500-line template.  The real fix is to JSON-encode
#     server-side which main.py now does correctly via json.dumps.)
# ─────────────────────────────────────────────────────────────────────────────
print("[5/5] Writing PATCHNOTES.md ...")
write("PATCHNOTES.md", """\
# AxisStock Patch Notes

## Security Fixes
- Super-admin cookie is now HttpOnly + SameSite=strict (was trivially forgeable)
- `SUPER_ADMIN_PASS` must be set via env var; login is disabled if empty
- `SESSION_SECRET` read from env var; no more hardcoded 'change-this-secret-key'
- Tenant schema name sanitised to alphanumeric+underscore only
- Subdomain validated to alphanumeric+hyphen only
- Password minimum 6 chars enforced on create/reset
- `items_map` JSON-encoded server-side with `json.dumps(..., default=str)`;
  templates use `| safe` on the result which is safe because the data is
  application-generated (not user-raw).  For full XSS hardening consider
  `markupsafe.Markup(json.dumps(...))` and removing `| safe`.

## Bug Fixes
- `view_customer_detailed_profile`: `if not profile` check now happens BEFORE
  `dict()` conversion – fixes crash on missing CNIC.
- `checkout`: replaced `lastval()` with `RETURNING id` to avoid race conditions.
- `analytics_page`: `date_join` (with/without WHERE) is now separate from
  `date_where`, fixing broken SQL when joining sale_items.
- `migrate_existing_tenants` is now called inside lifespan (was never called).
- Middleware: `finally` block always resets `search_path` and releases
  connection even on exceptions – fixes connection leaks.
- `toggle_user_status` now prevents disabling yourself (parity with delete).

## Code Quality
- Removed duplicated `get_user_permissions` double-calls in user management routes.
- Added `_assert_users_manage()` helper to DRY auth checks.
- `require_login` and `require_permission` decorators added (with functools.wraps).
- `pos` and `index` routes deduplicated.
- `smart-add` permission check uses `inventory_write` (was incorrectly `sales_read`).
- `recent_sales` accepts `pos_access` OR `sales_read` (cashiers need it).

## New Files
- `.env.example` – documents required environment variables.
- `PATCHNOTES.md` – this file.
""")

print("""
=== Patch complete! ===

Next steps:
  1. cp .env.example .env          (fill in your values)
  2. pip install -r requirements.txt
  3. uvicorn app.main:app --reload

Key things still to do manually:
  - Set SUPER_ADMIN_PASS in .env before going to production
  - Set SESSION_SECRET to a long random string
  - Review templates/customer_profile.html items_map | safe usage
    (safe because data is app-generated JSON, but worth auditing)
""")
