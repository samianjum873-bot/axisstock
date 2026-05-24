import re

with open("app/main.py", "r") as f:
    content = f.read()

# 1. Remove the entire PermissionMiddleware block if present
# Look for the middleware addition and remove it
middleware_start = "# Add a middleware to inject user_permissions"
if middleware_start in content:
    # Find the end of the middleware addition (until the next blank line or app.mount)
    lines = content.splitlines()
    new_lines = []
    skip = False
    for line in lines:
        if middleware_start in line:
            skip = True
            continue
        if skip and line.strip() == "":
            skip = False
            continue
        if skip:
            continue
        new_lines.append(line)
    content = "\n".join(new_lines)
    print("✅ Removed PermissionMiddleware")

# 2. For each route that uses index.html, add user_permissions to template context
# Routes: index, pos, inventory, sales, customers, analytics, settings

# Helper function to add user_permissions to return statements
def add_perms_to_route(content, route_name, template_name, context_vars):
    # Find the route function and its return statement
    # We'll do a simple replace for the return line
    # For each route, we'll add perms = await get_user_permissions(request) if not already there
    # and modify the return to include "user_permissions": perms
    
    # Find the function definition
    pattern = rf'(async def {route_name}\(request: Request\):.*?)(?=\n\s*@app\.|\n\s*async def |\n\s*$|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print(f"⚠️ Could not find route {route_name}")
        return content
    
    func_body = match.group(1)
    
    # Check if already has user_permissions in return
    if 'user_permissions' in func_body:
        print(f"✅ {route_name} already has user_permissions")
        return content
    
    # Add perms = await get_user_permissions(request) after the if not is_logged_in check
    lines = func_body.splitlines()
    new_func_lines = []
    added_perms = False
    for i, line in enumerate(lines):
        new_func_lines.append(line)
        if not added_perms and 'if not is_logged_in(request):' in line:
            # Add perms after the check (on next line)
            # Find the next line that is not indented? We'll just add after the if block.
            # Simpler: after the line that does `if not is_logged_in...` and its return.
            pass
    # Better approach: replace the return line directly.
    # We'll find the line with `return templates.TemplateResponse(...`
    for i, line in enumerate(lines):
        if 'return templates.TemplateResponse' in line and 'user_permissions' not in line:
            # Insert perms = await get_user_permissions(request) before this line, and modify return
            indent = re.match(r'(\s*)', line).group(1)
            new_func_lines.insert(i, f'{indent}perms = await get_user_permissions(request)')
            # Modify the return line to add user_permissions
            new_line = line.replace('})', ', "user_permissions": perms})')
            new_func_lines[i+1] = new_line
            added_perms = True
            break
    
    if added_perms:
        new_func_body = "\n".join(new_func_lines)
        content = content.replace(func_body, new_func_body)
        print(f"✅ Updated {route_name} to pass user_permissions")
    else:
        print(f"⚠️ Could not update {route_name}")
    
    return content

# Routes to patch
routes = [
    ('index', 'pos_professional.html'),
    ('pos_page', 'pos_professional.html'),
    ('inventory_page', 'inventory.html'),
    ('sales_page', 'sales.html'),
    ('list_registered_customers', 'customers.html'),
    ('operations_analytics_dashboard', 'analytics.html'),
    ('settings_page', 'settings.html'),
]

for route_name, template in routes:
    content = add_perms_to_route(content, route_name, template)

# Write back
with open("app/main.py", "w") as f:
    f.write(content)

print("\n✅ main.py fixed. Restart the server now.")
