import sqlite3
import os

DB_PATH = "app/database/school_store.db"

def init_db():
    """Initialize or update database schema"""
    if not os.path.exists("app/database"):
        os.makedirs("app/database")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Products table
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
            variation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Customers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Sales table
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
    
    # Sale items table
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
    
    print("✅ Database schema initialized successfully")

if __name__ == "__main__":
    init_db()
