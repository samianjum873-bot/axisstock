import os

path = 'app/templates/index.html'
with open(path, 'r') as f:
    content = f.read()

# CSS update for modal scrolling
old_style = ".modal-content { max-height: 90vh; overflow-y: auto; width: 95%; max-width: 800px; }"
new_style = ".modal-content { width: 95%; max-width: 800px; margin: auto; }"

# Modal container update to allow scrolling
old_modal = ".modal { display: none; background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px); }"
new_modal = ".modal { display: none; background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px); overflow-y: auto; padding: 20px 0; }"

content = content.replace(old_style, new_style).replace(old_modal, new_modal)

# JS update to lock body scroll
old_js = "document.getElementById('addModal').classList.toggle('active', show);"
new_js = """document.getElementById('addModal').classList.toggle('active', show);
            document.body.style.overflow = show ? 'hidden' : 'auto';"""

content = content.replace(old_js, new_js)

with open(path, 'w') as f:
    f.write(content)

print("✅ Scroll Logic Fixed! Ab Form aram se scroll hoga.")
