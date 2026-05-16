import os

def apply_sales_patches():
    print("--- 🛠️ AXIS SALES HISTORY INTEGRATION SYSTEM ---")
    
    # 1. Patch app/main.py
    main_path = "app/main.py"
    if os.path.exists(main_path):
        with open(main_path, "r") as f:
            content = f.read()
            
        # Target an existing block to inject the new routes nicely
        target_route = '@app.get("/inventory")'
        new_routes = """@app.get("/sales")
async def sales_page(request: Request):
    if not is_logged_in(request): return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "sales.html", {"active_page": "sales"})

@app.get("/api/sales-all")
async def all_sales(request: Request):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    # Fetch sales joined with customer details, ordered by latest first
    data = conn.execute(\"\"\"
        SELECT s.id, s.receipt_number, s.total_amount, s.cash_paid, s.profit, s.payment_status, s.timestamp,
               c.name as customer_name, c.phone as customer_phone
        FROM sales s 
        LEFT JOIN customers c ON s.customer_id = c.id 
        ORDER BY s.id DESC
    \"\"\").fetchall()
    conn.close()
    return data

@app.get("/api/sales-details/{sale_id}")
async def sale_details(request: Request, sale_id: int):
    if not is_logged_in(request): raise HTTPException(status_code=401)
    conn = get_db()
    items = conn.execute("SELECT product_name, qty, price FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
    conn.close()
    return items

"""
        if '@app.get("/sales")' not in content:
            content = content.replace(target_route, new_routes + target_route)
            with open(main_path, "w") as f:
                f.write(content)
            print("✅ Successfully injected Sales routes & endpoints into app/main.py")
        else:
            print("ℹ️ Sales routes already exist in app/main.py")

    # 2. Patch app/templates/index.html to add sidebar tab
    index_path = "app/templates/index.html"
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            content = f.read()
            
        target_nav = """            <a href="/inventory" id="link-inventory" class="sidebar-link {% if active_page == 'inventory' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900\">
                <i class="fas fa-box-open w-8"></i> <span class="font-bold text-xs">STOCK MANAGER</span>
            </a>"""
            
        new_nav_item = """\n            <a href="/sales" id="link-sales" class="sidebar-link {% if active_page == 'sales' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900\">
                <i class="fas fa-history w-8"></i> <span class="font-bold text-xs">SALES HISTORY</span>
            </a>"""
            
        if 'id="link-sales"' not in content:
            content = content.replace(target_nav, target_nav + new_nav_item)
            with open(index_path, "w") as f:
                f.write(content)
            print("✅ Successfully added 'SALES HISTORY' to sidebar in index.html")
        else:
            print("ℹ️ Sidebar link already present in index.html")

    # 3. Create app/templates/sales.html
    sales_template_path = "app/templates/sales.html"
    sales_html_content = """{% extends "index.html" %}

{% block title %}Sales History{% endblock %}
{% block header_title %}Sales History Ledger{% endblock %}

{% block page_content %}
<div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
            <h3 class="text-xl font-black text-indigo-950 uppercase italic">Transaction Logs</h3>
            <p class="text-slate-500 text-xs font-medium">Track and monitor all digital counters and payment history.</p>
        </div>
        <div class="flex gap-2 w-full md:w-auto">
            <input type="text" id="salesSearch" onkeyup="filterSales()" placeholder="Search Receipt, Customer or Phone..." class="border-2 border-slate-200 p-3 rounded-xl font-bold text-sm w-full md:w-80 focus:border-indigo-600 outline-none transition">
        </div>
    </div>

    <div class="overflow-x-auto rounded-2xl border border-slate-100">
        <table class="w-full text-left border-collapse">
            <thead>
                <tr class="bg-slate-50 text-indigo-950 text-xs font-black uppercase border-b border-slate-100">
                    <th class="p-4">Receipt No</th>
                    <th class="p-4">Date & Time</th>
                    <th class="p-4">Customer Name</th>
                    <th class="p-4">Contact</th>
                    <th class="p-4">Total Bill</th>
                    <th class="p-4">Cash Paid</th>
                    <th class="p-4">Net Profit</th>
                    <th class="p-4">Status</th>
                    <th class="p-4 text-center">Action</th>
                </tr>
            </thead>
            <tbody id="salesTableBody" class="text-xs font-bold text-slate-700 divide-y divide-slate-100">
                </tbody>
        </table>
    </div>
</div>

<div id="itemsModal" class="modal fixed inset-0 z-[100] items-center justify-center">
    <div class="bg-white rounded-3xl shadow-2xl w-[90%] max-w-lg overflow-hidden border-4 border-indigo-950">
        <div class="bg-indigo-950 p-5 text-white flex justify-between items-center">
            <h3 class="text-lg font-black uppercase italic" id="modalReceiptTitle">Items Breakdown</h3>
            <button onclick="closeItemsModal()" class="text-2xl font-black hover:text-yellow-400 transition">&times;</button>
        </div>
        <div class="p-6">
            <div class="overflow-x-auto rounded-xl border border-slate-100">
                <table class="w-full text-left">
                    <thead>
                        <tr class="bg-slate-50 text-[10px] font-black uppercase text-indigo-950 border-b">
                            <th class="p-3">Product Name</th>
                            <th class="p-3 text-center">Qty</th>
                            <th class="p-3 text-right">Unit Price</th>
                            <th class="p-3 text-right">Total</th>
                        </tr>
                    </thead>
                    <tbody id="modalItemsBody" class="text-xs font-bold text-slate-600 divide-y">
                        </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
    let allSalesData = [];

    async function loadSalesHistory() {
        try {
            const res = await fetch('/api/sales-all');
            allSalesData = await res.json();
            renderSales(allSalesData);
        } catch (err) {
            console.error("Error loading sales data:", err);
        }
    }

    function renderSales(data) {
        const tbody = document.getElementById('salesTableBody');
        tbody.innerHTML = '';
        
        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="p-8 text-center font-black text-slate-400 uppercase tracking-wider text-sm">No transactions found</td></tr>`;
            return;
        }

        data.forEach(sale => {
            const date = new Date(sale.timestamp).toLocaleString('en-US', { 
                day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true 
            });
            
            let statusColor = "bg-emerald-100 text-emerald-800";
            if (sale.payment_status === "Unpaid") statusColor = "bg-rose-100 text-rose-800";
            if (sale.payment_status === "Partial") statusColor = "bg-amber-100 text-amber-800";

            tbody.innerHTML += `
                <tr class="hover:bg-slate-50/80 transition">
                    <td class="p-4 font-black text-indigo-600">${sale.receipt_number}</td>
                    <td class="p-4 text-slate-500">${date}</td>
                    <td class="p-4 uppercase">${sale.customer_name || 'N/A'}</td>
                    <td class="p-4 text-slate-500">${sale.customer_phone || 'N/A'}</td>
                    <td class="p-4 text-slate-900 font-black">Rs. ${sale.total_amount}</td>
                    <td class="p-4 text-emerald-600">Rs. ${sale.cash_paid}</td>
                    <td class="p-4 text-indigo-950 font-black">Rs. ${sale.profit}</td>
                    <td class="p-4">
                        <span class="px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-wide ${statusColor}">
                            ${sale.payment_status}
                        </span>
                    </td>
                    <td class="p-4 text-center">
                        <button onclick="viewItems(${sale.id}, '${sale.receipt_number}')" class="bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-xl font-black hover:bg-indigo-600 hover:text-white transition uppercase text-[10px]">
                            <i class="fas fa-eye mr-1"></i> Items
                        </button>
                    </td>
                </tr>
            `;
        });
    }

    function filterSales() {
        const query = document.getElementById('salesSearch').value.toLowerCase().strip();
        const filtered = allSalesData.filter(sale => 
            sale.receipt_number.toLowerCase().includes(query) ||
            (sale.customer_name && sale.customer_name.toLowerCase().includes(query)) ||
            (sale.customer_phone && sale.customer_phone.includes(query))
        );
        renderSales(filtered);
    }

    async function viewItems(saleId, receiptNum) {
        document.getElementById('modalReceiptTitle').innerText = `Items in ${receiptNum}`;
        const tbody = document.getElementById('modalItemsBody');
        tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center">Loading breakdown...</td></tr>';
        
        document.getElementById('itemsModal').classList.add('active');

        try {
            const res = await fetch(`/api/sales-details/${saleId}`);
            const items = await res.json();
            tbody.innerHTML = '';
            
            items.forEach(item => {
                const total = item.qty * item.price;
                tbody.innerHTML += `
                    <tr>
                        <td class="p-3 text-slate-800 uppercase font-bold">${item.product_name}</td>
                        <td class="p-3 text-center">${item.qty}</td>
                        <td class="p-3 text-right text-slate-500">Rs. ${item.price}</td>
                        <td class="p-3 text-right font-black text-indigo-950">Rs. ${total}</td>
                    </tr>
                `;
            });
        } catch (err) {
            tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-rose-500">Error loading items breakdown</td></tr>';
        }
    }

    function closeItemsModal() {
        document.getElementById('itemsModal').classList.remove('active');
    }

    // Auto-load on page boot
    window.onload = loadSalesHistory;
</script>
\"\"\"
    with open(sales_template_path, "w") as f:
        f.write(sales_html_content)
    print("✅ Created new template 'app/templates/sales.html' with active modal views.")

    # Self-destruct logic to keep environment pristine
    try:
        os.remove(__file__)
        print("\nPatcher successfully deployed and auto-deleted. Execution context clean.")
    except:
        pass

if __name__ == "__main__":
    apply_sales_patches()
