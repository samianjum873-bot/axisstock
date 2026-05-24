#!/usr/bin/env python3
import re

# 1. Restore main.py - remove any PermissionMiddleware and add role to template context
main_path = "app/main.py"
with open(main_path, "r") as f:
    content = f.read()

# Remove any PermissionMiddleware block if present
lines = content.splitlines()
new_lines = []
skip = False
for line in lines:
    if "class PermissionMiddleware" in line or "app.add_middleware(PermissionMiddleware)" in line:
        skip = True
        continue
    if skip and line.strip() == "":
        skip = False
        continue
    if skip:
        continue
    new_lines.append(line)
content = "\n".join(new_lines)

# Ensure that index and pos routes pass role to template
# Find index route and modify its return to include role
index_route_pattern = r'(@app\.get\("/"\)\s+async def index\(request: Request\):.*?return templates\.TemplateResponse\(request,\s*"pos_professional\.html",\s*\{.*?\}\))'
def add_role_to_index(match):
    func = match.group(1)
    if '"role":' not in func:
        # Add role to the dict
        func = func.replace('{"active_page": "pos"}', '{"active_page": "pos", "role": request.session.get("role")}')
    return func

content = re.sub(index_route_pattern, add_role_to_index, content, flags=re.DOTALL)

# Similarly for pos_page
pos_route_pattern = r'(@app\.get\("/pos"\)\s+async def pos_page\(request: Request\):.*?return templates\.TemplateResponse\(request,\s*"pos_professional\.html",\s*\{.*?\}\))'
def add_role_to_pos(match):
    func = match.group(1)
    if '"role":' not in func:
        func = func.replace('{"active_page": "pos"}', '{"active_page": "pos", "role": request.session.get("role")}')
    return func

content = re.sub(pos_route_pattern, add_role_to_pos, content, flags=re.DOTALL)

# Also other routes that extend index.html? They don't need to show sidebar? Actually they also extend index.html, so sidebar appears on all pages.
# We'll patch inventory, sales, customers, analytics, settings similarly.
routes_to_patch = [
    ('inventory_page', 'inventory.html'),
    ('sales_page', 'sales.html'),
    ('list_registered_customers', 'customers.html'),
    ('operations_analytics_dashboard', 'analytics.html'),
    ('settings_page', 'settings.html'),
]
for route_name, template in routes_to_patch:
    pattern = rf'(@app\.get\("[^"]+"\)\s+async def {route_name}\(request: Request\):.*?return templates\.TemplateResponse\(request,\s*"{template}",\s*\{{.*?\}\))'
    def make_patcher(template):
        def patcher(match):
            func = match.group(1)
            if '"role":' not in func:
                # Find the dict part
                dict_match = re.search(r'\{(.*?)\}', func, re.DOTALL)
                if dict_match:
                    old_dict = dict_match.group(0)
                    if old_dict.strip() == "{}":
                        new_dict = '{"role": request.session.get("role")}'
                    else:
                        new_dict = old_dict.rstrip('}') + ', "role": request.session.get("role")}'
                    func = func.replace(old_dict, new_dict)
            return func
        return patcher
    content = re.sub(pattern, make_patcher(template), content, flags=re.DOTALL)

with open(main_path, "w") as f:
    f.write(content)
print("✅ main.py cleaned and role added to templates")

# 2. Update index.html sidebar to use role
index_path = "app/templates/index.html"
with open(index_path, "r") as f:
    html = f.read()

# Find the sidebar nav block and replace with conditional based on role
old_sidebar = '<nav class="flex-1 mt-6 px-4 space-y-2">.*?</nav>'
# We'll replace the whole nav with a new one that shows full sidebar for admin, only POS for others
new_nav = '''
        <nav class="flex-1 mt-6 px-4 space-y-2">
            <!-- POS tab - always show -->
            <a href="/pos" id="link-pos" class="sidebar-link {% if active_page == 'pos' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-calculator w-8"></i> <span class="font-bold text-xs">COUNTER BILLING</span>
            </a>
            {% if role == 'admin' %}
            <a href="/inventory" id="link-inventory" class="sidebar-link {% if active_page == 'inventory' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-box-open w-8"></i> <span class="font-bold text-xs">STOCK MANAGER</span>
            </a>
            <a href="/sales" id="link-sales" class="sidebar-link {% if active_page == 'sales' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-history w-8"></i> <span class="font-bold text-xs">SALES HISTORY</span>
            </a>
            <a href="/customers" id="link-customers" class="sidebar-link {% if active_page == 'customers' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-users w-8"></i> <span class="font-bold text-xs">CUSTOMER DATABASE</span>
            </a>
            <a href="/analytics" id="link-analytics" class="sidebar-link {% if active_page == 'analytics' %}active{% endif %} w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-chart-pie w-8 text-yellow-400"></i> <span class="font-bold text-xs text-yellow-400">REPORTS & ANALYTICS</span>
            </a>
            <a href="/settings" id="link-settings" class="sidebar-link w-full flex items-center p-4 rounded-xl transition hover:bg-indigo-900">
                <i class="fas fa-cog w-8"></i> <span class="font-bold text-xs">SETTINGS</span>
            </a>
            {% endif %}
        </nav>
'''

# Use regex to replace the nav block
html = re.sub(r'<nav class="flex-1 mt-6 px-4 space-y-2">.*?</nav>', new_nav, html, flags=re.DOTALL)

with open(index_path, "w") as f:
    f.write(html)
print("✅ index.html sidebar updated to use role variable")

print("\n✅ All fixes applied. Restart the server: uvicorn app.main:app --reload")
