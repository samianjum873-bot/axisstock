import sqlite3
import random
import string
import json
from datetime import datetime, timedelta

DB_PATH = "app/database/school_store.db"

def generate_sku(category, name, s_class="", subject=""):
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

def inject():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing demo data to avoid overlapping/duplicate errors
    cursor.execute("DELETE FROM sale_items;")
    cursor.execute("DELETE FROM sales;")
    cursor.execute("DELETE FROM products;")
    conn.commit()

    print("🧹 Purana demo inventory aur sales data clean ho gaya.")

    classes = [f"Class {i}" for i in range(1, 11)]
    subjects = ["English", "Urdu", "Mathematics", "Science", "Islamiyat", "Computer Science", "Physics", "Chemistry"]
    
    # --- 1. POPULATE INVENTORY ---
    products_list = []
    
    # Books & Notebooks insertion loop
    for c in classes:
        cls_num = int(c.split()[1])
        sub_pool = subjects[:4] if cls_num <= 5 else subjects
        for sub in sub_pool:
            p_price = float(random.randint(120, 250)) if cls_num <= 5 else float(random.randint(250, 480))
            s_price = p_price + random.randint(30, 70)
            products_list.append((f"{sub} Textbook", "Books", c, sub, p_price, s_price, random.randint(80, 150)))
            
            p_nb = float(random.randint(50, 90))
            s_nb = p_nb + random.randint(15, 30)
            products_list.append((f"{sub} Notebook (Single Line)", "Notebooks", c, sub, p_nb, s_nb, random.randint(100, 200)))

    # Premium Stationary Items
    stationary_templates = [
        ("Premium Geometry Box", 150.0, 220.0, "Stationary"),
        ("Scientific Calculator fx-991ES", 850.0, 1200.0, "Stationary"),
        ("Blue Ink Pen (Pack of 10)", 90.0, 150.0, "Stationary"),
        ("Lead Pencils HB (Box)", 70.0, 110.0, "Stationary"),
        ("Eraser & Sharpener Combo Pack", 30.0, 50.0, "Stationary"),
        ("A4 Photocopy Paper Rim", 750.0, 950.0, "Stationary")
    ]
    for name, p_p, s_p, cat in stationary_templates:
        products_list.append((name, cat, "All Classes", "General", p_p, s_p, random.randint(50, 100)))

    # Real Database Injection
    inserted_products = []
    for item in products_list:
        name, cat, s_class, sub, p_price, s_price, stock = item
        sku = generate_sku(cat, name, s_class, sub)
        bar = "BAR-" + "".join(random.choices(string.digits, k=10))
        cursor.execute("""
            INSERT INTO products (sku, barcode, name, category, student_class, subject, purchase_price, selling_price, stock, tag, variation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sku, bar, name, cat, s_class, sub, p_price, s_price, stock, "Academic", "Standard"))
        inserted_products.append({
            "id": cursor.lastrowid, "sku": sku, "name": name, 
            "p_price": p_price, "s_price": s_price, "class": s_class
        })
    print(f"📦 Successfully injected {len(inserted_products)} Standard School Products (1-10 Class).")

    # --- 2. POPULATE STRATEGIC TRANSACTIONS ---
    # Core Regular Customer Profile (Must have 10+ detailed continuous transactions)
    regular_customer = {
        "student_name": "Muhammad Ahmed", "father_name": "Amjad Malik",
        "cnic": "35302-8874125-3", "phone_no": "0300-1234567",
        "student_class": "Class 10", "address": "Mullanpur, Okara Cantt"
    }

    # Secondary Profiles (Mix of regular context and Walk-In scenarios)
    other_customers = [
        {"student_name": "Zainab Fatima", "father_name": "Tariq Mahmood", "cnic": "35302-1145896-4", "phone_no": "0321-7654321", "student_class": "Class 8", "address": "Benazir Colony, Okara"},
        {"student_name": "Ali Raza", "father_name": "Sajid Ali", "cnic": "35302-9963254-1", "phone_no": "0333-9876543", "student_class": "Class 5", "address": "South City, Okara"},
        {"student_name": "Ayesha Bilal", "father_name": "Bilal Siddique", "cnic": "", "phone_no": "0312-4567890", "student_class": "Class 3", "address": "Walk-In Customer"}
    ]

    base_time = datetime.now() - timedelta(days=15)

    # 1. Generate 11 Transactions specifically for the Regular Customer Profile
    print("⚡ Creating 11 clean sequential transactions for Regular Customer (CNIC: 35302-8874125-3)...")
    for idx in range(11):
        txn_time = base_time + timedelta(days=idx, hours=random.randint(1, 5))
        receipt = "REC-" + "".join(random.choices(string.digits, k=6))
        
        # Filter products matching student's current class context or general stationary
        class_prods = [p for p in inserted_products if p['class'] == regular_customer['student_class'] or p['class'] == "All Classes"]
        purchased_items = random.sample(class_prods, k=random.randint(2, 4))
        
        total_amount = 0
        total_cost = 0
        item_entry_list = []
        
        for p in purchased_items:
            qty = random.randint(1, 3)
            total_amount += p['s_price'] * qty
            total_cost += p['p_price'] * qty
            item_entry_list.append({"id": p['id'], "sku": p['sku'], "qty": qty, "price": p['s_price']})
            
            # Deduct active inventory stock logic safely
            cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, p['id']))

        profit = total_amount - total_cost
        
        # Randomize accounting balances (Mix of clean cash and pending udhaar tabs)
        pay_status = random.choice(["Paid", "Paid", "Pending", "CreditSplit"])
        cash_paid = total_amount if pay_status == "Paid" else (total_amount * 0.4 if pay_status == "CreditSplit" else 0.0)

        cursor.execute("""
            INSERT INTO sales (receipt_number, student_name, father_name, cnic, student_class, phone_no, address, sale_type, total_amount, cash_paid, profit, payment_status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (receipt, regular_customer['student_name'], regular_customer['father_name'], regular_customer['cnic'], 
              regular_customer['student_class'], regular_customer['phone_no'], regular_customer['address'], 
              "Bundle Package" if len(item_entry_list) > 2 else "Single Item", total_amount, cash_paid, profit, pay_status, txn_time.strftime('%Y-%m-%d %H:%M:%S')))
        
        sale_id = cursor.lastrowid
        
        for item in item_entry_list:
            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, sku, qty, price)
                VALUES (?, ?, ?, ?, ?)
            """, (sale_id, item['id'], item['sku'], item['qty'], item['price']))

    # 2. Generate Contextual Distributed Sales for remaining user layers
    print("⚡ Populating dynamic baseline sales data mapping for other accounts...")
    for cust in other_customers:
        for day in range(2):
            txn_time = base_time + timedelta(days=random.randint(1, 14), hours=random.randint(1, 8))
            receipt = "REC-" + "".join(random.choices(string.digits, k=6))
            
            class_prods = [p for p in inserted_products if p['class'] == cust['student_class'] or p['class'] == "All Classes"]
            purchased_items = random.sample(class_prods, k=random.randint(1, 3))
            
            total_amount = 0
            total_cost = 0
            item_entry_list = []
            
            for p in purchased_items:
                qty = random.randint(1, 2)
                total_amount += p['s_price'] * qty
                total_cost += p['p_price'] * qty
                item_entry_list.append({"id": p['id'], "sku": p['sku'], "qty": qty, "price": p['s_price']})
                cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, p['id']))

            profit = total_amount - total_cost
            pay_status = "Paid" if not cust['cnic'] else random.choice(["Paid", "Pending"])
            cash_paid = total_amount if pay_status == "Paid" else 0.0

            cursor.execute("""
                INSERT INTO sales (receipt_number, student_name, father_name, cnic, student_class, phone_no, address, sale_type, total_amount, cash_paid, profit, payment_status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (receipt, cust['student_name'], cust['father_name'], cust['cnic'], cust['student_class'], 
                  cust['phone_no'], cust['address'], "Single Item", total_amount, cash_paid, profit, pay_status, txn_time.strftime('%Y-%m-%d %H:%M:%S')))
            
            sale_id = cursor.lastrowid
            for item in item_entry_list:
                cursor.execute("""
                    INSERT INTO sale_items (sale_id, product_id, sku, qty, price)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_id, item['id'], item['sku'], item['qty'], item['price']))

    conn.commit()
    conn.close()
    print("🎯 DEMO DATA INJECTION COMPLETE! Presentation setup ready.")

if __name__ == "__main__":
    inject()
