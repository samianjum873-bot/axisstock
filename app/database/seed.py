import sqlite3
import sys
import os

# Append current directory to path so it can find app.database.models
sys.path.append(os.getcwd())
from app.database.models import get_db_connection

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        mock_items = [
            ('English Book - Class 1', 'Book', 'Class 1', 350.0, 100, 100),
            ('Math Book - Class 1', 'Book', 'Class 1', 400.0, 100, 100),
            ('Urdu Notebook - Class 1', 'Notebook', 'Class 1', 80.0, 200, 200),
            ('School Uniform Set - Small', 'Uniform', 'Class 1', 1200.0, 50, 50),
            
            ('English Book - Class 2', 'Book', 'Class 2', 380.0, 80, 80),
            ('Math Book - Class 2', 'Book', 'Class 2', 420.0, 80, 80),
            ('Urdu Notebook - Class 2', 'Notebook', 'Class 2', 80.0, 150, 150)
        ]
        
        cursor.executemany("""
            INSERT INTO inventory (item_name, item_type, student_class, price, total_stock, remaining_stock)
            VALUES (?, ?, ?, ?, ?, ?)
        """, mock_items)
        
        cursor.execute("INSERT INTO bundles (bundle_name, student_class, total_price) VALUES (?, ?, ?)", 
                       ('Class 1 Full Set', 'Class 1', 2030.0))
        bundle_id = cursor.lastrowid
        
        cursor.execute("SELECT id FROM inventory WHERE student_class = 'Class 1'")
        item_ids = [row['id'] for row in cursor.fetchall()]
        
        for item_id in item_ids:
            cursor.execute("INSERT INTO bundle_items (bundle_id, item_id, quantity) VALUES (?, ?, ?)", 
                           (bundle_id, item_id, 1))
            
        conn.commit()
        print("[SUCCESS] Mock data injected successfully from root folder.")
    else:
        print("[INFO] Database already contains data. Skipping seed.")
        
    conn.close()

if __name__ == "__main__":
    seed_data()