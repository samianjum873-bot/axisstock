import os

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import get_pool, tenant_exists

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Automatic device detection based on user-agent
        # Only phone-like devices should use mobile UI. Tablets and desktops use desktop UI.
        ua = request.headers.get("user-agent", "").lower()
        is_mobile = (
            "iphone" in ua
            or "ipod" in ua
            or ("android" in ua and "mobile" in ua)
        )
        request.state.is_mobile = is_mobile

        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static") or request.url.path == "/favicon.ico":
            request.state.tenant = None
            return await call_next(request)

        db_configured = os.getenv("DATABASE_URL") is not None
        if not db_configured:
            request.state.tenant = "demo"
            request.state.is_subuser_domain = False
            request.state.db_conn = None
            return await call_next(request)

        host = request.headers.get("host", "").split(":")[0].strip().lower()
        # Detect local host / IP addresses and use demo tenant for local UI testing
        if host in {"localhost", "0.0.0.0"} or host.startswith("127.") or host == "::1":
            tenant = "demo"
            request.state.is_subuser_domain = False
        else:
            is_subuser = ".subuser." in host
            if is_subuser:
                subdomain = host.split(".subuser.")[0]
            else:
                parts = host.split(".") if host else []
                subdomain = parts[0] if len(parts) >= 2 else None

            if subdomain and await tenant_exists(subdomain):
                tenant = subdomain
                request.state.is_subuser_domain = is_subuser
            else:
                raise HTTPException(status_code=404, detail="School not found")

        request.state.tenant = tenant
        pool = await get_pool()
        conn = await pool.acquire()
        await conn.execute(f'SET search_path TO "{tenant}"')
        request.state.db_conn = conn
        response = await call_next(request)
        await conn.execute('SET search_path TO public')
        await pool.release(conn)
        return response
