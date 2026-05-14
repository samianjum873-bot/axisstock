from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, random, string, json
from datetime import datetime

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "app/database/school_store.db"

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description): d[col[0]] = row[idx]
    return d

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

# --- INVENTORY & SETS ---
@app.post("/api/products/add")
async def add_p(name:str=Form(...), cat:str=Form(...), s_class:str=Form(...), sub:str=Form(...), p_price:float=Form(...), s_price:float=Form(...), stock:int=Form(...)):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, category, student_class, subject, purchase_price, selling_price, stock) VALUES (?,?,?,?,?,?,?)",
                 (name, cat, s_class, sub, p_price, s_price, stock))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/api/inventory")
async def list_inv():
    conn = get_db()
    data = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return data

@app.post("/api/bundles/create")
async def make_bundle(name:str=Form(...), s_class:str=Form(...), price:float=Form(...)):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT INTO bundles (name, student_class, price) VALUES (?,?,?)", (name, s_class, price))
    b_id = cursor.lastrowid
    # Auto-link all products of this class to this bundle
    prods = conn.execute("SELECT id FROM products WHERE student_class = ?", (s_class,)).fetchall()
    for p in prods:
        cursor.execute("INSERT INTO bundle_items (bundle_id, product_id) VALUES (?,?)", (b_id, p['id']))
    conn.commit(); conn.close()
    return {"status": "success"}

# --- POS SYSTEM (WITH UDHAAR) ---
@app.post("/api/checkout")
async def checkout(
    p_name:str=Form(...), p_phone:str=Form(...), s_name:str=Form(...), 
    items_json:str=Form(...), total:float=Form(...), status:str=Form(...)
):
    conn = get_db(); cursor = conn.cursor()
    receipt = "REC-" + "".join(random.choices(string.digits, k=6))
    items = json.loads(items_json) # List of {id, name, qty, type, s_price, p_price}
    
    try:
        # 1. Handle Customer
        cursor.execute("INSERT INTO customers (name, phone, student_name) VALUES (?,?,?)", (p_name, p_phone, s_name))
        c_id = cursor.lastrowid
        
        # 2. Calculate Profit
        total_p_price = sum(float(i['p_price']) * int(i['qty']) for i in items)
        profit = total - total_p_price
        
        # 3. Create Sale
        cursor.execute("INSERT INTO sales (customer_id, receipt_number, total_amount, profit, payment_status) VALUES (?,?,?,?,?)",
                       (c_id, receipt, total, profit, status))
        sale_id = cursor.lastrowid
        
        # 4. Deduct Stock & Save Details
        for i in items:
            cursor.execute("INSERT INTO sale_items (sale_id, product_name, qty, price) VALUES (?,?,?,?)", 
                           (sale_id, i['name'], i['qty'], i['s_price']))
            if i['type'] == 'single':
                cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
            else:
                # Deduct all items in bundle
                sub_items = conn.execute("SELECT product_id FROM bundle_items WHERE bundle_id = ?", (i['id'],)).fetchall()
                for si in sub_items:
                    cursor.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (si['product_id'],))
        
        conn.commit()
        return {"status": "success", "receipt": receipt}
    except Exception as e:
        conn.rollback(); return {"status": "error", "message": str(e)}
    finally: conn.close()

# --- REPORTS ---
@app.get("/api/reports/summary")
async def report():
    conn = get_db()
    total_sales = conn.execute("SELECT SUM(total_amount) as total FROM sales").fetchone()['total'] or 0
    total_profit = conn.execute("SELECT SUM(profit) as profit FROM sales").fetchone()['profit'] or 0
    udhaar = conn.execute("SELECT SUM(total_amount) as total FROM sales WHERE payment_status = 'Pending'").fetchone()['total'] or 0
    conn.close()
    return {"sales": total_sales, "profit": total_profit, "udhaar": udhaar}
