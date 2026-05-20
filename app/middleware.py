from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import get_pool, tenant_exists

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static"):
            request.state.tenant = None
            return await call_next(request)

        host = request.headers.get("host", "")
        host = host.split(":")[0]
        parts = host.split(".")
        if len(parts) >= 2:
            subdomain = parts[0]
            if await tenant_exists(subdomain):
                request.state.tenant = subdomain
                pool = await get_pool()
                conn = await pool.acquire()
                await conn.execute(f'SET search_path TO "{subdomain}"')
                request.state.db_conn = conn
                response = await call_next(request)
                await conn.execute('SET search_path TO public')
                await pool.release(conn)
                return response
        raise HTTPException(status_code=404, detail="School not found")
