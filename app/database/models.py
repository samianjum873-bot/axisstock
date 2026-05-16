import sqlite3

DB_PATH = "app/database/school_store.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Inventory Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL,
        student_class TEXT NOT NULL,
        price REAL NOT NULL,
        total_stock INTEGER NOT NULL,
        remaining_stock INTEGER NOT NULL
    );
    """)
    
    # 2. Bundles Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bundles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bundle_name TEXT NOT NULL,
        student_class TEXT NOT NULL UNIQUE,
        total_price REAL NOT NULL
    );
    """)
    
    # 3. Bundle Items Mapping
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bundle_items (
        bundle_id INTEGER,
        item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        FOREIGN KEY(bundle_id) REFERENCES bundles(id),
        FOREIGN KEY(item_id) REFERENCES inventory(id),
        PRIMARY KEY (bundle_id, item_id)
    );
    """)
    
    # 4. Sales/Transactions Table (Fully Updated for Analytics & POS Billing v2)
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
        profit REAL DEFAULT 0.0,
        payment_status TEXT DEFAULT 'Paid',
        cash_paid REAL DEFAULT 0.0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 5. Sale Details
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price_per_unit REAL NOT NULL,
        FOREIGN KEY(sale_id) REFERENCES sales(id)
    );
    """)
    
    conn.commit()
    conn.close()
    print("[SUCCESS] Database tables initialized successfully with professional POS & Analytics columns.")

if __name__ == "__main__":
    init_db()
