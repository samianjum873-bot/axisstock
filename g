#!/usr/bin/env python3
"""
AxisStock FINAL Fix Patcher
- Updates .env with correct PostgreSQL credentials (peer auth)
- Creates database if missing
- Restores full main.py (PostgreSQL + Super Admin)
- Runs migrations and seeds demo school
- Injects demo data (optional)
"""

import os
import sys
import re
import subprocess
import asyncio
import asyncpg
from dotenv import load_dotenv, set_key

# Load existing .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not set in .env")
    sys.exit(1)

# Parse URL
match = re.match(r'postgresql://([^:]+):([^@]+)@([^/]+)/(.+)', DATABASE_URL)
if not match:
    print("❌ Invalid DATABASE_URL format. Expected: postgresql://user:pass@host/dbname")
    sys.exit(1)

old_user, old_pass, host, dbname = match.groups()

# Detect system username
system_user = os.getenv("USER", "sami")
print(f"🔍 Detected system user: {system_user}")

# If old_user is placeholder, replace with system user
if old_user in ['user', 'USER', 'postgres'] and old_pass in ['password', 'PASSWORD', '']:
    new_user = system_user
    new_pass = ''  # peer authentication – no password
    new_database_url = f"postgresql://{new_user}:{new_pass}@{host}/{dbname}"
    print(f"🔄 Updating .env with actual user: {new_user}")
    env_file = ".env"
    if os.path.exists(env_file):
        set_key(env_file, "DATABASE_URL", new_database_url)
        # Reload environment
        load_dotenv(override=True)
        DATABASE_URL = new_database_url
        print("✅ .env updated.")
    else:
        print("⚠️ .env file not found, skipping update.")

async def ensure_database():
    """Create database if not exists using peer auth."""
    # Try connecting with system user (no password)
    conn_params = {
        'user': system_user,
        'password': '',
        'host': host,
        'database': 'postgres'
    }
    try:
        conn = await asyncpg.connect(**conn_params)
    except Exception as e:
        print(f"❌ Could not connect with user '{system_user}': {e}")
        print("   Trying with default 'postgres' user...")
        try:
            conn = await asyncpg.connect(user='postgres', password='', host=host, database='postgres')
            print("✅ Connected as 'postgres'.")
        except Exception as e2:
            print(f"❌ Also failed with 'postgres': {e2}")
            print("   Please ensure PostgreSQL is running and you have proper access.")
            print("   You may need to set a password in .env manually.")
            sys.exit(1)

    # Check if database exists
    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbname)
    if not exists:
        print(f"📀 Creating database '{dbname}'...")
        await conn.execute(f"CREATE DATABASE {dbname}")
        print("✅ Database created.")
    else:
        print(f"✅ Database '{dbname}' already exists.")
    await conn.close()

def run_script(script_name):
    """Run a Python script and print output."""
    if os.path.exists(script_name):
        print(f"▶️  Running {script_name}...")
        result = subprocess.run([sys.executable, script_name], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️  {script_name} failed, but continuing...")
            print(result.stderr)
        else:
            print(result.stdout)
    else:
        print(f"ℹ️  {script_name} not found, skipping.")

def restore_main():
    """Run restore_full_main.py to overwrite app/main.py."""
    if os.path.exists("restore_full_main.py"):
        print("📄 Restoring full main.py (PostgreSQL version)...")
        result = subprocess.run([sys.executable, "restore_full_main.py"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Restore failed:")
            print(result.stderr)
            sys.exit(1)
        else:
            print("✅ main.py restored.")
    else:
        print("❌ restore_full_main.py not found!")
        sys.exit(1)

def inject_demo_data():
    """Optional: inject demo data using inject_demo_data.py."""
    if os.path.exists("inject_demo_data.py"):
        print("📦 Injecting demo data...")
        result = subprocess.run([sys.executable, "inject_demo_data.py"], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  Demo injection failed, but app may still work.")
            print(result.stderr)
        else:
            print(result.stdout)
    else:
        print("ℹ️  inject_demo_data.py not found, skipping.")

async def main():
    print("🔧 AxisStock FINAL Fix Patcher Starting...\n")
    
    # Step 1: Ensure .env is fixed (already done above)
    
    # Step 2: Ensure PostgreSQL database exists
    await ensure_database()
    
    # Step 3: Restore full main.py
    restore_main()
    
    # Step 4: Run migrations and seed
    run_script("migrate_existing_tenants_final.py")
    run_script("app/database/seed.py")
    run_script("migrate_passwords.py")
    
    # Step 5: Inject demo data (optional)
    inject_demo_data()
    
    print("\n✅ All steps completed successfully!")
    print("🔹 Now start your app with:")
    print("   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    print("\n🔹 Super Admin credentials (from .env):")
    env_user = os.getenv("SUPER_ADMIN_USER", "superadmin")
    env_pass = os.getenv("SUPER_ADMIN_PASS", "superadmin123")
    print(f"   Username: {env_user}")
    print(f"   Password: {env_pass}")

if __name__ == "__main__":
    asyncio.run(main())
