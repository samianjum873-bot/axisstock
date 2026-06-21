import asyncio
import os
from app.database import get_pool, create_tenant_schema

async def seed_public_schema():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create demo school if not exists
        demo = await conn.fetchval("SELECT 1 FROM public.schools WHERE subdomain = 'demo'")
        if not demo:
            await conn.execute(
                "INSERT INTO public.schools (name, subdomain, admin_username, admin_password) VALUES ($1,$2,$3,$4)",
                "Demo School", "demo", "admin", "admin"
            )
            await create_tenant_schema("demo", "admin", "admin")
            print("Demo school created")
        else:
            print("Demo school already exists")

if __name__ == "__main__":
    asyncio.run(seed_public_schema())
