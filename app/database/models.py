import sqlite3

DB_PATH = "app/database/school_store.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Inventory Table (Individual items like books, copies, uniforms)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL, -- 'Book', 'Notebook', 'Uniform', etc.
        student_class TEXT NOT NULL, -- e.g., 'Class 1', 'Class 2'
        price REAL NOT NULL,
        total_stock INTEGER NOT NULL,
        remaining_stock INTEGER NOT NULL
    );
    """)
    
    # 2. Bundles Table (Mapping which items belong to which class set)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bundles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bundle_name TEXT NOT NULL, -- e.g., 'Class 1 Full Set'
        student_class TEXT NOT NULL UNIQUE,
        total_price REAL NOT NULL
    );
    """)
    
    # 3. Bundle Items Mapping (Many-to-Many relationship between Bundles and Inventory)
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
    
    # 4. Sales/Transactions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_number TEXT NOT NULL UNIQUE,
        parent_name TEXT NOT NULL,
        parent_phone TEXT NOT NULL,
        student_class TEXT NOT NULL,
        sale_type TEXT NOT NULL, -- 'Single Item' or 'Full Bundle'
        total_amount REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 5. Sale Details (What was sold in that receipt)
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
    print("[SUCCESS] Database tables initialized successfully.")

if __name__ == "__main__":
    init_db()