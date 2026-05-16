from fastapi import FastAPI, Request, Form, HTTPException, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, random, string, json
from datetime import datetime
import os

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "app/database/school_store.db"

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database schema on app startup"""
    if not os.path.exists("app/database"):
        os.makedirs("app/database")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            student_class TEXT,
            subject TEXT,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock INTEGER NOT NULL,
            tag TEXT,
            variation TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            receipt_number TEXT UNIQUE NOT NULL,
            total_amount REAL NOT NULL,
            cash_paid REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Paid',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id)
        )
    """)
    
    # Add cash_paid column if it doesn't exist (migration)
    cursor.execute("PRAGMA table_info(sales)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'cash_paid' not in columns:
        cursor.execute("ALTER TABLE sales ADD COLUMN cash_paid REAL DEFAULT 0")
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    return conn

def is_logged_in(request: Request):
    user = request.cookies.get("active_user")
    return True if user else False

@app.get("/")
async def index(request: Request):
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos"})

@app.get("/pos")
async def pos_page(request: Request):
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "pos_professional.html", {"active_page": "pos"})

@app.get("/inventory")
async def inventory_page(request: Request):
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "inventory.html", {"active_page": "inventory"})

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/login")
async def do_login(response: Response, username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
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
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    conn = get_db()
    # Fetch all sales joined with customer details
    query = """
        SELECT s.id, s.receipt_number, s.total_amount, s.cash_paid, s.profit, 
               s.payment_status, s.timestamp, c.name as customer_name, c.phone as customer_phone
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        ORDER BY s.id DESC
    """
    all_sales = conn.execute(query).fetchall()
    
    # Fetch all items linked to sales for the detail modal breakdown
    items_query = """
        SELECT si.sale_id, si.product_name, si.qty, si.price, p.category
        FROM sale_items si
        LEFT JOIN products p ON si.product_name = p.name
    """
    all_items = conn.execute(items_query).fetchall()
    conn.close()
    
    # Structure items by sale_id for lightning-fast JS lookups
    sales_items_map = {}
    for item in all_items:
        s_id = item['sale_id']
        if s_id not in sales_items_map:
            sales_items_map[s_id] = []
        sales_items_map[s_id].append(item)

    return templates.TemplateResponse(request, "sales.html", {
        "active_page": "sales",
        "sales": all_sales,
        "items_map": json.dumps(sales_items_map)
    })

# --- SMART INVENTORY APIs ---

@app.get("/api/products/check-existing")
async def check_existing(tag: str = None, name: str = None, s_class: str = None):
    conn = get_db()
    result = None
    if tag and name: 
        result = conn.execute("SELECT * FROM products WHERE name = ? AND tag = ?", (name, tag)).fetchone()
    elif name and s_class:
        result = conn.execute("SELECT * FROM products WHERE name = ? AND student_class = ?", (name, s_class)).fetchone()
    conn.close()
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
    force_new: str = Form("false")
):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db(); cursor = conn.cursor()
    is_force_new = True if force_new.lower() == "true" else False

    if mode == 'update' and prod_id and not is_force_new:
        cursor.execute("UPDATE products SET stock = stock + ?, purchase_price = ?, selling_price = ? WHERE id = ?", 
                       (stock, p_price, s_price, prod_id))
    else:
        cursor.execute("""INSERT INTO products 
            (name, category, student_class, subject, purchase_price, selling_price, stock, tag, variation) 
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (name, cat, s_class, sub, p_price, s_price, stock, tag, variation))
    
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/api/inventory")
async def list_inv(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    data = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return data

@app.get("/api/sales-recent")
async def recent_sales(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    data = conn.execute("""
        SELECT s.id, s.receipt_number, s.total_amount, s.payment_status, s.timestamp
        FROM sales s ORDER BY s.id DESC LIMIT 5
    """).fetchall()
    conn.close()
    return data

@app.post("/api/checkout")
async def checkout(
    request: Request, 
    p_name: str = Form(...), 
    p_phone: str = Form(...), 
    items_json: str = Form(...), 
    total: float = Form(...), 
    status: str = Form(...),
    p_father_name: str = Form(""),
    p_class: str = Form(""),
    cash_paid: float = Form(0)
):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db(); cursor = conn.cursor()
    receipt = "REC-" + "".join(random.choices(string.digits, k=6))
    items = json.loads(items_json)
    try:
        cursor.execute("INSERT INTO customers (name, phone) VALUES (?,?)", (p_name, p_phone))
        c_id = cursor.lastrowid
        
        total_p_cost = 0
        for i in items:
            if 'id' in i and i['id']:
                prod = cursor.execute("SELECT purchase_price FROM products WHERE id = ?", (i['id'],)).fetchone()
                cost = prod['purchase_price'] if prod else float(i.get('purchase_price', 0))
            else:
                cost = float(i.get('purchase_price', 0))
            total_p_cost += float(cost) * int(i['qty'])
            
        profit = total - total_p_cost
        
        cursor.execute("INSERT INTO sales (customer_id, receipt_number, total_amount, cash_paid, profit, payment_status) VALUES (?,?,?,?,?,?)",
                       (c_id, receipt, total, float(cash_paid) if cash_paid else total, profit, status))
        sale_id = cursor.lastrowid
        
        for i in items:
            selling_price = float(i.get('selling_price', 0))
            cursor.execute("INSERT INTO sale_items (sale_id, product_name, qty, price) VALUES (?,?,?,?)", 
                           (sale_id, i['name'], i['qty'], selling_price))
            cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
            
        conn.commit()
        return {"status": "success", "receipt": receipt, "sale_id": sale_id}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally: conn.close()

@app.get("/api/receipt/{sale_id}")
async def get_receipt(request: Request, sale_id: int):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    
    sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if not sale:
        conn.close()
        raise HTTPException(status_code=404, detail="Sale not found")
    
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", (sale['customer_id'],)).fetchone()
    items = conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
    
    conn.close()
    
    receipt_data = {
        "sale_id": sale['id'],
        "receipt_number": sale['receipt_number'],
        "timestamp": sale['timestamp'],
        "customer": customer,
        "items": items,
        "subtotal": sale['total_amount'],
        "payment_status": sale['payment_status'],
        "cash_paid": sale['cash_paid'] if 'cash_paid' in sale and sale['cash_paid'] else 0
    }
    
    if sale['payment_status'] == 'Pending' or sale['payment_status'] == 'CreditSplit':
        receipt_data["outstanding_balance"] = sale['total_amount'] - (receipt_data["cash_paid"] or 0)
    
    return receipt_data

@app.get("/api/v2/analytics")
async def get_fast_stats(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    stock_val = conn.execute("SELECT SUM(stock * selling_price) as val FROM products").fetchone()
    low_stock = conn.execute("SELECT COUNT(*) as val FROM products WHERE stock < 10").fetchone()
    profit_today = conn.execute("SELECT SUM(profit) as val FROM sales WHERE date(timestamp) = date('now', 'localtime')").fetchone()
    udhaar = conn.execute("SELECT SUM(total_amount) as val FROM sales WHERE payment_status != 'Paid'").fetchone()
    
    stats = {
        "stock_value": stock_val['val'] if stock_val['val'] else 0,
        "low_stock": low_stock['val'] if low_stock['val'] else 0,
        "profit_today": profit_today['val'] if profit_today['val'] else 0,
        "udhaar": udhaar['val'] if udhaar['val'] else 0
    }
    conn.close()
    return stats

@app.get("/product/{product_id}")
async def product_detail(request: Request, product_id: int):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    analytics = conn.execute("""
        SELECT
            SUM(si.qty) as total_units,
            SUM(si.qty * si.price) as total_revenue,
            MAX(s.timestamp) as last_sold,
            COUNT(*) as sale_count
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE si.product_name = ?
    """, (product['name'],)).fetchone()

    sales = conn.execute("""
        SELECT si.qty, si.price, s.receipt_number, s.payment_status, s.timestamp,
               c.name as customer_name, c.phone as customer_phone
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE si.product_name = ?
        ORDER BY s.timestamp DESC
        LIMIT 20
    """, (product['name'],)).fetchall()

    conn.close()

    total_units = analytics['total_units'] if analytics['total_units'] else 0
    total_revenue = analytics['total_revenue'] if analytics['total_revenue'] else 0
    sale_count = analytics['sale_count'] if analytics['sale_count'] else 0
    last_sold = analytics['last_sold']
    profit = total_revenue - (total_units * product['purchase_price']) if total_units else 0

    return templates.TemplateResponse(request, "product_detail.html", {
        "product": product,
        "sales": sales,
        "analytics": {
            "total_units": total_units,
            "total_revenue": total_revenue,
            "sale_count": sale_count,
            "last_sold": last_sold,
            "profit": profit
        }
    })
