import sqlite3

DB_PATH = "app/database/school_store.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)
    
    # 2. Products Table (With Professional Identity Blueprint)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        barcode TEXT UNIQUE,
        name TEXT NOT NULL,
        category TEXT NOT NULL, -- Stationary, Books, Notebooks
        student_class TEXT,
        subject TEXT,
        purchase_price REAL NOT NULL,
        selling_price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        tag TEXT,
        variation TEXT
    );
    """)
    
    # 3. Sales / Invoice Table
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
    );
    """)
    
    # 4. Sale Items (Relational Mapping using IDs & SKUs)
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
    );
    """)
    
    conn.commit()
    conn.close()
    print("[SUCCESS] Axis Database Engine initialized with professional SKU Identity layers.")

if __name__ == "__main__":
    init_db()
