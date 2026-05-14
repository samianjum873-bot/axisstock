import os

file_path = "app/database/seed.py"

code_content = '''import sqlite3
from models import get_db_connection

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        # Inserting mock inventory items for Class 1 and Class 2
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
        
        # Create a Full Bundle for Class 1 (Sum of Class 1 items = 350+400+80+1200 = 2030)
        cursor.execute("INSERT INTO bundles (bundle_name, student_class, total_price) VALUES (?, ?, ?)", 
                       ('Class 1 Full Set', 'Class 1', 2030.0))
        bundle_id = cursor.lastrowid
        
        # Link Class 1 items to the Class 1 Bundle
        cursor.execute("SELECT id FROM inventory WHERE student_class = 'Class 1'")
        item_ids = [row['id'] for row in cursor.fetchall()]
        
        for item_id in item_ids:
            cursor.execute("INSERT INTO bundle_items (bundle_id, item_id, quantity) VALUES (?, ?, ?)", 
                           (bundle_id, item_id, 1))
            
        conn.commit()
        print("[SUCCESS] Mock data injected for testing.")
    else:
        print("[INFO] Database already contains data. Skipping seed.")
        
    conn.close()

if __name__ == "__main__":
    seed_data()
'''

with open(file_path, "w") as f:
    f.write(code_content.strip())

print(f"[PATCHER] Successfully wrote/patched {file_path}")
