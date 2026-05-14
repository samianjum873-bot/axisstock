import os

file_path = 'app/main.py'
with open(file_path, 'r') as f:
    content = f.read()

# Update parameters to include force_new
old_params = "stock: int = Form(...)"
new_params = "stock: int = Form(...),\n    force_new: bool = Form(False)"
content = content.replace(old_params, new_params)

# Update the logic inside smart_add
old_logic = """if mode == 'update' and prod_id:
        cursor.execute("UPDATE products SET stock = stock + ?, purchase_price = ?, selling_price = ? WHERE id = ?", 
                       (stock, p_price, s_price, prod_id))"""

new_logic = """if mode == 'update' and prod_id and not force_new:
        cursor.execute("UPDATE products SET stock = stock + ?, purchase_price = ?, selling_price = ? WHERE id = ?", 
                       (stock, p_price, s_price, prod_id))"""

content = content.replace(old_logic, new_logic)

with open(file_path, 'w') as f:
    f.write(content)
