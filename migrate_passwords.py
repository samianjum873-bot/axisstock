import asyncio
import bcrypt
from app.database import get_pool

async def migrate_tenants():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get all existing school subdomains
        schools = await conn.fetch("SELECT subdomain FROM public.schools")
        for school in schools:
            sub = school['subdomain']
            print(f"Migrating schema: {sub}")
            await conn.execute(f'SET search_path TO "{sub}"')
            
            # Check if password_hash column already exists
            col_check = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='password_hash'
                )
            """)
            
            if not col_check:
                # Add password_hash column
                await conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                print(f"  Added password_hash column to {sub}.users")
                
                # If old password column exists, copy and hash the passwords
                has_old = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='users' AND column_name='password'
                    )
                """)
                if has_old:
                    rows = await conn.fetch("SELECT id, password FROM users WHERE password IS NOT NULL")
                    for row in rows:
                        hashed = bcrypt.hashpw(row['password'].encode(), bcrypt.gensalt()).decode()
                        await conn.execute(
                            "UPDATE users SET password_hash = $1 WHERE id = $2",
                            hashed, row['id']
                        )
                    print(f"  Migrated {len(rows)} passwords in {sub}")
                    # Drop the old password column
                    await conn.execute("ALTER TABLE users DROP COLUMN password")
                    print(f"  Dropped old password column from {sub}")
            else:
                print(f"  password_hash already exists in {sub}, skipping")
            
            await conn.execute('SET search_path TO public')
    print("Migration completed successfully.")

if __name__ == "__main__":
    asyncio.run(migrate_tenants())
