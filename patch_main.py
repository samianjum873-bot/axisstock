import os

clean_code = """from fastapi import FastAPI, Request, Form, HTTPException, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, random, string, json
from datetime import datetime

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "app/database/school_store.db"

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
    return templates.TemplateResponse(request, "index.html")

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
        cursor.execute(\"\"\"INSERT INTO products 
            (name, category, student_class, subject, purchase_price, selling_price, stock, tag, variation) 
            VALUES (?,?,?,?,?,?,?,?,?)\"\"\",
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
    data = conn.execute(\"\"\"
        SELECT s.id, s.receipt_number, s.total_amount, s.payment_status, s.timestamp
        FROM sales s ORDER BY s.id DESC LIMIT 5
    \"\"\").fetchall()
    conn.close()
    return data

@app.post("/api/checkout")
async def checkout(
    request: Request, 
    p_name: str = Form(...), 
    p_phone: str = Form(...), 
    items_json: str = Form(...), 
    total: float = Form(...), 
    status: str = Form(...)
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
            prod = cursor.execute("SELECT purchase_price FROM products WHERE id = ?", (i['id'],)).fetchone()
            cost = prod['purchase_price'] if prod else i.get('purchase_price', 0)
            total_p_cost += float(cost) * int(i['qty'])

        profit = total - total_p_cost

        cursor.execute("INSERT INTO sales (customer_id, receipt_number, total_amount, profit, payment_status) VALUES (?,?,?,?,?)",
                       (c_id, receipt, total, profit, status))
        sale_id = cursor.lastrowid

        for i in items:
            cursor.execute("INSERT INTO sale_items (sale_id, product_name, qty, price) VALUES (?,?,?,?)", 
                           (sale_id, i['name'], i['qty'], i['selling_price']))
            cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))

        conn.commit()
        return {"status": "success", "receipt": receipt}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally: conn.close()

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
"""

with open("app/main.py", "w") as f:
    f.write(clean_code.strip() + "\\n")

print("SUCCESS: app/main.py ko clean kar diya gaya hai bina kisi code change ke!")
