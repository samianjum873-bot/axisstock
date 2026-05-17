import re
import os

file_path = "app/templates/inventory.html"

if not os.path.exists(file_path):
    print(f"Error: {file_path} not found!")
    exit(1)

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Target block: The row containing Variation and Barcode inputs
target_pattern = r'(<div class="grid grid-cols-2 gap-3">.*?prodBarcode.*?</div>\s*</div>)'

# The new HTML block for Supplier selection to insert right after
supplier_block = """

                <!-- Automated Supplier Field Injection -->
                <div>
                    <label class="block text-[10px] font-black uppercase text-slate-500 mb-1">Supplier / Vendor Source *</label>
                    <select id="prodSupplier" required class="w-full border p-3 rounded-xl font-bold bg-slate-50 focus:border-indigo-600 focus:outline-none">
                        <option value="">Select Supplier</option>
                        <option value="Oxford University Press">Oxford University Press</option>
                        <option value="Paramount Books">Paramount Books</option>
                        <option value="Local Market City">Local Market City</option>
                        <option value="Direct Mill Distributor">Direct Mill Distributor</option>
                    </select>
                </div>"""

# Check if already patched to prevent double injection
if "prodSupplier" in content:
    print("Patcher Warning: Supplier field already exists in the template form.")
else:
    # Perform exact regex injection safely
    updated_content, count = re.subn(target_pattern, r"\1" + supplier_block, content, flags=re.DOTALL)
    
    if count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print("Success: Supplier field safely patched inside the template form container!")
    else:
        print("Error: Could not locate the exact form layout match inside the HTML file.")
