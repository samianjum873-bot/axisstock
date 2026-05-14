from fastapi import FastAPI, Request, Form, HTTPException, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3, random, string, json

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "app/database/school_store.db"

# Database Helper
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    return conn

# AUTH CHECK: Check if user is logged in via cookies
def is_logged_in(request: Request):
    user = request.cookies.get("active_user")
    if not user:
        return False
    return True

# --- ROUTES ---

@app.get("/")
async def index(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
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

# --- API ENDPOINTS (Protected) ---

@app.post("/api/products/add")
async def add_p(request: Request, name:str=Form(...), cat:str=Form(...), s_class:str=Form(...), sub:str=Form(...), p_price:float=Form(...), s_price:float=Form(...), stock:int=Form(...)):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, category, student_class, subject, purchase_price, selling_price, stock) VALUES (?,?,?,?,?,?,?)",
                 (name, cat, s_class, sub, p_price, s_price, stock))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/api/inventory")
async def list_inv(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    data = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return data

@app.post("/api/checkout")
async def checkout(request: Request, p_name:str=Form(...), p_phone:str=Form(...), items_json:str=Form(...), total:float=Form(...), status:str=Form(...)):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db(); cursor = conn.cursor()
    receipt = "REC-" + "".join(random.choices(string.digits, k=6))
    items = json.loads(items_json)
    try:
        cursor.execute("INSERT INTO customers (name, phone) VALUES (?,?)", (p_name, p_phone))
        c_id = cursor.lastrowid
        total_p_price = sum(float(i['p_price']) * int(i['qty']) for i in items)
        profit = total - total_p_price
        cursor.execute("INSERT INTO sales (customer_id, receipt_number, total_amount, profit, payment_status) VALUES (?,?,?,?,?)",
                       (c_id, receipt, total, profit, status))
        sale_id = cursor.lastrowid
        for i in items:
            cursor.execute("INSERT INTO sale_items (sale_id, product_name, qty, price) VALUES (?,?,?,?)", (sale_id, i['name'], i['qty'], i['s_price']))
            cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
        conn.commit()
        return {"status": "success", "receipt": receipt}
    except Exception as e:
        conn.rollback(); return {"status": "error", "message": str(e)}
    finally: conn.close()

@app.get("/api/reports/summary")
async def report(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    total_sales = conn.execute("SELECT SUM(total_amount) as total FROM sales").fetchone()['total'] or 0
    total_profit = conn.execute("SELECT SUM(profit) as profit FROM sales").fetchone()['profit'] or 0
    udhaar = conn.execute("SELECT SUM(total_amount) as total FROM sales WHERE payment_status = 'Pending'").fetchone()['total'] or 0
    conn.close()
    return {"sales": total_sales, "profit": total_profit, "udhaar": udhaar}
