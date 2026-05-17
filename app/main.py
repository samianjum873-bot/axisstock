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

@app.on_event("startup")
async def startup_event():
    """Initialize database schema using the exact relational structural specifications"""
    if not os.path.exists("app/database"):
        os.makedirs("app/database")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_id INTEGER,
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    return conn

def is_logged_in(request: Request):
    return True if request.cookies.get("active_user") else False

def generate_professional_sku(category: str, name: str, s_class: str = "", subject: str = ""):
    """Generates automated structural barcode SKU tags for precise tracking"""
    clean_name = "".join([c for c in name if c.isalnum()]).upper()[:5]
    clean_sub = "".join([c for c in subject if c.isalnum()]).upper()[:4] if subject else "GEN"
    clean_class = "".join([c for c in s_class if c.isalnum()]).upper() if s_class else "ALL"
    rand_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    
    cat_lower = category.strip().lower()
    if "book" in cat_lower and "notebook" not in cat_lower:
        return f"BK-{clean_class}-{clean_sub}-{rand_suffix}"
    elif "notebook" in cat_lower:
        return f"NB-{clean_name}-{clean_class}-{rand_suffix}"
    else:
        return f"ST-{clean_name}-{rand_suffix}"

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
    if not user and username == "admin" and password == "admin":
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin','admin')")
        conn.commit()
        user = {"username": "admin"}
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
    
    all_sales = conn.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
    
    items_query = """
        SELECT si.sale_id, si.qty, si.price, si.sku, p.name as product_name, p.category, p.subject, p.student_class
        FROM sale_items si
        LEFT JOIN products p ON si.product_id = p.id
    """
    all_items = conn.execute(items_query).fetchall()
    conn.close()
    
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

# --- SMART RELATIONAL INVENTORY APIs ---

@app.get("/api/products/check-existing")
async def check_existing(sku: str = None, barcode: str = None, name: str = None, s_class: str = None):
    conn = get_db()
    result = None
    if sku:
        result = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    elif barcode:
        result = conn.execute("SELECT * FROM products WHERE barcode = ?", (barcode,)).fetchone()
    elif name and s_class:
        result = conn.execute("SELECT * FROM products WHERE name = ? AND student_class = ?", (name, s_class)).fetchone()
    elif name:
        result = conn.execute("SELECT * FROM products WHERE name = ?", (name,)).fetchone()
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
    barcode: str = Form(""),
    force_new: str = Form("false")
):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db(); cursor = conn.cursor()
    is_force_new = True if force_new.lower() == "true" else False

    if mode == 'update' and prod_id and not is_force_new:
        cursor.execute("UPDATE products SET stock = stock + ?, purchase_price = ?, selling_price = ? WHERE id = ?", 
                       (stock, p_price, s_price, prod_id))
    else:
        assigned_sku = generate_professional_sku(cat, name, s_class, sub)
        assigned_barcode = barcode.strip() if barcode.strip() else "BAR-" + "".join(random.choices(string.digits, k=10))
        
        cursor.execute("""INSERT INTO products 
            (sku, barcode, name, category, student_class, subject, purchase_price, selling_price, stock, tag, variation) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (assigned_sku, assigned_barcode, name, cat, s_class, sub, p_price, s_price, stock, tag, variation))
    
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
        SELECT id, receipt_number, total_amount, payment_status, timestamp
        FROM sales ORDER BY id DESC LIMIT 5
    """).fetchall()
    conn.close()
    return data

@app.post("/api/checkout")
async def checkout(
    request: Request, 
    student_name: str = Form(...), 
    father_name: str = Form(...), 
    cnic: str = Form(""), 
    student_class: str = Form(...), 
    phone_no: str = Form(...), 
    address: str = Form(""), 
    items_json: str = Form(...), 
    total: float = Form(...), 
    status: str = Form(...),
    sale_type: str = Form("Single Item"),
    cash_paid: float = Form(0)
):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db(); cursor = conn.cursor()
    receipt = "REC-" + "".join(random.choices(string.digits, k=6))
    items = json.loads(items_json)
    try:
        total_p_cost = 0
        for i in items:
            prod = cursor.execute("SELECT purchase_price FROM products WHERE id = ?", (i['id'],)).fetchone()
            cost = prod['purchase_price'] if prod else 0
            total_p_cost += float(cost) * int(i['qty'])
            
        profit = total - total_p_cost
        
        cursor.execute("""
            INSERT INTO sales (
                receipt_number, student_name, father_name, cnic, student_class, 
                phone_no, address, sale_type, total_amount, cash_paid, profit, payment_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            receipt, student_name, father_name, cnic, student_class, 
            phone_no, address, sale_type, total, float(cash_paid) if cash_paid else total, profit, status
        ))
        sale_id = cursor.lastrowid
        
        for i in items:
            prod_info = cursor.execute("SELECT sku, selling_price FROM products WHERE id = ?", (i['id'],)).fetchone()
            sku_code = prod_info['sku'] if prod_info else "UNKNOWN-SKU"
            selling_price = float(prod_info['selling_price']) if prod_info else float(i.get('price', 0))
            
            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, sku, qty, price) 
                VALUES (?,?,?,?,?)
            """, (sale_id, i['id'], sku_code, i['qty'], selling_price))
            
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
        raise HTTPException(status_code=404, detail="Sale transaction not found")
    
    items = conn.execute("""
        SELECT si.*, p.name as product_name FROM sale_items si 
        LEFT JOIN products p ON si.product_id = p.id 
        WHERE si.sale_id = ?
    """, (sale_id,)).fetchall()
    conn.close()
    
    receipt_data = {
        "sale_id": sale['id'],
        "receipt_number": sale['receipt_number'],
        "timestamp": sale['timestamp'],
        "student_name": sale['student_name'],
        "father_name": sale['father_name'],
        "cnic": sale['cnic'],
        "student_class": sale['student_class'],
        "phone_no": sale['phone_no'],
        "address": sale['address'],
        "items": items,
        "subtotal": sale['total_amount'],
        "payment_status": sale['payment_status'],
        "cash_paid": sale['cash_paid'] if sale['cash_paid'] else 0
    }
    if sale['payment_status'] in ['Pending', 'CreditSplit']:
        receipt_data["outstanding_balance"] = sale['total_amount'] - (receipt_data["cash_paid"] or 0)
    return receipt_data

@app.get("/api/v2/analytics")
async def get_fast_stats(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    stock_val = conn.execute("SELECT SUM(stock * selling_price) as val FROM products").fetchone()
    low_stock = conn.execute("SELECT COUNT(*) as val FROM products WHERE stock < 10").fetchone()
    profit_today = conn.execute("SELECT SUM(profit) as val FROM sales WHERE date(timestamp) = date('now', 'localtime')").fetchone()
    udhaar = conn.execute("SELECT SUM(total_amount - cash_paid) as val FROM sales WHERE payment_status != 'Paid'").fetchone()
    
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
        raise HTTPException(status_code=404, detail="Product entity not found")

    try:
        analytics = conn.execute("""
            SELECT SUM(qty) as total_units, SUM(qty * price) as total_revenue, 
                   COUNT(DISTINCT sale_id) as sale_count
            FROM sale_items WHERE product_id = ?
        """, (product_id,)).fetchone()

        last_sold_row = conn.execute("""
            SELECT s.timestamp FROM sale_items si 
            JOIN sales s ON si.sale_id = s.id 
            WHERE si.product_id = ? ORDER BY s.timestamp DESC LIMIT 1
        """, (product_id,)).fetchone()
        last_sold = last_sold_row['timestamp'] if last_sold_row else None

        sales = conn.execute("""
            SELECT si.qty, si.price, s.receipt_number, s.payment_status, s.timestamp, s.student_name, s.phone_no
            FROM sale_items si 
            JOIN sales s ON si.sale_id = s.id 
            WHERE si.product_id = ?
            ORDER BY s.timestamp DESC LIMIT 20
        """, (product_id,)).fetchall()
    except Exception as e:
        analytics = {"total_units": 0, "total_revenue": 0, "sale_count": 0}
        last_sold = None
        sales = []

    conn.close()

    total_units = analytics['total_units'] if analytics and analytics.get('total_units') else 0
    total_revenue = analytics['total_revenue'] if analytics and analytics.get('total_revenue') else 0
    sale_count = analytics['sale_count'] if analytics and analytics.get('sale_count') else 0
    
    return templates.TemplateResponse(request, "product_detail.html", {
        "product": product, "sales": sales,
        "analytics": {
            "total_units": total_units, 
            "total_revenue": total_revenue,
            "sale_count": sale_count, 
            "last_sold": last_sold, 
            "profit": total_revenue - (total_units * product['purchase_price'])
        }
    })

@app.get("/customers")
async def list_registered_customers(request: Request):
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    conn = get_db()
    query = """
        SELECT cnic, student_name, father_name, phone_no, student_class, address,
               COUNT(id) as total_orders, SUM(total_amount) as total_spent
        FROM sales WHERE cnic IS NOT NULL AND cnic != '' GROUP BY cnic ORDER BY total_spent DESC
    """
    unique_customers = conn.execute(query).fetchall()
    conn.close()
    return templates.TemplateResponse(request, "customers.html", {"active_page": "customers", "customers": unique_customers})

@app.get("/customers/profile/{cnic_id}")
async def view_customer_detailed_profile(request: Request, cnic_id: str):
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    conn = get_db()
    profile = conn.execute("SELECT * FROM sales WHERE cnic = ? LIMIT 1", (cnic_id,)).fetchone()
    if not profile:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer Data Not Found")
        
    history = conn.execute("SELECT * FROM sales WHERE cnic = ? ORDER BY id DESC", (cnic_id,)).fetchall()
    sale_ids = [row['id'] for row in history]
    items_map = {}
    total_items_count = 0
    
    if sale_ids:
        placeholders = ",".join("?" for _ in sale_ids)
        items_data = conn.execute(f"""
            SELECT si.sale_id, si.qty, si.price, si.sku, p.name as product_name, p.category 
            FROM sale_items si LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id IN ({placeholders})
        """, sale_ids).fetchall()
        
        for item in items_data:
            s_id = item['sale_id']
            if s_id not in items_map: items_map[s_id] = []
            items_map[s_id].append(item)
            total_items_count += item['qty']

    total_pending = sum((row['total_amount'] - (row['cash_paid'] or 0)) for row in history if row['payment_status'] != 'Paid')

    stats_block = {
        "total_orders": len(history), "total_spent": sum(row['total_amount'] for row in history),
        "total_pending": total_pending, "total_profit": sum(row['profit'] for row in history if row['profit']),
        "total_items": total_items_count
    }
    conn.close()
    return templates.TemplateResponse(request, "customer_profile.html", {
        "active_page": "customers", "profile": profile, "history": history, "stats": stats_block, "items_map": json.dumps(items_map)
    })
