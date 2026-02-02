from aiohttp import web


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path.startswith("/internal/"):
        secret = request.headers.get("X-Internal-Secret", "")
        expected = request.app.get("internal_secret", "")
        if not expected or secret != expected:
            raise web.HTTPUnauthorized(
                text='{"error":"Invalid internal secret"}',
                content_type="application/json",
            )
    return await handler(request)
