import os

frontend_path = 'app/templates/index.html'

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EduStock Pro POS</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        .tab { display: none; } .active-tab { display: block; }
        .active-btn { background-color: #4338ca !important; border-bottom: 4px solid #facc15; }
        .modal { display: none; background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(4px); }
        .modal.active { display: flex; }
        .modal-content { max-height: 85vh; overflow-y: auto; }
        #existingAlert { border-left: 5px solid #f59e0b; transition: all 0.3s ease-in-out; }
        .hidden-field { display: none !important; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-thumb { background: #6366f1; border-radius: 10px; }
    </style>
</head>
<body class="bg-slate-100 min-h-screen font-sans text-slate-900">
    <nav class="bg-indigo-900 text-white shadow-2xl sticky top-0 z-50">
        <div class="container mx-auto px-4 flex justify-between items-center h-16">
            <div class="flex items-center space-x-2">
                <div class="bg-yellow-400 p-2 rounded-lg text-indigo-900"><i class="fas fa-school text-xl"></i></div>
                <h1 class="text-2xl font-black tracking-tighter uppercase">EduStock <span class="text-yellow-400">Pro</span></h1>
            </div>
            <div class="flex h-full items-center">
                <button onclick="showTab('pos')" id="btn-pos" class="px-6 h-full font-bold hover:bg-indigo-800 transition">POS</button>
                <button onclick="showTab('inventory')" id="btn-inventory" class="px-6 h-full font-bold hover:bg-indigo-800 transition">INVENTORY</button>
                <button onclick="showTab('reports')" id="btn-reports" class="px-6 h-full font-bold hover:bg-indigo-800 transition">REPORTS</button>
                <a href="/logout" class="ml-4 text-rose-400 font-bold text-xs border border-rose-400 px-3 py-1 rounded-md">LOGOUT</a>
            </div>
        </div>
    </nav>

    <div class="container mx-auto p-4 lg:p-8">
        <!-- POS TAB -->
        <div id="pos" class="tab active-tab">
            <div class="grid grid-cols-12 gap-6">
                <div class="col-span-12 lg:col-span-8">
                    <input type="text" id="smartSearch" onkeyup="filterProducts()" placeholder="Search Item, Class or Brand..." class="w-full mb-6 p-4 border-2 rounded-xl outline-none focus:border-indigo-500 text-lg shadow-sm">
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" id="productGrid"></div>
                </div>
                <div class="col-span-12 lg:col-span-4">
                    <div class="bg-white rounded-2xl shadow-xl border-t-8 border-indigo-600 p-6 sticky top-24">
                        <h2 class="font-black text-xl mb-4 flex justify-between uppercase">Order Summary <span id="cartCount" class="text-indigo-600">0</span></h2>
                        <div id="cartItems" class="space-y-3 mb-6 max-h-80 overflow-y-auto border-b pb-4"></div>
                        <div class="text-3xl font-black flex justify-between text-indigo-900 font-mono pt-4">
                            <span>TOTAL:</span><span>Rs. <span id="orderTotal">0</span></span>
                        </div>
                        <div class="mt-6 space-y-4">
                            <input type="text" id="custName" placeholder="Parent Name" class="w-full border-2 p-3 rounded-xl outline-none">
                            <select id="payStatus" class="w-full border-2 p-3 rounded-xl font-bold bg-white">
                                <option value="Paid">✅ Paid Full</option>
                                <option value="Pending">⏳ Udhaar</option>
                            </select>
                            <button onclick="completeSale()" class="w-full bg-indigo-600 text-white py-4 rounded-2xl font-black text-xl shadow-lg transform active:scale-95 transition">FINALIZE</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- INVENTORY TAB -->
        <div id="inventory" class="tab">
            <div class="bg-white p-6 rounded-2xl shadow-xl border border-slate-200">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="font-black text-3xl">Inventory Master</h2>
                    <button onclick="toggleModal(true)" class="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold shadow-lg hover:bg-indigo-700 active:scale-95 transition"><i class="fas fa-plus mr-2"></i> ADD NEW STOCK</button>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-slate-50 text-slate-500 text-xs font-black uppercase border-b">
                            <tr><th class="p-4">Item & Brand</th><th class="p-4">Specs / Class</th><th class="p-4">P. Price</th><th class="p-4">S. Price</th><th class="p-4 text-center">Stock</th></tr>
                        </thead>
                        <tbody id="inventoryTableBody" class="text-sm"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL -->
    <div id="addModal" class="modal fixed inset-0 z-[100] items-center justify-center p-4">
        <div class="bg-white w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden modal-content">
            <div class="bg-indigo-900 p-6 text-white flex justify-between items-center">
                <div>
                    <h3 class="text-2xl font-black uppercase tracking-tight">Add New Stock</h3>
                    <p class="text-indigo-300 text-xs font-bold">Category-specific fields enabled</p>
                </div>
                <button onclick="toggleModal(false)" class="text-3xl hover:text-yellow-400 transition">&times;</button>
            </div>
            
            <div id="existingAlert" class="hidden bg-amber-50 border-l-4 border-amber-500 p-4 m-4 animate-pulse">
                <p class="text-amber-800 font-black text-sm text-center mb-3">⚠️ ITEM ALREADY IN SYSTEM!</p>
                <div class="grid grid-cols-2 gap-3">
                    <button type="button" onclick="setEntryMode(false)" id="btnMerge" class="bg-amber-500 text-white text-[10px] font-black p-2 rounded-lg">UPDATE EXISTING</button>
                    <button type="button" onclick="setEntryMode(true)" id="btnSeparate" class="bg-slate-500 text-white text-[10px] font-black p-2 rounded-lg">ADD NEW ENTRY</button>
                </div>
            </div>

            <form id="addProdForm" class="p-8 space-y-6">
                <input type="hidden" name="mode" id="formMode" value="new">
                <input type="hidden" name="prod_id" id="prod_id">
                <input type="hidden" name="force_new" id="forceNew" value="false">

                <div class="grid grid-cols-2 gap-6">
                    <div class="space-y-2">
                        <label class="text-xs font-black text-slate-500 uppercase">Category</label>
                        <select name="cat" id="catSelect" onchange="handleCatChange()" class="w-full border-2 p-3 rounded-xl font-bold text-indigo-700 bg-indigo-50 border-indigo-100">
                            <option value="Stationery">Stationery</option>
                            <option value="Book">Course Book</option>
                            <option value="Notebook">Notebook</option>
                        </select>
                    </div>
                    <div id="statItemNameField" class="space-y-2">
                        <label class="text-xs font-black text-slate-500 uppercase">Item Name</label>
                        <input type="text" id="statName" onkeyup="checkDuplicate()" placeholder="e.g. Ballpoint" class="w-full border-2 p-3 rounded-xl font-bold">
                    </div>
                </div>

                <div id="stationeryFields" class="grid grid-cols-3 gap-4">
                    <input type="text" id="statBrand" onkeyup="checkDuplicate()" placeholder="Brand" class="border-2 p-3 rounded-xl">
                    <input type="text" id="statColor" onkeyup="checkDuplicate()" placeholder="Color" class="border-2 p-3 rounded-xl">
                    <input type="text" id="statType" onkeyup="checkDuplicate()" placeholder="Size/Type" class="border-2 p-3 rounded-xl">
                </div>

                <div id="bookFields" class="hidden-field grid grid-cols-3 gap-4">
                    <input type="text" id="bookClass" onkeyup="checkDuplicate()" placeholder="Class" class="border-2 p-3 rounded-xl">
                    <input type="text" id="bookName" onkeyup="checkDuplicate()" placeholder="Subject" class="col-span-2 border-2 p-3 rounded-xl">
                </div>

                <div class="bg-indigo-50 p-6 rounded-2xl border-2 border-indigo-100 grid grid-cols-2 gap-4">
                    <input type="number" name="stock" id="totalQty" onkeyup="calcPrices()" placeholder="Qty" class="p-4 rounded-xl font-black">
                    <input type="number" id="totalBuy" onkeyup="calcPrices()" placeholder="Total Bill" class="p-4 rounded-xl font-black">
                    <input type="number" step="any" name="p_price" id="perItemCost" class="bg-slate-200 p-4 rounded-xl font-black" readonly>
                    <input type="number" name="s_price" id="perItemSell" onkeyup="validatePrice()" placeholder="Sell Price" class="border-2 border-rose-200 p-4 rounded-xl font-black">
                </div>
                <p id="priceError" class="text-xs text-rose-500 font-bold hidden text-center">⚠️ Profit exceeds 50%! Please check.</p>

                <button type="submit" id="submitBtn" class="w-full bg-emerald-600 text-white py-5 rounded-2xl font-black text-xl shadow-xl transition">CONFIRM & SAVE</button>
            </form>
        </div>
    </div>

    <script>
        let inventory = []; let cart = [];

        function showTab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active-tab'));
            document.querySelectorAll('nav button').forEach(b => b.classList.remove('active-btn'));
            document.getElementById(id).classList.add('active-tab');
            document.getElementById('btn-'+id).classList.add('active-btn');
            if(id === 'inventory') refreshData();
        }

        function toggleModal(show) {
            document.getElementById('addModal').classList.toggle('active', show);
            if(!show) {
                document.getElementById('addProdForm').reset();
                document.getElementById('existingAlert').classList.add('hidden');
                setEntryMode(true);
            }
        }

        function handleCatChange() {
            const cat = document.getElementById('catSelect').value;
            const sFields = document.getElementById('stationeryFields');
            const bFields = document.getElementById('bookFields');
            const sNameField = document.getElementById('statItemNameField');
            
            if(cat === 'Stationery') {
                sFields.classList.remove('hidden-field');
                sNameField.classList.remove('hidden-field');
                bFields.classList.add('hidden-field');
            } else {
                sFields.classList.add('hidden-field');
                sNameField.classList.add('hidden-field');
                bFields.classList.remove('hidden-field');
            }
            checkDuplicate();
        }

        async function checkDuplicate() {
            const cat = document.getElementById('catSelect').value;
            let query = "";
            if(cat === 'Stationery') {
                const name = document.getElementById('statName').value;
                const tag = `${document.getElementById('statBrand').value} ${document.getElementById('statColor').value} ${document.getElementById('statType').value}`.trim();
                if(name.length < 2) return;
                query = `name=${encodeURIComponent(name)}&tag=${encodeURIComponent(tag)}`;
            } else {
                const name = document.getElementById('bookName').value;
                const s_class = document.getElementById('bookClass').value;
                if(!name || !s_class) return;
                query = `name=${encodeURIComponent(name)}&s_class=${encodeURIComponent(s_class)}`;
            }

            const res = await fetch(`/api/products/check-existing?${query}`);
            const data = await res.json();
            const alertBox = document.getElementById('existingAlert');
            if(data.id) {
                alertBox.classList.remove('hidden');
                document.getElementById('prod_id').value = data.id;
                document.getElementById('perItemSell').value = data.selling_price;
                setEntryMode(false);
            } else {
                alertBox.classList.add('hidden');
                setEntryMode(true);
            }
        }

        function setEntryMode(isNew) {
            document.getElementById('forceNew').value = isNew;
            document.getElementById('formMode').value = isNew ? 'new' : 'update';
            const bM = document.getElementById('btnMerge');
            const bS = document.getElementById('btnSeparate');
            if(isNew) {
                bS.className = "bg-indigo-600 text-white text-[10px] font-black p-2 rounded-lg";
                bM.className = "bg-slate-400 text-white text-[10px] font-black p-2 rounded-lg";
            } else {
                bM.className = "bg-amber-500 text-white text-[10px] font-black p-2 rounded-lg";
                bS.className = "bg-slate-400 text-white text-[10px] font-black p-2 rounded-lg";
            }
        }

        function calcPrices() {
            const bill = parseFloat(document.getElementById('totalBuy').value) || 0;
            const qty = parseInt(document.getElementById('totalQty').value) || 1;
            document.getElementById('perItemCost').value = (bill / qty).toFixed(2);
            validatePrice();
        }

        function validatePrice() {
            const cost = parseFloat(document.getElementById('perItemCost').value) || 0;
            const sell = parseFloat(document.getElementById('perItemSell').value) || 0;
            const err = document.getElementById('priceError');
            const btn = document.getElementById('submitBtn');
            if(cost > 0 && sell > cost * 1.5) {
                err.classList.remove('hidden'); btn.classList.add('opacity-50', 'pointer-events-none');
            } else {
                err.classList.add('hidden'); btn.classList.remove('opacity-50', 'pointer-events-none');
            }
        }

        document.getElementById('addProdForm').onsubmit = async (e) => {
            e.preventDefault();
            const fd = new FormData(e.target);
            const cat = document.getElementById('catSelect').value;
            if(cat === 'Stationery') {
                fd.set('name', document.getElementById('statName').value);
                fd.set('tag', `${document.getElementById('statBrand').value} ${document.getElementById('statColor').value} ${document.getElementById('statType').value}`.trim());
            } else {
                fd.set('name', document.getElementById('bookName').value);
                fd.set('s_class', document.getElementById('bookClass').value);
            }
            await fetch('/api/products/smart-add', {method: 'POST', body: fd});
            toggleModal(false);
            refreshData();
        };

        async function refreshData() {
            const res = await fetch('/api/inventory');
            inventory = await res.json();
            document.getElementById('inventoryTableBody').innerHTML = inventory.map(p => `
                <tr class="border-b hover:bg-slate-50 transition">
                    <td class="p-4 font-black uppercase text-xs">${p.name}<br><span class="text-indigo-400 font-bold text-[10px]">${p.category}</span></td>
                    <td class="p-4 text-xs font-bold text-slate-500 uppercase">${p.tag || ('Class ' + p.student_class)}</td>
                    <td class="p-4 font-mono font-bold text-slate-400">Rs. ${p.purchase_price}</td>
                    <td class="p-4 font-mono font-black text-indigo-600 text-base">Rs. ${p.selling_price}</td>
                    <td class="p-4 text-center">
                        <span class="px-3 py-1 rounded-full text-[10px] font-black ${p.stock < 10 ? 'bg-rose-100 text-rose-600 animate-pulse':'bg-emerald-100 text-emerald-600'}">${p.stock}</span>
                    </td>
                </tr>`).join('');
            renderProducts(inventory);
        }

        function renderProducts(data) {
            document.getElementById('productGrid').innerHTML = data.map(p => `
                <div onclick="addToCart(${p.id})" class="bg-white p-5 rounded-2xl shadow-sm border-2 border-transparent hover:border-indigo-500 hover:shadow-lg cursor-pointer transition">
                    <h3 class="font-black text-sm uppercase text-indigo-900 leading-tight">${p.name}</h3>
                    <p class="text-[10px] text-slate-400 font-bold uppercase mt-1">${p.tag || ('Class ' + p.student_class)}</p>
                    <div class="flex justify-between items-center mt-4">
                        <div class="text-xl font-black text-indigo-600">Rs. ${p.selling_price}</div>
                        <div class="text-[9px] bg-slate-100 px-2 py-1 rounded font-bold">Stock: ${p.stock}</div>
                    </div>
                </div>`).join('');
        }

        function filterProducts() {
            const q = document.getElementById('smartSearch').value.toLowerCase();
            renderProducts(inventory.filter(p => p.name.toLowerCase().includes(q) || (p.tag && p.tag.toLowerCase().includes(q)) || (p.student_class && p.student_class.includes(q))));
        }

        function addToCart(id) {
            const i = inventory.find(p => p.id === id);
            if(i.stock <= 0) return alert("Out of Stock!");
            cart.push({...i});
            updateCartUI();
        }

        function updateCartUI() {
            document.getElementById('cartItems').innerHTML = cart.map((i,idx)=>`
                <div class="flex justify-between items-center bg-indigo-50 p-3 rounded-xl text-xs font-black border border-indigo-100">
                    <div class="flex flex-col"><span>${i.name}</span><span class="text-indigo-400 text-[10px] uppercase">${i.tag || ('Class ' + i.student_class)}</span></div>
                    <div class="flex items-center space-x-3"><span>Rs. ${i.selling_price}</span><button onclick="cart.splice(${idx},1);updateCartUI()" class="text-rose-500 text-lg">&times;</button></div>
                </div>`).join('');
            document.getElementById('orderTotal').innerText = cart.reduce((a, b) => a + b.selling_price, 0);
            document.getElementById('cartCount').innerText = cart.length;
        }

        async function completeSale() {
            if(cart.length === 0) return;
            const fd = new FormData();
            fd.append('p_name', document.getElementById('custName').value || 'Cash Parent');
            fd.append('p_phone', '0000');
            fd.append('items_json', JSON.stringify(cart.map(i => ({...i, qty:1}))));
            fd.append('total', document.getElementById('orderTotal').innerText);
            fd.append('status', document.getElementById('payStatus').value);
            const res = await fetch('/api/checkout', {method: 'POST', body: fd});
            if(res.ok) { cart=[]; updateCartUI(); refreshData(); alert("Sale Successful!"); }
        }

        window.onload = refreshData;
    </script>
</body>
</html>"""

with open(frontend_path, 'w') as f:
    f.write(html_content)

print("✅ UI Fixed: JavaScript cleaned, Scroll restored, and Category Logic synced!")
