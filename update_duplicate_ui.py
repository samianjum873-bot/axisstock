import os

path = 'app/templates/index.html'
with open(path, 'r') as f:
    content = f.read()

# 1. Update the Alert Box UI for better clarity
old_alert = '<div id="existingAlert" class="hidden bg-amber-100 border-4 border-amber-500 p-5 m-6 rounded-2xl animate-bounce">'
new_alert = """<div id="existingAlert" class="hidden bg-amber-50 border-l-[12px] border-amber-500 p-6 m-6 rounded-r-2xl shadow-xl">
                <div class="flex items-center mb-4">
                    <i class="fas fa-exclamation-triangle text-amber-500 text-3xl mr-4"></i>
                    <div>
                        <h4 class="text-amber-900 font-black text-xl uppercase">Yeh Item Pehle Se Hai!</h4>
                        <p class="text-amber-700 text-sm font-bold">System ko milta julta product mil gaya hai. Aap kya karna chahte hain?</p>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <button type="button" onclick="setEntryMode(false)" id="btnMerge" class="group p-4 rounded-xl border-2 border-amber-500 bg-amber-500 text-white transition-all">
                        <div class="font-black text-lg uppercase">Update Existing</div>
                        <div class="text-[10px] opacity-90 uppercase font-bold">Purane stock mein Quantity jama hogi</div>
                    </button>
                    <button type="button" onclick="setEntryMode(true)" id="btnSeparate" class="group p-4 rounded-xl border-2 border-slate-300 bg-white text-slate-600 hover:border-indigo-600 transition-all">
                        <div class="font-black text-lg uppercase text-slate-900">Add as New</div>
                        <div class="text-[10px] opacity-70 uppercase font-bold">Bilkul naya entry ban jaye ga</div>
                    </button>
                </div>
            </div>"""

if old_alert in content:
    content = content.replace(old_alert, new_alert)

# 2. Update setEntryMode JS to handle visual feedback
old_mode_js = """        function setEntryMode(isNew) {
            document.getElementById('forceNew').value = isNew;
            document.getElementById('formMode').value = isNew ? 'new' : 'update';
            const bM = document.getElementById('btnMerge');
            const bS = document.getElementById('btnSeparate');
            if(isNew) {
                bS.className = "bg-indigo-600 text-white font-black p-4 rounded-xl text-sm uppercase";
                bM.className = "bg-slate-400 text-white font-black p-4 rounded-xl text-sm uppercase";
            } else {
                bM.className = "bg-amber-500 text-white font-black p-4 rounded-xl text-sm uppercase shadow-lg";
                bS.className = "bg-slate-400 text-white font-black p-4 rounded-xl text-sm uppercase";
            }
        }"""

new_mode_js = """        function setEntryMode(isNew) {
            document.getElementById('forceNew').value = isNew;
            document.getElementById('formMode').value = isNew ? 'new' : 'update';
            const bM = document.getElementById('btnMerge');
            const bS = document.getElementById('btnSeparate');
            
            if(isNew) {
                bS.className = "p-4 rounded-xl border-2 border-indigo-600 bg-indigo-600 text-white shadow-lg transition-all";
                bM.className = "p-4 rounded-xl border-2 border-slate-200 bg-white text-slate-400 transition-all";
                document.getElementById('submitBtn').innerText = "SAVE AS NEW ENTRY ✅";
                document.getElementById('submitBtn').className = "w-full bg-indigo-600 hover:bg-indigo-700 text-white py-6 rounded-3xl font-black text-3xl shadow-2xl transition uppercase tracking-widest";
            } else {
                bM.className = "p-4 rounded-xl border-2 border-amber-500 bg-amber-500 text-white shadow-lg transition-all";
                bS.className = "p-4 rounded-xl border-2 border-slate-200 bg-white text-slate-400 transition-all";
                document.getElementById('submitBtn').innerText = "CONFIRM & UPDATE STOCK 🔄";
                document.getElementById('submitBtn').className = "w-full bg-amber-500 hover:bg-amber-600 text-white py-6 rounded-3xl font-black text-3xl shadow-2xl transition uppercase tracking-widest";
            }
        }"""

content = content.replace(old_mode_js, new_mode_js)

with open(path, 'w') as f:
    f.write(content)

print("✅ Professional Duplicate UI Enabled!")
