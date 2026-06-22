from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import get_pool, tenant_exists

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Mobile detection (basic user-agent sniffing) - DO THIS FIRST, BEFORE EARLY RETURNS
        ua = request.headers.get("user-agent", "").lower()
        is_mobile = any(k in ua for k in ["mobile", "android", "iphone", "ipad", "ipod", "phone", "mobi"]) 

        # Allow forcing mobile view for testing/dev via query param, cookie, or header
        try:
            mobile_param = request.query_params.get("mobile")
            if mobile_param == "1":
                is_mobile = True
        except Exception:
            pass
        if request.cookies.get("force_mobile") == "1":
            is_mobile = True
        if request.headers.get("x-force-mobile") == "1":
            is_mobile = True

        request.state.is_mobile = is_mobile

        if request.url.path.startswith("/super-admin") or request.url.path.startswith("/static") or request.url.path == "/favicon.ico" or request.url.path == "/login":
            request.state.tenant = None
            return await call_next(request)

        # If mobile rendering was explicitly forced (query/cookie/header),
        # skip tenant DB lookup so pages like `/login` can render during dev/testing
        forced = False
        try:
            if request.query_params.get("mobile") == "1":
                forced = True
        except Exception:
            pass
        if request.cookies.get("force_mobile") == "1":
            forced = True
        if request.headers.get("x-force-mobile") == "1":
            forced = True
        if forced:
            request.state.tenant = "demo"
            request.state.is_subuser_domain = False
            request.state.db_conn = None
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
