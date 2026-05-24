import re

with open("app/main.py", "r") as f:
    content = f.read()

# Add middleware after session middleware if not already present
middleware_code = '''
# Middleware to inject user_permissions into template context
from starlette.middleware.base import BaseHTTPMiddleware
class PermissionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.session.get("user"):
            perms = await get_user_permissions(request)
            request.state.user_permissions = perms
        else:
            request.state.user_permissions = set()
        response = await call_next(request)
        # If response is a TemplateResponse, add user_permissions to its context
        if hasattr(response, "context") and isinstance(response.context, dict):
            response.context["user_permissions"] = request.state.user_permissions
        return response

app.add_middleware(PermissionMiddleware)
'''

if "PermissionMiddleware" not in content:
    # Insert after the existing middleware line
    session_line = 'app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key-in-production")'
    if session_line in content:
        content = content.replace(session_line, session_line + "\n" + middleware_code)
        with open("app/main.py", "w") as f:
            f.write(content)
        print("✅ Middleware added to main.py")
    else:
        print("⚠️ Could not find session middleware line")
else:
    print("✅ Middleware already present")
