file_path = 'app/templates/index.html'
with open(file_path, 'r') as f:
    content = f.read()

# Correct the checkDuplicate logic
old_logic = """            if(cat === 'Stationery') {
                const name = document.getElementById('statName').value;
                const brand = document.getElementById('statBrand').value;
                const color = document.getElementById('statColor').value;
                if(name.length < 2) return;
                query = `name=${name}&brand=${brand}&color=${color}`;
            }"""

new_logic = """            if(cat === 'Stationery') {
                const name = document.getElementById('statName').value;
                const brand = document.getElementById('statBrand').value;
                const color = document.getElementById('statColor').value;
                const type = document.getElementById('statType').value;
                if(name.length < 2) return;
                // Important: Tag must match how it is saved
                const tag = `${brand} ${color} ${type}`.trim();
                query = `tag=${encodeURIComponent(tag)}`;
            }"""

content = content.replace(old_logic, new_logic)

with open(file_path, 'w') as f:
    f.write(content)
