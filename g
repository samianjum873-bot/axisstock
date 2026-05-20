import os
import re

def scan_axisstock():
    print("🔍 Scanning AxisStock Project for Offline Readiness...\n")
    
    templates_dir = "app/templates"
    static_dir = "app/static"
    main_file = "app/main.py"
    
    online_cdn_patterns = [
        r'https://cdn\.jsdelivr\.net',
        r'https://cdnjs\.cloudflare\.com',
        r'https://code\.jquery\.com',
        r'https://fonts\.googleapis\.com',
        r'https://unpkg\.com'
    ]
    
    # 1. Scan app/main.py for core structures
    print("--- [ 1. Core Backend Check ] ---")
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"✅ {main_file} found.")
            if "app.mount(\"/static\"" in content:
                print("  -> Static files routing is correctly configured.")
            else:
                print("  ⚠️ Warning: Static files routing might be missing!")
    else:
        print(f"❌ Core file {main_file} not found!")

    print("\n--- [ 2. HTML Templates & Online CDN Dependency Check ] ---")
    if os.path.exists(templates_dir):
        for root, dirs, files in os.walk(templates_dir):
            for file in files:
                if file.endswith('.html'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    found_cdns = []
                    for line_no, line in enumerate(lines, 1):
                        for pattern in online_cdn_patterns:
                            if re.search(pattern, line):
                                found_cdns.append((line_no, line.strip()))
                    
                    if found_cdns:
                        print(f"⚠️ {file} requires Internet! Found {len(found_cdns)} online links:")
                        for no, text in found_cdns[:3]: # Show first 3
                            print(f"   Line {no}: {text[:80]}...")
                    else:
                        print(f"✅ {file} is fully local / clean.")
    else:
        print("❌ Templates directory missing!")

    print("\n--- [ 3. Static Assets Check ] ---")
    if os.path.exists(static_dir):
        static_files = []
        for root, dirs, files in os.walk(static_dir):
            for f in files:
                static_files.append(f)
        print(f"Total files in app/static: {len(static_files)}")
        if len(static_files) == 0:
            print("  ⚠️ Warning: app/static is EMPTY. If templates have online links, we need to download assets here.")
    else:
        print("❌ Static directory missing!")

if __name__ == "__main__":
    scan_project_dir = os.getcwd()
    if os.path.basename(scan_project_dir) == "axisstock":
        scan_axisstock()
    else:
        print("❌ Please run this script from inside the 'axisstock' root directory!")
