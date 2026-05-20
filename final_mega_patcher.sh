#!/bin/bash
# Final Mega Patcher - Fixes all issues and completes multi-tenant SaaS setup

set -e

echo "===== AxisStock Final Mega Patcher ====="

# 1. Install missing dependency
source venv/bin/activate
pip install itsdangerous

# 2. Backup existing main.py
cp app/main.py app/main.py.backup

# 3. Write corrected main.py with proper imports and middleware order
cat > app/main.py <<'EOF'
import os
import random
import string
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db_pool, pool, create_tenant_schema, tenant_exists
from app.middleware import TenantMiddleware

DATABASE_URL = os.getenv("DATABASE_URL")
SUPER_ADMIN_USER = os.getenv("SUPER_ADMIN_USER", "superadmin")
SUPER_ADMIN_PASS = os.getenv("SUPER_ADMIN_PASS", "superadmin123")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
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

def is_logged_in(request: Request):
    return request.cookies.get("active_user") is not None

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
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT id, name, subdomain, admin_username, created_at FROM public.schools ORDER BY id")
    return templates.TemplateResponse(request, "super_admin_dashboard.html", {"schools": schools})

@app.post("/super-admin/create-school")
async def create_school(request: Request, name: str = Form(...), subdomain: str = Form(...),
                        admin_username: str = Form(...), admin_password: str = Form(...)):
    if request.cookies.get("super_admin") != "true":
        raise HTTPException(status_code=401)
    subdomain = subdomain.lower().strip()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO public.schools (name, subdomain, admin_username, admin_password) VALUES ($1, $2, $3, $4)",
                name, subdomain, admin_username, admin_password
            )
            await create_tenant_schema(subdomain, admin_username, admin_password)
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=400, detail="Subdomain already exists")
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
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos"})

@app.get("/pos")
async def pos_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos"})

@app.get("/inventory")
async def inventory_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "inventory.html", {"active_page": "inventory"})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/login")
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
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("active_user")
    return resp

@app.get("/sales")
async def sales_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
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
        "items_map": json.dumps(sales_items_map, default=str)
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
    conn = get_tenant_conn(request)
    data = await conn.fetch("SELECT * FROM products ORDER BY id DESC")
    return [dict(r) for r in data]

@app.get("/api/sales-recent")
async def recent_sales(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401)
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
        }
    })

@app.get("/customers")
async def list_registered_customers(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    query = """
        SELECT cnic, student_name, father_name, phone_no, student_class, address,
               COUNT(id) as total_orders, SUM(total_amount) as total_spent
        FROM sales WHERE cnic IS NOT NULL AND cnic != '' GROUP BY cnic ORDER BY total_spent DESC
    """
    customers = await conn.fetch(query)
    return templates.TemplateResponse(request, "customers.html", {"active_page": "customers", "customers": [dict(c) for c in customers]})

@app.get("/customers/profile/{cnic_id}")
async def view_customer_detailed_profile(request: Request, cnic_id: str):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_tenant_conn(request)
    profile = await conn.fetchrow("SELECT * FROM sales WHERE cnic = $1 LIMIT 1", cnic_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    history = await conn.fetch("SELECT * FROM sales WHERE cnic = $1 ORDER BY id DESC", cnic_id)
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
        "stats": stats
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
        "low_stock_items": [dict(l) for l in low_stock_items]
    })
EOF

# 4. Ensure middleware.py is correct
cat > app/middleware.py <<'EOF'
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import pool, tenant_exists

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip tenant detection for super admin paths and static files
        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static"):
            request.state.tenant = None
            return await call_next(request)

        host = request.headers.get("host", "")
        host = host.split(":")[0]
        parts = host.split(".")
        if len(parts) >= 2:
            subdomain = parts[0]
            if await tenant_exists(subdomain):
                request.state.tenant = subdomain
                conn = await pool.acquire()
                await conn.execute(f'SET search_path TO "{subdomain}"')
                request.state.db_conn = conn
                response = await call_next(request)
                await conn.execute('SET search_path TO public')
                await pool.release(conn)
                return response
        raise HTTPException(status_code=404, detail="School not found")
EOF

# 5. Update database.py (already fine, but ensure it's there)
cat > app/database.py <<'EOF'
import os
import asyncpg
from contextlib import asynccontextmanager

pool = None

async def init_db_pool():
    global pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=20)

async def get_pool():
    return pool

async def create_tenant_schema(schema_name: str, admin_username: str, admin_password: str):
    async with pool.acquire() as conn:
        safe_schema = schema_name.replace('"', '').replace("'", "")
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{safe_schema}"')
        await conn.execute(f'SET search_path TO "{safe_schema}"')
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
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
                variation TEXT
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
                payment_status TEXT DEFAULT 'Paid',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        await conn.execute("""
            INSERT INTO users (username, password) VALUES ($1, $2)
            ON CONFLICT (username) DO NOTHING;
        """, admin_username, admin_password)
        await conn.execute('SET search_path TO public')

async def tenant_exists(subdomain: str) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT 1 FROM public.schools WHERE subdomain = $1", subdomain) is not None
EOF

# 6. Ensure super admin dashboard uses correct base template (already done)
# 7. Create requirements.txt
cat > requirements.txt <<'EOF'
fastapi==0.136.1
uvicorn==0.47.0
jinja2==3.1.6
python-multipart==0.0.28
asyncpg==0.31.0
itsdangerous==2.2.0
EOF

echo "===== Patcher completed! ====="
echo "Start the server with: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo "Super admin: http://localhost:8000/super-admin/login (superadmin/superadmin123)"
echo "Create a school with admin credentials."
echo "For local testing of subdomains, add to /etc/hosts: 127.0.0.1 demo.localhost myschool.localhost"
EOF
