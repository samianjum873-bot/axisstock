import re

with open("app/main.py", "r") as f:
    content = f.read()

fastapi_smart_add = """@app.post("/api/products/smart-add")
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
    
    # ---------------------------------------------------------
    # WORKFLOW MODE A: MODE IS STRICT UPDATE
    # ---------------------------------------------------------
    if mode == 'update' and prod_id and not is_force_new:
        # Check if updating directly from context resolution window
        cursor.execute("UPDATE products SET stock = stock + ?, purchase_price = ?, selling_price = ? WHERE id = ?", 
                       (stock, p_price, s_price, prod_id))
        conn.commit(); conn.close()
        return {"status": "success", "message": "Product operational assets merged."}

    # ---------------------------------------------------------
    # WORKFLOW MODE B: SMART DUPLICATION SCAN ENGINE
    # ---------------------------------------------------------
    if not is_force_new:
        duplicate_item = None
        
        # Case 1: Strict Structural Context Matching for Course Books & Notebooks
        if cat.strip() in ["Book", "Notebook"]:
            if cat.strip() == "Book":
                cursor.execute('''
                    SELECT id, name, stock, purchase_price, selling_price FROM products 
                    WHERE LOWER(category)=LOWER(?) AND LOWER(student_class)=LOWER(?) AND LOWER(subject)=LOWER(?)
                ''', (cat.strip(), s_class.strip(), sub.strip()))
            else: # Notebooks layout check
                cursor.execute('''
                    SELECT id, name, stock, purchase_price, selling_price FROM products 
                    WHERE LOWER(category)=LOWER(?) AND LOWER(student_class)=LOWER(?)
                ''', (cat.strip(), s_class.strip()))
            duplicate_item = cursor.fetchone()

        # Case 2: Hardware Barcode Engine Lookups
        if not duplicate_item and barcode.strip():
            cursor.execute('SELECT id, name, stock, purchase_price, selling_price FROM products WHERE barcode=?', (barcode.strip(),))
            duplicate_item = cursor.fetchone()

        # Case 3: Sanitized String Content Tokens Match for Stationery / General Ledger
        if not duplicate_item:
            sanitized_target = "".join(name.split()).lower()
            cursor.execute('SELECT id, name, stock, purchase_price, selling_price, category FROM products')
            all_prods = cursor.fetchall()
            for p in all_prods:
                if "".join(p['name'].split()).lower() == sanitized_target and p['category'] == cat:
                    duplicate_item = p
                    break

        # Abort pipeline execution flow if match footprint caught
        if duplicate_item:
            conn.close()
            return {
                "status": "duplicate_found",
                "message": "Similar structural inventory match registered inside live database context.",
                "product": {
                    "id": duplicate_item["id"],
                    "name": duplicate_item["name"],
                    "current_stock": duplicate_item["stock"],
                    "purchase_price": duplicate_item["purchase_price"],
                    "selling_price": duplicate_item["selling_price"]
                }
            }

    # ---------------------------------------------------------
    # WORKFLOW MODE C: EXECUTE FRESH ASSET INSERTION
    # ---------------------------------------------------------
    assigned_sku = generate_professional_sku(cat, name, s_class, sub)
    assigned_barcode = barcode.strip() if barcode.strip() else "BAR-" + "".join(random.choices(string.digits, k=10))
    
    cursor.execute("""INSERT INTO products 
        (sku, barcode, name, category, student_class, subject, purchase_price, selling_price, stock, tag, variation) 
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (assigned_sku, assigned_barcode, name, cat, s_class if s_class else None, sub if sub else None, p_price, s_price, stock, tag, variation))
    
    conn.commit(); conn.close()
    return {"status": "success"}"""

# Search and accurately swap only the target route layout structure logic safely
pattern = r"@app\.post\(\"/api/products/smart-add\"\).*?async def smart_add\(.*?return \{\"status\": \"success\"\}\s*"
content_modified, count = re.subn(pattern, fastapi_smart_add, content, flags=re.DOTALL)

if count > 0:
    with open("app/main.py", "w") as f:
        f.write(content_modified)
    print("SUCCESS: FastAPI smart-add routing algorithm dynamically updated!")
else:
    print("ERROR: Route signature mismatch pattern failed to process automatically.")
