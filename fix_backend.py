import os

file_path = 'app/main.py'
with open(file_path, 'r') as f:
    content = f.read()

# Naya simple check_existing function
new_function = """@app.get("/api/products/check-existing")
async def check_existing(tag: str = None, name: str = None, s_class: str = None):
    conn = get_db()
    if tag: # Stationery check
        result = conn.execute("SELECT * FROM products WHERE tag = ?", (tag,)).fetchone()
    else: # Book check
        result = conn.execute("SELECT * FROM products WHERE name = ? AND student_class = ?", (name, s_class)).fetchone()
    conn.close()
    return result if result else {"exists": False}"""

# Purane function ko replace karein (start aur end points dhund kar)
import re
pattern = r'@app\.get\("/api/products/check-existing"\).*?return result if result else \{"exists": False\}'
content = re.sub(pattern, new_function, content, flags=re.DOTALL)

with open(file_path, 'w') as f:
    f.write(content)
