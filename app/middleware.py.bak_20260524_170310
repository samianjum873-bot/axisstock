from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import get_pool, tenant_exists

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static") or request.url.path == "/favicon.ico":
            request.state.tenant = None
            return await call_next(request)

        host = request.headers.get("host", "")
        host = host.split(":")[0]
        # Detect subuser domain: school.subuser.localhost
        is_subuser = ".subuser." in host
        if is_subuser:
            subdomain = host.split(".subuser.")[0]
        else:
            parts = host.split(".")
            subdomain = parts[0] if len(parts) >= 2 else None
        if subdomain and await tenant_exists(subdomain):
            request.state.tenant = subdomain
            request.state.is_subuser_domain = is_subuser
            pool = await get_pool()
            conn = await pool.acquire()
            await conn.execute(f'SET search_path TO "{subdomain}"')
            request.state.db_conn = conn
            response = await call_next(request)
            await conn.execute('SET search_path TO public')
            await pool.release(conn)
            return response
        raise HTTPException(status_code=404, detail="School not found")
