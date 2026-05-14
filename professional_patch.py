import os

# --- 1. Fix Backend Logic (Strict Matching) ---
backend_path = 'app/main.py'
if os.path.exists(backend_path):
    with open(backend_path, 'r') as f:
        content = f.read()
    
    # Strictly check for Stationery (Name + Tag)
    new_backend = """
@app.get("/api/products/check-existing")
async def check_existing(tag: str = None, name: str = None, s_class: str = None):
    conn = get_db()
    if tag and name: # Strict Stationery: Name AND Tag must match
        result = conn.execute("SELECT * FROM products WHERE name = ? AND tag = ?", (name, tag)).fetchone()
    elif name and s_class: # Book check
        result = conn.execute("SELECT * FROM products WHERE name = ? AND student_class = ?", (name, s_class)).fetchone()
    else:
        result = None
    conn.close()
    return result if result else {"exists": False}
"""
    import re
    pattern = r'@app\.get\("/api/products/check-existing"\).*?return result if result else \{"exists": False\}'
    content = re.sub(pattern, new_backend, content, flags=re.DOTALL)
    
    with open(backend_path, 'w') as f:
        f.write(content)

# --- 2. Fix Frontend UI & Logic ---
frontend_path = 'app/templates/index.html'
if os.path.exists(frontend_path):
    with open(frontend_path, 'r') as f:
        html = f.read()

    # CSS Fix for Scroll and Modal
    css_fix = """
    .modal-content { max-height: 85vh; overflow-y: auto; }
    #existingAlert { border-left: 5px solid #f59e0b; }
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-thumb { background: #6366f1; border-radius: 10px; }
    """
    html = html.replace('.modal-content { max-height: 90vh; overflow-y: auto; scrollbar-width: thin; }', css_fix)

    # UI cleanup: Move alert box above buttons
    old_alert = '<div id="existingAlert" class="hidden bg-amber-100 border-2 border-amber-400 p-4 rounded-2xl mb-4">'
    new_alert = '<div id="existingAlert" class="hidden bg-amber-50 border-l-4 border-amber-500 p-3 mb-4 animate-bounce">'
    html = html.replace(old_alert, new_alert)

    # JS Fix: checkDuplicate with strict name + tag logic
    new_js_logic = """
        async function checkDuplicate() {
            const cat = document.getElementById('catSelect').value;
            let query = "";
            if(cat === 'Stationery') {
                const name = document.getElementById('statName').value;
                const brand = document.getElementById('statBrand').value;
                const color = document.getElementById('statColor').value;
                const type = document.getElementById('statType').value;
                if(name.length < 2 || brand.length < 1) return;
                const tag = `${brand} ${color} ${type}`.trim();
                query = `name=${encodeURIComponent(name)}&tag=${encodeURIComponent(tag)}`;
            } else {
                const name = document.getElementById('bookName').value;
                const s_class = document.getElementById('bookClass').value;
                if(!name || !s_class) return;
                query = `name=${encodeURIComponent(name)}&s_class=${encodeURIComponent(s_class)}`;
            }

            try {
                const res = await fetch(`/api/products/check-existing?${query}`);
                const data = await res.json();
                const alertBox = document.getElementById('existingAlert');
                if(data.id) {
                    alertBox.classList.remove('hidden');
                    document.getElementById('prod_id').value = data.id;
                    setEntryMode(false);
                    document.getElementById('perItemSell').value = data.selling_price;
                } else {
                    alertBox.classList.add('hidden');
                    document.getElementById('formMode').value = 'new';
                    document.getElementById('forceNew').value = 'false';
                }
            } catch(e) { console.error("Sync Error"); }
        }
    """
    # Replace the old checkDuplicate function
    js_pattern = r'async function checkDuplicate\(\) \{.*?\}'
    html = re.sub(js_pattern, new_js_logic, html, flags=re.DOTALL)

    with open(frontend_path, 'w') as f:
        f.write(html)

print("✅ Patch Applied: Backend strict matching added, UI scrolling fixed, and duplicates refined!")
