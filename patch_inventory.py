import re

file_path = 'app/templates/inventory.html'
with open(file_path, 'r') as f:
    content = f.read()

# 1. Inject CSS animations & Toast Box right before space-y-6
css_injection = """        @keyframes pulseNewItem {
            0%, 100% { background-color: rgba(220, 252, 231, 0.4); box-shadow: inset 0 0 0 2px rgba(34, 197, 94, 0.2); }
            50% { background-color: rgba(187, 247, 208, 0.8); box-shadow: inset 0 0 0 2px rgba(34, 197, 94, 0.6); }
        }
        .blink-new-row {
            animation: pulseNewItem 1.5s infinite ease-in-out;
        }
    </style>

    <!-- Toast Notification Container -->
    <div id="toast-container" class="fixed top-5 right-5 z-[9999] flex flex-col gap-3 pointer-events-none"></div>"""

content = content.replace('</style>', css_injection)

# 2. Replace FA Icons with Inline SVGs
content = content.replace('<i class="fas fa-search"></i>', '<svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>')
content = content.replace('<i class="fas fa-times-circle"></i>', '<svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>')
content = content.replace('<i class="fas fa-plus"></i>', '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>')
content = content.replace('<i class="fas fa-edit"></i>', '<svg class="w-3 h-3 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>')

# 3. Completely replace JS block with our upgraded logic
new_js = """<script>
        let fullInventory = [];
        let lowStockFilterActive = false;
        let newlyAddedSessionIds = []; // Tracks new items for blinking effect

        // Toast Notification System
        function showToast(message, type="success") {
            const container = document.getElementById('toast-container');
            if(!container) return;
            const toast = document.createElement('div');
            const bgColor = type === 'error' ? 'bg-rose-500' : 'bg-emerald-500';
            const icon = type === 'error' ? 
                '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>' : 
                '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
            
            toast.className = `px-4 py-3 rounded-xl text-white font-bold text-xs shadow-lg transform transition-all duration-300 translate-x-full flex items-center gap-2 ${bgColor}`;
            toast.innerHTML = `${icon} <span>${message}</span>`;
            container.appendChild(toast);
            
            requestAnimationFrame(() => setTimeout(() => toast.classList.remove('translate-x-full'), 10));
            setTimeout(() => {
                toast.classList.add('translate-x-full');
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        async function loadInventory() {
            try {
                const response = await fetch('/api/inventory');
                fullInventory = await response.json();
                calculateAnalyticsMetrics(fullInventory);
                masterFilter(); 
            } catch (error) {
                console.error("Error fetching inventory:", error);
            }
        }

        function formatCompactNumber(number) {
            if (number === 0) return "0";
            const formatter = Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });
            return formatter.format(number);
        }

        function calculateAnalyticsMetrics(items) {
            let totalUnique = items.length;
            let totalStockUnits = 0;
            let totalValuation = 0;
            let lowStockCount = 0;
            let catBookCount = 0, catNotebookCount = 0, catStationeryCount = 0;

            items.forEach(item => {
                const stock = parseInt(item.stock) || 0;
                const pPrice = parseFloat(item.purchase_price) || 0;
                totalStockUnits += stock;
                totalValuation += (stock * pPrice);
                if (stock < 10) lowStockCount++;

                if (item.category === "Book") catBookCount += stock;
                else if (item.category === "Notebook") catNotebookCount += stock;
                else catStationeryCount += stock;
            });

            document.getElementById("kpiTotalItems").innerText = formatCompactNumber(totalUnique);
            document.getElementById("kpiTotalStock").innerText = formatCompactNumber(totalStockUnits);
            document.getElementById("kpiValuation").innerText = "Rs " + formatCompactNumber(totalValuation);
            document.getElementById("kpiLowStock").innerText = lowStockCount;
            document.getElementById("kpiStockBreakdown").innerText = `Books: ${formatCompactNumber(catBookCount)} | Notebooks: ${formatCompactNumber(catNotebookCount)} | Stat.: ${formatCompactNumber(catStationeryCount)}`;
        }

        function toggleLowStockFilter() {
            lowStockFilterActive = !lowStockFilterActive;
            const card = document.getElementById("cardLowStockAlert");
            const pill = document.getElementById("activeFilterPill");
            const subtext = document.getElementById("lowStockCardSubtext");

            if (lowStockFilterActive) {
                card.className = "bg-rose-900 border-rose-950 p-4 rounded-2xl border shadow-md cursor-pointer transition-all scale-[1.02] relative overflow-hidden group select-none text-white";
                document.getElementById("kpiLowStock").className = "text-2xl font-black text-white mt-1";
                subtext.className = "text-[10px] text-rose-200 font-bold mt-1";
                subtext.innerText = "🛑 Showing low stock variants only";
                pill.classList.remove("hidden");
                pill.classList.add("flex");
            } else {
                card.className = "bg-gradient-to-br from-rose-50 to-rose-100/50 p-4 rounded-2xl border border-rose-100 shadow-sm cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98] relative overflow-hidden group select-none";
                document.getElementById("kpiLowStock").className = "text-2xl font-black text-rose-950 mt-1";
                subtext.className = "text-[10px] text-rose-600/80 font-bold mt-1";
                subtext.innerText = "Items with less than 10 units";
                pill.classList.remove("flex");
                pill.classList.add("hidden");
            }
            masterFilter();
        }

        function toggleSubFilters() {
            const cat = document.getElementById("filterCat").value;
            const classInput = document.getElementById("filterClass");
            const subInput = document.getElementById("filterSubject");
            if (cat === "Book") { classInput.classList.remove("hidden"); subInput.classList.remove("hidden"); } 
            else if (cat === "Notebook") { classInput.classList.remove("hidden"); subInput.classList.add("hidden"); subInput.value = ""; } 
            else { classInput.classList.add("hidden"); subInput.classList.add("hidden"); classInput.value = ""; subInput.value = ""; }
        }

        function masterFilter() {
            const omniToken = document.getElementById("filterOmni").value.toLowerCase();
            const catToken = document.getElementById("filterCat").value.toLowerCase();
            const classToken = document.getElementById("filterClass").value.toLowerCase();
            const subToken = document.getElementById("filterSubject").value.toLowerCase();

            const filtered = fullInventory.filter(item => {
                const matchesCat = !catToken || item.category.toLowerCase().includes(catToken);
                const matchesClass = !classToken || (item.student_class && item.student_class.toLowerCase().includes(classToken));
                const matchesSub = !subToken || (item.subject && item.subject.toLowerCase().includes(subToken));
                const matchesOmni = !omniToken || item.name.toLowerCase().includes(omniToken) || item.sku.toLowerCase().includes(omniToken) || (item.barcode && item.barcode.toLowerCase().includes(omniToken)) || (item.student_class && item.student_class.toLowerCase().includes(omniToken)) || (item.subject && item.subject.toLowerCase().includes(omniToken));
                const matchesLowStock = !lowStockFilterActive || (parseInt(item.stock) < 10);
                return matchesCat && matchesClass && matchesSub && matchesOmni && matchesLowStock;
            });
            renderTable(filtered);
        }

        function renderTable(data) {
            const tbody = document.getElementById("inventoryTableBody");
            tbody.innerHTML = "";

            if(data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" class="p-8 text-center text-slate-400 font-medium">No inventory blueprints matched active filters</td></tr>`;
                return;
            }

            // Professional identification of Top Sellers
            const getSoldQty = (itm) => parseInt(itm.sold_quantity || itm.sales || itm.total_sold || 0);
            const topSellers = [...data].sort((a,b) => getSoldQty(b) - getSoldQty(a));
            const top5Ids = topSellers.filter(x => getSoldQty(x) > 0).slice(0, 5).map(x => x.id);

            const now = new Date();

            data.forEach(item => {
                const tr = document.createElement("tr");

                // Determine tags & shades
                let isRecent = false;
                if (item.created_at) { isRecent = (now - new Date(item.created_at)) < 86400000; }
                const isJustAdded = newlyAddedSessionIds.includes(item.id);
                const topRank = top5Ids.indexOf(item.id) + 1;

                // Priority Hierarchy Styling
                if (lowStockFilterActive) {
                    tr.className = "low-stock-pulse-row text-slate-700 transition duration-150 text-xs border-b border-rose-200";
                } else if (isJustAdded) {
                    tr.className = "blink-new-row text-slate-800 transition duration-150 text-xs border-b border-green-200";
                } else if (isRecent) {
                    tr.className = "bg-green-50/40 text-slate-700 transition duration-150 text-xs border-b border-green-100 hover:bg-green-50/80";
                } else if (topRank > 0) {
                    tr.className = "bg-blue-50/30 text-slate-800 transition duration-150 text-xs border-b border-blue-100 hover:bg-blue-50/70";
                } else {
                    tr.className = "hover:bg-slate-50/60 text-slate-700 transition duration-150 text-xs border-b border-slate-100";
                }
                
                let dynamicDisplayIdentity = "";
                if (item.category === "Book") {
                    dynamicDisplayIdentity = `<div class="font-black text-indigo-700 text-[13px] uppercase tracking-wide">Class: ${item.student_class || 'General'} <span class="text-slate-300 mx-1.5">|</span> Subject: ${item.subject || 'N/A'}</div><div class="text-[11px] font-bold text-slate-500 mt-0.5">${item.name} ${item.variation ? ' - ' + item.variation : ''}</div>`;
                } else if (item.category === "Notebook") {
                    dynamicDisplayIdentity = `<div class="font-black text-emerald-700 text-[13px] uppercase tracking-wide">Class: ${item.student_class || 'General'} Notebook</div><div class="text-[11px] font-bold text-slate-500 mt-0.5">${item.name || 'Standard'} ${item.variation ? ' - ' + item.variation : ''}</div>`;
                } else {
                    dynamicDisplayIdentity = `<div class="font-black text-slate-900 text-[13px]">${item.name}</div><div class="text-[11px] font-bold text-slate-400 mt-0.5">${item.variation || 'Standard Unit'}</div>`;
                }

                let badgesHtml = `<div class="mt-1.5 flex flex-wrap gap-1.5">`;
                if (topRank > 0) { badgesHtml += `<span class="bg-blue-100 text-blue-700 border border-blue-200 px-1.5 py-0.5 rounded text-[8px] font-black uppercase shadow-xs">🏆 Top ${topRank} Selling</span>`; }
                if (isJustAdded || isRecent) { badgesHtml += `<span class="bg-green-100 text-green-700 border border-green-200 px-1.5 py-0.5 rounded text-[8px] font-black uppercase shadow-xs">✨ Recently Added</span>`; }
                badgesHtml += `</div>`;

                tr.innerHTML = `
                    <td class="p-4 max-w-xs">
                        ${dynamicDisplayIdentity}
                        ${badgesHtml}
                        <div class="text-[10px] font-mono text-slate-400 flex items-center space-x-2 mt-2">
                            <span class="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 font-bold">SKU: ${item.sku}</span>
                            <span>•</span><span>BC: ${item.barcode || 'None'}</span>
                        </div>
                    </td>
                    <td class="p-4 vertical-align-middle"><span class="text-[9px] px-2 py-0.5 rounded-full bg-slate-900 text-white font-black uppercase tracking-wider shadow-xs">${item.category}</span></td>
                    <td class="p-4">
                        <div class="text-[10px] text-slate-400 font-bold">Cost: Rs ${item.purchase_price}</div>
                        <div class="text-slate-900 font-black text-xs mt-0.5">Sale: Rs ${item.selling_price}</div>
                    </td>
                    <td class="p-4 text-center">
                        <span class="px-2.5 py-1 rounded-xl text-xs font-black inline-block border ${item.stock < 10 ? 'bg-rose-50 text-rose-700 border-rose-200 animate-pulse' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}">
                            ${formatCompactNumber(item.stock)} units
                        </span>
                    </td>
                    <td class="p-4 text-right space-x-1 whitespace-nowrap">
                        <button onclick="openProductModal('update', ${item.id})" class="text-xs bg-slate-100 text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 px-3 py-1.5 rounded-xl font-black uppercase text-[10px] transition shadow-xs border border-transparent hover:border-indigo-100">
                            <svg class="w-3 h-3 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg> Restock
                        </button>
                        <a href="/product/${item.id}" class="inline-block text-xs text-white bg-slate-900 hover:bg-slate-800 px-3 py-1.5 rounded-xl font-black uppercase text-[10px] tracking-wide transition shadow-xs">Ledger →</a>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        function openProductModal(mode, prodId = null) {
            document.getElementById("productForm").reset();
            document.getElementById("formMode").value = mode;
            document.getElementById("productModal").classList.remove("hidden");

            if (mode === 'add') {
                document.getElementById("modalTitle").innerText = "Create New Inventory Item Asset";
                document.getElementById("formProdId").value = "";
                document.getElementById("prodCat").disabled = false;
                document.getElementById("stockLabel").innerText = "Initial Stock *";
                adaptFormToCategory();
            } else {
                document.getElementById("modalTitle").innerText = "Update Existing Item Element";
                document.getElementById("formProdId").value = prodId;
                document.getElementById("prodCat").disabled = true;
                // LABEL CHANGED FOR OVERWRITE UX
                document.getElementById("stockLabel").innerText = "Current Stock (Overwrite) *";
                
                const item = fullInventory.find(x => x.id === prodId);
                if (item) {
                    document.getElementById("prodCat").value = item.category;
                    document.getElementById("prodName").value = item.name;
                    document.getElementById("prodClass").value = item.student_class || "";
                    document.getElementById("prodSubject").value = item.subject || "";
                    document.getElementById("prodVariation").value = item.variation || "";
                    document.getElementById("prodBarcode").value = item.barcode || "";
                    document.getElementById("prodPPrice").value = item.purchase_price;
                    document.getElementById("prodSPrice").value = item.selling_price;
                    // PRE-FILL EXISTING STOCK FOR OVERWRITING
                    document.getElementById("prodStock").value = item.stock; 
                    adaptFormToCategory();
                }
            }
        }

        function closeProductModal() { document.getElementById("productModal").classList.add("hidden"); }

        function adaptFormToCategory() {
            const cat = document.getElementById("prodCat").value;
            const classWrapper = document.getElementById("classFieldWrapper");
            const subWrapper = document.getElementById("subjectFieldWrapper");
            if (cat === "Book") { classWrapper.classList.remove("hidden"); subWrapper.classList.remove("hidden"); } 
            else if (cat === "Notebook") { classWrapper.classList.remove("hidden"); subWrapper.classList.add("hidden"); document.getElementById("prodSubject").value = ""; } 
            else { classWrapper.classList.add("hidden"); subWrapper.classList.add("hidden"); document.getElementById("prodClass").value = ""; document.getElementById("prodSubject").value = ""; }
        }

        async function handleFormSubmission(e) {
            e.preventDefault();
            
            // STRICT VALIDATION
            const pPrice = parseFloat(document.getElementById("prodPPrice").value);
            const sPrice = parseFloat(document.getElementById("prodSPrice").value);
            if (sPrice < pPrice) {
                showToast("Selling price cannot be less than Buying cost!", "error");
                return;
            }

            const mode = document.getElementById("formMode").value;
            const formData = new FormData();
            formData.append("mode", mode);
            formData.append("prod_id", document.getElementById("formProdId").value);
            formData.append("cat", document.getElementById("prodCat").value);
            formData.append("name", document.getElementById("prodName").value);
            formData.append("s_class", document.getElementById("prodClass").value);
            formData.append("sub", document.getElementById("prodSubject").value);
            formData.append("variation", document.getElementById("prodVariation").value);
            formData.append("barcode", document.getElementById("prodBarcode").value);
            formData.append("p_price", document.getElementById("prodPPrice").value);
            formData.append("s_price", document.getElementById("prodSPrice").value);
            formData.append("stock", document.getElementById("prodStock").value);
            formData.append("force_new", "false");
            formData.append("overwrite_stock", "true"); // Hint to backend if needed

            // Track existing IDs to find exactly what got created
            const existingIds = fullInventory.map(x => x.id);

            try {
                const response = await fetch('/api/products/smart-add', { method: 'POST', body: formData });
                const result = await response.json();
                
                if (result.status === "success") {
                    showToast(mode === 'add' ? "New product added successfully!" : "Inventory updated successfully!", "success");
                    closeProductModal();
                    
                    // Reload and identify new additions to trigger blink effect
                    await loadInventory();
                    if (mode === 'add') {
                        const newItems = fullInventory.filter(x => !existingIds.includes(x.id));
                        newItems.forEach(x => newlyAddedSessionIds.push(x.id));
                        masterFilter(); // re-render to show blinking effect
                    }
                } else {
                    showToast("Error saving data: " + result.message, "error");
                }
            } catch (error) {
                showToast("Network connectivity mapping drop anomaly.", "error");
            }
        }

        document.addEventListener("DOMContentLoaded", loadInventory);
    </script>"""

# Find existing script block and replace it
import re
content = re.sub(r'<script>.*?</script>', new_js, content, flags=re.DOTALL)

with open(file_path, 'w') as f:
    f.write(content)

print("✅ Patch applied successfully! Start your app and check the awesome new features.")
