#!/usr/bin/env python3
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def repair_tenant(conn, schema):
    print(f"\n🔧 Repairing schema: {schema}")
    await conn.execute(f'SET search_path TO "{schema}"')
    
    # 1. Add missing columns (idempotent)
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)")
    await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    # 2. Ensure all users are active
    await conn.execute("UPDATE users SET is_active = TRUE WHERE is_active IS NULL")
    
    # 3. Ensure admin role exists
    admin_role_id = await conn.fetchval("SELECT id FROM roles WHERE name = 'admin'")
    if not admin_role_id:
        admin_role_id = await conn.fetchval("""
            INSERT INTO roles (name, description) VALUES ('admin', 'Full access to all features')
            ON CONFLICT (name) DO UPDATE SET name = 'admin' RETURNING id
        """)
        print(f"  → Created admin role with id {admin_role_id}")
    else:
        print(f"  → Admin role exists (id: {admin_role_id})")
    
    # 4. Get all permission IDs
    perm_ids = await conn.fetch("SELECT id FROM permissions")
    print(f"  → Found {len(perm_ids)} permissions")
    
    # 5. Assign all permissions to admin role
    assigned = 0
    for p in perm_ids:
        result = await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, admin_role_id, p['id'])
        assigned += 1 if result == "INSERT 0 1" else 0
    print(f"  → Assigned {assigned} new permissions to admin role (total {len(perm_ids)})")
    
    # 6. Find the admin user (either username 'admin' or the first user)
    admin_user = await conn.fetchrow("SELECT id, username FROM users WHERE username = 'admin'")
    if not admin_user:
        admin_user = await conn.fetchrow("SELECT id, username FROM users ORDER BY id LIMIT 1")
    if admin_user:
        # Assign admin role to this user
        await conn.execute("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, admin_user['id'], admin_role_id)
        print(f"  → Assigned admin role to user '{admin_user['username']}' (id: {admin_user['id']})")
    else:
        print("  ⚠️ No user found in this tenant!")
    
    # 7. Verify that the admin user now has permissions
    perms = await conn.fetch("""
        SELECT DISTINCT p.name FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        WHERE ur.user_id = $1
    """, admin_user['id'] if admin_user else 0)
    perm_names = [p['name'] for p in perms]
    if 'pos_access' in perm_names:
        print(f"  ✅ SUCCESS: Admin user has 'pos_access' permission")
    else:
        print(f"  ❌ WARNING: Admin user missing permissions. Found: {perm_names}")
    
    await conn.execute('SET search_path TO public')
    return True

async def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env file")
        return
    
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        if not schools:
            print("No schools found in public.schools. Has super admin created any?")
            return
        
        for school in schools:
            await repair_tenant(conn, school['subdomain'])
    
    await pool.close()
    print("\n✨ All tenants repaired successfully!")
    print("\n📌 Next steps:")
    print("   1. Restart your uvicorn server (Ctrl+C then `uvicorn app.main:app --reload`)")
    print("   2. Clear your browser cache or open an incognito window")
    print("   3. Login as school admin at http://<school-subdomain>.localhost:8000/login")
    print("   4. You should now have full access to all pages.")

if __name__ == "__main__":
    asyncio.run(main())
