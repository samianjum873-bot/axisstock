file_path = 'app/templates/index.html'
with open(file_path, 'r') as f:
    content = f.read()

# 1. Update the Alert Box UI
old_alert = '<div id="existingAlert" class="hidden bg-yellow-400 p-3 text-center text-indigo-900 font-black text-xs uppercase animate-bounce">\n                ⚠️ Match Found! Updating existing product stock...\n            </div>'

new_alert = """<div id="existingAlert" class="hidden bg-amber-100 border-2 border-amber-400 p-4 rounded-2xl mb-4">
                <p class="text-amber-800 font-black text-sm text-center mb-3 uppercase">⚠️ Item Already Exists in Inventory!</p>
                <div class="grid grid-cols-2 gap-3">
                    <button type="button" onclick="setEntryMode(false)" id="btnMerge" class="bg-amber-500 text-white text-[10px] font-black p-2 rounded-lg border-b-4 border-amber-700 active:border-0">ADD TO EXISTING</button>
                    <button type="button" onclick="setEntryMode(true)" id="btnSeparate" class="bg-slate-500 text-white text-[10px] font-black p-2 rounded-lg border-b-4 border-slate-700 active:border-0">ADD SEPARATELY</button>
                </div>
                <input type="hidden" id="forceNew" name="force_new" value="false">
            </div>"""

content = content.replace(old_alert, new_alert)

# 2. Add setEntryMode function and update checkDuplicate
old_check_dup = """            if(data.id) {
                    alertBox.classList.remove('hidden');
                    document.getElementById('prod_id').value = data.id;
                    document.getElementById('formMode').value = 'update';
                    document.getElementById('perItemSell').value = data.selling_price;
                } else {"""

new_check_dup = """            if(data.id) {
                    alertBox.classList.remove('hidden');
                    document.getElementById('prod_id').value = data.id;
                    setEntryMode(false); // Default to update
                    document.getElementById('perItemSell').value = data.selling_price;
                } else {"""

content = content.replace(old_check_dup, new_check_dup)

# 3. Add the helper function script
script_addition = """
        function setEntryMode(isNew) {
            document.getElementById('forceNew').value = isNew;
            document.getElementById('formMode').value = isNew ? 'new' : 'update';
            const btnMerge = document.getElementById('btnMerge');
            const btnSep = document.getElementById('btnSeparate');
            
            if(isNew) {
                btnSep.classList.replace('bg-slate-500', 'bg-indigo-600');
                btnMerge.classList.replace('bg-amber-500', 'bg-slate-400');
            } else {
                btnMerge.classList.replace('bg-slate-400', 'bg-amber-500');
                btnSep.classList.replace('bg-indigo-600', 'bg-slate-500');
            }
        }
"""
content = content.replace("refreshData();", script_addition + "\n        refreshData();")

with open(file_path, 'w') as f:
    f.write(content)
