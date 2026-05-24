#!/usr/bin/env python3

# This restores the complete app/main.py with all API routes
full_main = '''from dotenv import load_dotenv
load_dotenv()

import os
import random
import string
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db_pool, get_pool, create_tenant_schema, tenant_exists
from app.middleware import TenantMiddleware
import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL")
SUPER_ADMIN_USER = os.getenv("SUPER_ADMIN_USER", "superadmin")
SUPER_ADMIN_PASS = os.getenv("SUPER_ADMIN_PASS", "superadmin123")


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

async def lifespan(app: FastAPI):
    await init_db_pool()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE SCHEMA IF NOT EXISTS public;
            CREATE TABLE IF NOT EXISTS public.schools (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                subdomain TEXT UNIQUE NOT NULL,
                admin_username TEXT NOT NULL,
                admin_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        demo_exists = await conn.fetchval("SELECT 1 FROM public.schools WHERE subdomain = 'demo'")
        if not demo_exists:
            await conn.execute(
                "INSERT INTO public.schools (name, subdomain, admin_username, admin_password) VALUES ($1, $2, $3, $4)",
                "Demo School", "demo", "admin", "admin"
            )
            await create_tenant_schema("demo", "admin", "admin")
    yield
    await pool.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key-in-production")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def get_tenant_conn(request: Request):
    if not hasattr(request.state, "db_conn"):
        raise HTTPException(status_code=500, detail="Database connection not available")
    return request.state.db_conn


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

def is_logged_in(request: Request):
    return request.session.get("user") is not None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def generate_professional_sku(category, name, s_class="", subject=""):
    clean_name = "".join(c for c in name if c.isalnum()).upper()[:5]
    clean_sub = "".join(c for c in subject if c.isalnum()).upper()[:4] if subject else "GEN"
    clean_class = "".join(c for c in s_class if c.isalnum()).upper() if s_class else "ALL"
    rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    cat_lower = category.strip().lower()
    if "book" in cat_lower and "notebook" not in cat_lower:
        return f"BK-{clean_class}-{clean_sub}-{rand_suffix}"
    elif "notebook" in cat_lower:
        return f"NB-{clean_name}-{clean_class}-{rand_suffix}"
    else:
        return f"ST-{clean_name}-{rand_suffix}"

# ---------- SUPER ADMIN ROUTES (NO TENANT) ----------
@app.get("/super-admin/login", response_class=HTMLResponse)
async def super_admin_login(request: Request):
    return templates.TemplateResponse(request, "super_admin_login.html")

@app.post("/super-admin/login")
async def super_admin_do_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == SUPER_ADMIN_USER and password == SUPER_ADMIN_PASS:
        resp = RedirectResponse(url="/super-admin/dashboard", status_code=303)
        resp.set_cookie(key="super_admin", value="true")
        return resp
    return RedirectResponse(url="/super-admin/login?error=1", status_code=303)

@app.get("/super-admin/dashboard", response_class=HTMLResponse)
async def super_admin_dashboard(request: Request):
    if request.cookies.get("super_admin") != "true":
        return RedirectResponse(url="/super-admin/login")
    pool = await get_pool()
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT id, name, subdomain, admin_username, created_at FROM public.schools ORDER BY id")
    return templates.TemplateResponse(request, "super_admin_dashboard.html", {"schools": schools})

@app.post("/super-admin/create-school")
async def create_school(request: Request, name: str = Form(...), subdomain: str = Form(...),
                        admin_username: str = Form(...), admin_password: str = Form(...)):
    if request.cookies.get("super_admin") != "true":
        raise HTTPException(status_code=401)
    subdomain = subdomain.lower().strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO public.schools (name, subdomain, admin_username, admin_password) VALUES ($1, $2, $3, $4)",
                name, subdomain, admin_username, admin_password
            )
            await create_tenant_schema(subdomain, admin_username, admin_password)
        except Exception as e:
            if "unique constraint" in str(e).lower():
                raise HTTPException(status_code=400, detail="Subdomain already exists")
            raise
    return RedirectResponse(url="/super-admin/dashboard", status_code=303)

@app.get("/super-admin/logout")
async def super_admin_logout():
    resp = RedirectResponse(url="/super-admin/login", status_code=303)
    resp.delete_cookie("super_admin")
    return resp

# ---------- TENANT ROUTES (protected) ----------
@app.get("/")
async def index(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    role = request.session.get("role")
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos", "role": role})

@app.get("/pos")
async def pos_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "pos_access" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    role = request.session.get("role")
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos", "role": role})

@app.get("/inventory")
async def inventory_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "inventory_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    role = request.session.get("role")
    return templates.TemplateResponse(request, "inventory.html", {"active_page": "inventory", "role": role})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/login")
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
    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/sales")
async def sales_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)
    all_sales = await conn.fetch("SELECT * FROM sales ORDER BY id DESC")
    items_query = """
        SELECT si.sale_id, si.qty, si.price, si.sku, p.name as product_name, p.category, p.subject, p.student_class
        FROM sale_items si
        LEFT JOIN products p ON si.product_id = p.id
    """
    all_items = await conn.fetch(items_query)
    sales_items_map = {}
    for item in all_items:
        s_id = item['sale_id']
        if s_id not in sales_items_map:
            sales_items_map[s_id] = []
        sales_items_map[s_id].append(dict(item))
    return templates.TemplateResponse(request, "sales.html", {
        "active_page": "sales",
        "sales": all_sales,
        "items_map": json.dumps(sales_items_map, default=str),
        "role": request.session.get("role")
    })

@app.get("/api/products/check-existing")
async def check_existing(request: Request, sku: str = None, barcode: str = None, name: str = None, s_class: str = None):
    conn = get_tenant_conn(request)
    if sku:
        result = await conn.fetchrow("SELECT * FROM products WHERE sku = $1", sku)
    elif barcode:
        result = await conn.fetchrow("SELECT * FROM products WHERE barcode = $1", barcode)
    elif name and s_class:
        result = await conn.fetchrow("SELECT * FROM products WHERE name = $1 AND student_class = $2", name, s_class)
    elif name:
        result = await conn.fetchrow("SELECT * FROM products WHERE name = $1", name)
    else:
        result = None
    return result if result else {"exists": False}

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
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    is_force_new = force_new.lower() == "true"
    if mode in ['update', 'edit'] and prod_id and not is_force_new:
        await conn.execute("UPDATE products SET stock = stock + $1, purchase_price = $2, selling_price = $3 WHERE id = $4",
                           stock, p_price, s_price, prod_id)
    else:
        assigned_sku = generate_professional_sku(cat, name, s_class, sub)
        assigned_barcode = barcode.strip() if barcode.strip() else "BAR-" + "".join(random.choices(string.digits, k=10))
        await conn.execute("""
            INSERT INTO products (sku, barcode, name, category, student_class, subject, purchase_price, selling_price, stock, tag, variation)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        """, assigned_sku, assigned_barcode, name, cat, s_class, sub, p_price, s_price, stock, tag, variation)
    return {"status": "success"}

@app.get("/api/inventory")
async def list_inv(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    data = await conn.fetch("SELECT * FROM products ORDER BY id DESC")
    return [dict(r) for r in data]

@app.get("/api/sales-recent")
async def recent_sales(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
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
    student_name: str = Form(...),
    father_name: str = Form(""),
    cnic: str = Form(""),
    student_class: str = Form(...),
    phone_no: str = Form(...),
    address: str = Form(""),
    items_json: str = Form(...),
    total: float = Form(...),
    status: str = Form(...),
    sale_type: str = Form("Single Item"),
    cash_paid: float = Form(0),
):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    receipt = "REC-" + "".join(random.choices(string.digits, k=6))
    items = json.loads(items_json)
    try:
        async with conn.transaction():
            total_p_cost = 0
            for i in items:
                prod = await conn.fetchrow("SELECT purchase_price FROM products WHERE id = $1", i['id'])
                cost = prod['purchase_price'] if prod else 0
                total_p_cost += float(cost) * int(i['qty'])
            profit = total - total_p_cost
            await conn.execute("""
                INSERT INTO sales (receipt_number, student_name, father_name, cnic, student_class, phone_no, address, sale_type, total_amount, cash_paid, profit, payment_status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """, receipt, student_name, father_name, cnic, student_class, phone_no, address, sale_type, total, cash_paid, profit, status)
            sale_id = await conn.fetchval("SELECT lastval()")
            for i in items:
                prod_info = await conn.fetchrow("SELECT sku, selling_price FROM products WHERE id = $1", i['id'])
                sku_code = prod_info['sku'] if prod_info else "UNKNOWN-SKU"
                selling_price = float(prod_info['selling_price']) if prod_info else float(i.get('price', 0))
                await conn.execute("""
                    INSERT INTO sale_items (sale_id, product_id, sku, qty, price)
                    VALUES ($1,$2,$3,$4,$5)
                """, sale_id, i['id'], sku_code, i['qty'], selling_price)
                await conn.execute("UPDATE products SET stock = stock - $1 WHERE id = $2", i['qty'], i['id'])
            return {"status": "success", "receipt": receipt, "sale_id": sale_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/receipt/{sale_id}")
async def get_receipt(request: Request, sale_id: int):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    sale = await conn.fetchrow("SELECT * FROM sales WHERE id = $1", sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Sale transaction not found")
    items = await conn.fetch("""
        SELECT si.*, p.name as product_name FROM sale_items si
        LEFT JOIN products p ON si.product_id = p.id
        WHERE si.sale_id = $1
    """, sale_id)
    receipt_data = dict(sale)
    receipt_data["items"] = [dict(i) for i in items]
    return receipt_data

@app.get("/api/v2/analytics")
async def get_fast_stats(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    stock_val = await conn.fetchval("SELECT SUM(stock * selling_price) FROM products")
    low_stock = await conn.fetchval("SELECT COUNT(*) FROM products WHERE stock < 10")
    profit_today = await conn.fetchval("SELECT SUM(profit) FROM sales WHERE DATE(timestamp) = CURRENT_DATE")
    udhaar = await conn.fetchval("SELECT SUM(total_amount - cash_paid) FROM sales WHERE payment_status != 'Paid'")
    return {
        "stock_value": stock_val or 0,
        "low_stock": low_stock or 0,
        "profit_today": profit_today or 0,
        "udhaar": udhaar or 0
    }

@app.get("/product/{product_id}")
async def product_detail(request: Request, product_id: int):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    product = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    analytics = await conn.fetchrow("""
        SELECT SUM(qty) as total_units, SUM(qty * price) as total_revenue, COUNT(DISTINCT sale_id) as sale_count
        FROM sale_items WHERE product_id = $1
    """, product_id)
    last_sold_row = await conn.fetchrow("""
        SELECT s.timestamp FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE si.product_id = $1 ORDER BY s.timestamp DESC LIMIT 1
    """, product_id)
    last_sold = last_sold_row['timestamp'] if last_sold_row else None
    sales = await conn.fetch("""
        SELECT si.qty, si.price, s.receipt_number, s.payment_status, s.timestamp, s.student_name, s.phone_no
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE si.product_id = $1
        ORDER BY s.timestamp DESC LIMIT 20
    """, product_id)
    return templates.TemplateResponse(request, "product_detail.html", {
        "product": dict(product),
        "sales": [dict(s) for s in sales],
        "analytics": {
            "total_units": analytics['total_units'] or 0,
            "total_revenue": analytics['total_revenue'] or 0,
            "sale_count": analytics['sale_count'] or 0,
            "last_sold": last_sold,
            "profit": (analytics['total_revenue'] or 0) - (analytics['total_units'] or 0) * product['purchase_price']
        },
        "role": request.session.get("role")
    })

@app.get("/customers")
async def list_registered_customers(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    perms = await get_user_permissions(request)
    if "customers_read" not in perms:
        return templates.TemplateResponse(request, "403.html", status_code=403)
    conn = get_tenant_conn(request)
    # Fixed PostgreSQL GROUP BY query
    query = """
        SELECT cnic, student_name, father_name, phone_no, student_class, address,
               COUNT(id) as total_orders, SUM(total_amount) as total_spent
        FROM sales
        WHERE cnic IS NOT NULL AND cnic != ''
        GROUP BY cnic, student_name, father_name, phone_no, student_class, address
        ORDER BY total_spent DESC
    """
    customers = await conn.fetch(query)
    return templates.TemplateResponse(request, "customers.html", {"active_page": "customers", "customers": [dict(c) for c in customers], "role": request.session.get("role")})

@app.get("/customers/profile/{cnic_id}")
async def view_customer_detailed_profile(request: Request, cnic_id: str):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    profile = await conn.fetchrow("SELECT * FROM sales WHERE cnic = $1 LIMIT 1", cnic_id)
    profile = dict(profile)
    if isinstance(profile.get("timestamp"), datetime):
        profile["timestamp"] = profile["timestamp"].isoformat()
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    history = await conn.fetch("SELECT * FROM sales WHERE cnic = $1 ORDER BY id DESC", cnic_id)
    # Convert datetime objects to string for JSON serialization
    history = [dict(row) for row in history]
    for row in history:
        if isinstance(row.get("timestamp"), datetime):
            row["timestamp"] = row["timestamp"].isoformat()
    sale_ids = [row['id'] for row in history]
    items_map = {}
    if sale_ids:
        items_data = await conn.fetch("""
            SELECT si.sale_id, si.qty, si.price, si.sku, p.name as product_name, p.category
            FROM sale_items si LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ANY($1::int[])
        """, sale_ids)
        for item in items_data:
            s_id = item['sale_id']
            if s_id not in items_map:
                items_map[s_id] = []
            items_map[s_id].append(dict(item))
    total_pending = sum((row['total_amount'] - (row['cash_paid'] or 0)) for row in history if row['payment_status'] != 'Paid')
    stats = {
        "total_orders": len(history),
        "total_spent": sum(row['total_amount'] for row in history),
        "total_pending": total_pending,
        "total_profit": sum(row['profit'] or 0 for row in history),
        "total_items": sum(len(items_map.get(row['id'], [])) for row in history)
    }
    return templates.TemplateResponse(request, "customer_profile.html", {
        "profile": dict(profile),
        "history": [dict(h) for h in history],
        "items_map": items_map,
        "stats": stats,
        "role": request.session.get("role")
    })

@app.get("/analytics")
async def operations_analytics_dashboard(request: Request, range: str = "all"):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    date_filter = ""
    if range == "today":
        date_filter = "WHERE DATE(timestamp) = CURRENT_DATE"
    elif range == "month":
        date_filter = "WHERE DATE_TRUNC('month', timestamp) = DATE_TRUNC('month', CURRENT_DATE)"
    gross_row = await conn.fetchrow(f"SELECT COALESCE(SUM(total_amount),0) as gross, COUNT(id) as cnt, COALESCE(SUM(profit),0) as prf FROM sales {date_filter}")
    gross_revenue = gross_row['gross']
    total_sales_count = gross_row['cnt']
    net_profit = gross_row['prf']
    if date_filter:
        udhaar_query = f"SELECT COALESCE(SUM(total_amount - cash_paid),0) as rc, COUNT(id) as cnt FROM sales {date_filter} AND payment_status != 'Paid'"
    else:
        udhaar_query = "SELECT COALESCE(SUM(total_amount - cash_paid),0) as rc, COUNT(id) as cnt FROM sales WHERE payment_status != 'Paid'"
    credit_row = await conn.fetchrow(udhaar_query)
    total_receivables = credit_row['rc']
    credit_sales_count = credit_row['cnt']
    stock_val = await conn.fetchval("SELECT COALESCE(SUM(stock * purchase_price),0) FROM products")
    low_stock_count = await conn.fetchval("SELECT COUNT(*) FROM products WHERE stock < 10")
    stats = {
        "gross_revenue": gross_revenue,
        "total_sales_count": total_sales_count,
        "net_profit": net_profit,
        "total_receivables": total_receivables,
        "credit_sales_count": credit_sales_count,
        "stock_valuation": stock_val,
        "low_stock_count": low_stock_count
    }
    top_products = await conn.fetch(f"""
        SELECT p.id as product_id, p.name as product_name, p.category, SUM(si.qty) as total_qty, SUM(si.qty * si.price) as total_revenue
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        JOIN products p ON si.product_id = p.id
        {date_filter}
        GROUP BY si.product_id, p.id, p.name, p.category
        ORDER BY total_qty DESC LIMIT 5
    """)
    class_sales = await conn.fetch(f"""
        SELECT student_class, COUNT(id) as volume, SUM(total_amount) as revenue
        FROM sales {date_filter} GROUP BY student_class ORDER BY revenue DESC
    """)
    low_stock_items = await conn.fetch("SELECT id, name, sku, stock, category FROM products WHERE stock < 10 ORDER BY stock ASC LIMIT 6")
    return templates.TemplateResponse(request, "analytics.html", {
        "active_page": "analytics",
        "selected_range": range,
        "stats": stats,
        "top_products": [dict(p) for p in top_products],
        "class_sales": [dict(c) for c in class_sales],
        "low_stock_items": [dict(l) for l in low_stock_items],
        "role": request.session.get("role")
    })


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
        "roles": roles,
        "role": request.session.get("role")
    })

@app.post("/api/users/create")
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
    return {"status": "success"}

@app.post("/api/users/toggle-status")
async def toggle_user_status(request: Request, user_id: int = Form(...)):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
    perms = await get_user_permissions(request)
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
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
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
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
    if "sales_read" not in perms:
        raise HTTPException(status_code=403)
    perms = await get_user_permissions(request)
    if "users_manage" not in perms:
        raise HTTPException(status_code=403)
    conn = get_tenant_conn(request)
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", hashed, user_id)
    return {"status": "success"}


@app.get("/403", response_class=HTMLResponse)
async def forbidden(request: Request):
    return templates.TemplateResponse(request, "403.html")

@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")
'''

with open("app/main.py", "w") as f:
    f.write(full_main)
print("✅ Full main.py restored with all API endpoints")
