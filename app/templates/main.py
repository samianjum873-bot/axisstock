<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EduStock Pro POS</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        .tab { display: none; } .active-tab { display: block; }
        .active-btn { background-color: #facc15 !important; color: #1e1b4b !important; border-bottom: 4px solid #1e1b4b; }
        .modal { display: none; background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px); overflow-y: auto; padding: 20px 0; }
        .modal.active { display: flex; }
        .modal-content { width: 95%; max-width: 800px; margin: auto; }
        .hidden-field { display: none !important; }
    </style>
</head>
<body class="bg-slate-200 min-h-screen font-sans text-slate-900">
    <!-- Navbar -->
    <nav class="bg-indigo-950 text-white shadow-2xl sticky top-0 z-50">
        <div class="container mx-auto px-4 flex justify-between items-center h-20">
            <div class="flex items-center space-x-3">
                <div class="bg-yellow-400 p-3 rounded-xl text-indigo-950 shadow-lg"><i class="fas fa-calculator text-2xl"></i></div>
                <h1 class="text-3xl font-black tracking-tighter italic uppercase">EduStock <span class="text-yellow-400 font-black">PRO</span></h1>
            </div>
            <div class="flex h-full items-center text-lg">
                <button onclick="showTab('pos')" id="btn-pos" class="px-8 h-full font-black hover:bg-indigo-900 transition border-r border-indigo-800 active-btn">SALE (F1)</button>
                <button onclick="showTab('inventory')" id="btn-inventory" class="px-8 h-full font-black hover:bg-indigo-900 transition border-r border-indigo-800">STOCK</button>
                <button onclick="showTab('reports')" id="btn-reports" class="px-8 h-full font-black hover:bg-indigo-900 transition">REPORTS</button>
            </div>
        </div>
    </nav>

    <div class="container mx-auto p-4 lg:p-6">
        <!-- POS TAB -->
        <div id="pos" class="tab active-tab">
            <div class="grid grid-cols-12 gap-6">
                <div class="col-span-12 lg:col-span-8">
                    <input type="text" id="smartSearch" onkeyup="filterProducts()" placeholder="🔍 Search Item, Class, or Brand..." class="w-full mb-6 p-5 border-4 border-indigo-200 rounded-2xl outline-none focus:border-indigo-600 text-2xl font-bold shadow-xl">
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" id="productGrid"></div>
                </div>
                <div class="col-span-12 lg:col-span-4">
                    <div class="bg-white rounded-3xl shadow-2xl border-t-[12px] border-indigo-600 p-6 sticky top-24">
                        <h2 class="font-black text-2xl mb-4 flex justify-between border-b-4 border-slate-100 pb-2">ORDER BILL <span id="cartCount" class="bg-indigo-100 px-3 rounded-full text-indigo-700">0</span></h2>
                        <div id="cartItems" class="space-y-3 mb-6 max-h-96 overflow-y-auto pr-2"></div>
                        <div class="bg-slate-900 text-yellow-400 p-5 rounded-2xl shadow-inner">
                            <div class="text-sm font-bold uppercase opacity-70">Total Amount</div>
                            <div class="text-5xl font-black font-mono">Rs. <span id="orderTotal">0</span></div>
                        </div>
                        <div class="mt-6 space-y-4">
                            <input type="text" id="custName" placeholder="👤 Parent/Student Name" class="w-full border-2 border-slate-300 p-4 rounded-xl font-bold text-lg">
                            <select id="payStatus" class="w-full border-4 border-emerald-500 p-4 rounded-xl font-black text-xl bg-white">
                                <option value="Paid">✅ CASH RECEIVED</option>
                                <option value="Pending">⏳ UDHAAR (PENDING)</option>
                            </select>
                            <button onclick="completeSale()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-6 rounded-2xl font-black text-3xl shadow-2xl transform active:scale-95 transition">PRINT BILL</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- INVENTORY TAB -->
        <div id="inventory" class="tab">
            <div class="bg-white p-8 rounded-3xl shadow-2xl border border-slate-300">
                <div class="flex flex-col md:flex-row justify-between items-center mb-8">
                    <h2 class="font-black text-4xl text-indigo-950 uppercase italic">Stock Inventory</h2>
                    <button onclick="toggleModal(true)" class="bg-indigo-600 text-white px-10 py-5 rounded-2xl font-black text-xl shadow-lg hover:bg-indigo-700">
                        <i class="fas fa-plus-circle mr-3"></i> ADD NEW STOCK
                    </button>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left">
                        <thead class="bg-indigo-50 text-indigo-900 text-sm font-black uppercase">
                            <tr>
                                <th class="p-5 border-b-4 border-indigo-200">Item Detail</th>
                                <th class="p-5 border-b-4 border-indigo-200">Category</th>
                                <th class="p-5 border-b-4 border-indigo-200">Specs/Class</th>
                                <th class="p-5 border-b-4 border-indigo-200">Buy Price</th>
                                <th class="p-5 border-b-4 border-indigo-200">Sale Price</th>
                                <th class="p-5 border-b-4 border-indigo-200 text-center">Stock</th>
                            </tr>
                        </thead>
                        <tbody id="inventoryTableBody" class="text-lg font-bold"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- MODAL -->
    <div id="addModal" class="modal fixed inset-0 z-[100] items-center justify-center p-4">
        <div class="bg-white rounded-3xl shadow-2xl overflow-hidden modal-content border-4 border-indigo-900">
            <div class="bg-indigo-950 p-6 text-white flex justify-between items-center">
                <h3 class="text-3xl font-black uppercase italic">Stock Entry</h3>
                <button onclick="toggleModal(false)" class="text-3xl">&times;</button>
            </div>
            
            <!-- ALERTS SECTION -->
            <div id="existingAlert" class="hidden bg-amber-50 border-l-[12px] border-amber-500 p-6 m-6 rounded-r-2xl shadow-xl">
                <div class="flex items-center mb-4">
                    <i class="fas fa-exclamation-triangle text-amber-500 text-3xl mr-4"></i>
                    <h4 class="text-amber-900 font-black text-xl uppercase">Yeh Item Pehle Se Hai!</h4>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <button type="button" onclick="setEntryMode(false)" id="btnMerge" class="p-4 rounded-xl border-2 font-black text-sm uppercase">Purane mein add karo</button>
                    <button type="button" onclick="setEntryMode(true)" id="btnSeparate" class="p-4 rounded-xl border-2 font-black text-sm uppercase">Alag entry banao</button>
                </div>
            </div>

            <form id="addProdForm" class="p-8 space-y-6">
                <input type="hidden" name="mode" id="formMode" value="new">
                <input type="hidden" name="prod_id" id="prod_id">
                <input type="hidden" name="force_new" id="forceNew" value="false">

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="font-black text-indigo-900 uppercase text-xs">Category</label>
                        <select name="cat" id="catSelect" onchange="handleCatChange()" class="w-full border-4 p-4 rounded-xl font-black bg-indigo-50 border-indigo-200">
                            <option value="Stationery">Stationery</option>
                            <option value="Book">Course Book</option>
                            <option value="Notebook">Notebook / Register</option>
                        </select>
                    </div>
                    <div id="statItemNameField">
                        <label class="font-black text-indigo-900 uppercase text-xs">Item Name</label>
                        <input type="text" id="statName" onkeyup="checkDuplicate()" placeholder="e.g. Dollar Pen" class="w-full border-4 p-4 rounded-xl font-black border-slate-200">
                    </div>
                </div>

                <div id="stationeryFields" class="grid grid-cols-3 gap-4 bg-slate-50 p-4 rounded-xl border-2">
                    <input type="text" id="statBrand" onkeyup="checkDuplicate()" placeholder="Brand" class="border p-3 rounded-lg font-bold">
                    <input type="text" id="statColor" onkeyup="checkDuplicate()" placeholder="Color" class="border p-3 rounded-lg font-bold">
                    <input type="text" id="statType" onkeyup="checkDuplicate()" placeholder="Size" class="border p-3 rounded-lg font-bold">
                </div>

                <div id="bookFields" class="hidden-field grid grid-cols-3 gap-4 bg-slate-50 p-4 rounded-xl border-2">
                    <input type="text" id="bookClass" onkeyup="checkDuplicate()" placeholder="Class" class="border p-3 rounded-lg font-bold">
                    <input type="text" id="bookName" onkeyup="checkDuplicate()" placeholder="Subject Name" class="col-span-2 border p-3 rounded-lg font-bold">
                </div>

                <div class="bg-indigo-900 p-6 rounded-2xl grid grid-cols-2 gap-4">
                    <input type="number" name="stock" id="totalQty" onkeyup="calcPrices()" placeholder="Qty" class="p-4 rounded-xl font-black text-2xl">
                    <input type="number" id="totalBuy" onkeyup="calcPrices()" placeholder="Total Bill" class="p-4 rounded-xl font-black text-2xl">
                    <input type="number" step="any" name="p_price" id="perItemCost" class="p-4 rounded-xl font-black text-2xl bg-indigo-800 text-white" readonly placeholder="Cost">
                    <input type="number" name="s_price" id="perItemSell" onkeyup="validatePrice()" placeholder="Sell Rate" class="p-4 rounded-xl font-black text-2xl border-4 border-yellow-400">
                </div>
                
                <p id="priceError" class="text-rose-500 font-black hidden text-center italic">⚠️ FAIDA BOHOT ZYADA HAI!</p>

                <button type="submit" id="submitBtn" class="w-full bg-emerald-600 text-white py-5 rounded-2xl font-black text-2xl shadow-xl uppercase">Confirm Entry ✅</button>
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
            document.getElementById('stationeryFields').classList.toggle('hidden-field', cat !== 'Stationery');
            document.getElementById('statItemNameField').classList.toggle('hidden-field', cat !== 'Stationery');
            document.getElementById('bookFields').classList.toggle('hidden-field', cat === 'Stationery');
            checkDuplicate();
        }

        async function checkDuplicate() {
            const cat = document.getElementById('catSelect').value;
            let query = "";
            if(cat === 'Stationery') {
                const name = document.getElementById('statName').value;
                const tag = `${document.getElementById('statBrand').value} ${document.getElementById('statColor').value} ${document.getElementById('statType').value}`.trim();
                if(name.length < 2) return document.getElementById('existingAlert').classList.add('hidden');
                query = `name=${encodeURIComponent(name)}&tag=${encodeURIComponent(tag)}`;
            } else {
                const name = document.getElementById('bookName').value;
                const s_class = document.getElementById('bookClass').value;
                if(!name || !s_class) return document.getElementById('existingAlert').classList.add('hidden');
                query = `name=${encodeURIComponent(name)}&s_class=${encodeURIComponent(s_class)}`;
            }

            try {
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
            } catch(e) {}
        }

        function setEntryMode(isNew) {
            document.getElementById('forceNew').value = isNew;
            document.getElementById('formMode').value = isNew ? 'new' : 'update';
            const bM = document.getElementById('btnMerge');
            const bS = document.getElementById('btnSeparate');
            
            bM.className = isNew ? "p-4 rounded-xl border-2 border-slate-200 bg-white text-slate-400" : "p-4 rounded-xl border-2 border-amber-500 bg-amber-500 text-white shadow-lg";
            bS.className = isNew ? "p-4 rounded-xl border-2 border-indigo-600 bg-indigo-600 text-white shadow-lg" : "p-4 rounded-xl border-2 border-slate-200 bg-white text-slate-400";
            
            document.getElementById('submitBtn').innerText = isNew ? "SAVE AS NEW ENTRY ✅" : "CONFIRM & UPDATE STOCK 🔄";
            document.getElementById('submitBtn').className = isNew ? "w-full bg-indigo-600 text-white py-6 rounded-3xl font-black text-3xl" : "w-full bg-amber-500 text-white py-6 rounded-3xl font-black text-3xl";
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
            document.getElementById('priceError').classList.toggle('hidden', !(cost > 0 && sell > cost * 2));
        }

        document.getElementById('addProdForm').onsubmit = async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            btn.innerText = "SAVING..."; btn.disabled = true;
            
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
            btn.disabled = false;
            toggleModal(false);
            refreshData();
        };

        async function refreshData() {
            const res = await fetch('/api/inventory');
            inventory = await res.json();
            document.getElementById('inventoryTableBody').innerHTML = inventory.map(p => `
                <tr class="border-b-2 border-slate-100 hover:bg-indigo-50">
                    <td class="p-5"><div>${p.name}</div><div class="text-[10px] text-slate-400">#${p.id}</div></td>
                    <td class="p-5"><span class="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-lg text-xs">${p.category}</span></td>
                    <td class="p-5 text-slate-600 italic">${p.tag || ('CLASS ' + p.student_class)}</td>
                    <td class="p-5 font-mono">Rs. ${p.purchase_price}</td>
                    <td class="p-5 font-mono font-black text-indigo-600">Rs. ${p.selling_price}</td>
                    <td class="p-5 text-center"><div class="px-5 py-2 rounded-2xl font-black ${p.stock < 5 ? 'bg-rose-600 text-white' : 'bg-emerald-100 text-emerald-700'}">${p.stock}</div></td>
                </tr>`).join('');
            renderProducts(inventory);
        }

        function renderProducts(data) {
            document.getElementById('productGrid').innerHTML = data.map(p => `
                <div onclick="addToCart(${p.id})" class="bg-white p-6 rounded-3xl shadow-lg border-4 border-transparent hover:border-indigo-500 cursor-pointer relative overflow-hidden">
                    <div class="absolute top-0 right-0 bg-indigo-600 text-white px-3 py-1 text-[10px] font-black rounded-bl-xl">${p.category}</div>
                    <h3 class="font-black text-lg uppercase text-indigo-950">${p.name}</h3>
                    <p class="text-xs text-slate-400 font-bold">${p.tag || ('Class ' + p.student_class)}</p>
                    <div class="flex justify-between items-end mt-6">
                        <div class="text-3xl font-black text-indigo-600 font-mono">Rs. ${p.selling_price}</div>
                        <div class="text-xs px-3 py-2 rounded-xl font-black ${p.stock < 5 ? 'text-rose-600':'text-slate-600'}">Stock: ${p.stock}</div>
                    </div>
                </div>`).join('');
        }

        function filterProducts() {
            const q = document.getElementById('smartSearch').value.toLowerCase();
            renderProducts(inventory.filter(p => p.name.toLowerCase().includes(q) || (p.tag && p.tag.toLowerCase().includes(q)) || (p.student_class && p.student_class.includes(q))));
        }

        function addToCart(id) {
            const i = inventory.find(p => p.id === id);
            if(i.stock <= 0) return alert("❌ STOCK KHATAM!");
            cart.push({...i});
            updateCartUI();
        }

        function updateCartUI() {
            document.getElementById('cartItems').innerHTML = cart.map((i,idx)=>`
                <div class="flex justify-between items-center bg-white p-4 rounded-2xl border-2 border-indigo-100">
                    <div>${i.name}</div>
                    <div class="flex items-center space-x-4"><span>Rs. ${i.selling_price}</span><button onclick="cart.splice(${idx},1);updateCartUI()" class="text-rose-600 text-2xl">&times;</button></div>
                </div>`).join('');
            document.getElementById('orderTotal').innerText = cart.reduce((a, b) => a + b.selling_price, 0);
            document.getElementById('cartCount').innerText = cart.length;
        }

        async function completeSale() {
            if(cart.length === 0) return alert("Pehle item add karein!");
            const fd = new FormData();
            fd.append('p_name', document.getElementById('custName').value || 'Cash Parent');
            fd.append('p_phone', '0000');
            fd.append('items_json', JSON.stringify(cart.map(i => ({...i, qty:1}))));
            fd.append('total', document.getElementById('orderTotal').innerText);
            fd.append('status', document.getElementById('payStatus').value);
            
            const res = await fetch('/api/checkout', {method: 'POST', body: fd});
            if(res.ok) { cart=[]; updateCartUI(); refreshData(); alert("✅ BIKRI MUKAMMAL!"); }
        }

        window.onload = refreshData;
    </script>
</body>
</html>
