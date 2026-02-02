from aiohttp import web


def setup_internal_routes(app: web.Application):
    app.router.add_post("/internal/register", handle_register)
    app.router.add_post("/internal/set_address", handle_set_address)
    app.router.add_post("/internal/delete", handle_delete)
    app.router.add_get("/internal/user/{license_key}", handle_user_info)


async def handle_register(request: web.Request) -> web.Response:
    data = await request.json()
    license_key = data.get("license_key", "")
    telegram_id = data.get("telegram_id")

    if not license_key:
        return web.json_response({"error": "license_key is required"}, status=400)

    db = request.app["db"]
    fe = await db.register_frontend(license_key, telegram_id)
    return web.json_response({"ok": True, "id": fe["id"]})


async def handle_set_address(request: web.Request) -> web.Response:
    data = await request.json()
    license_key = data.get("license_key", "")
    udp_host = data.get("udp_host", "")
    udp_port = data.get("udp_port", 0)

    if not license_key or not udp_host or not udp_port:
        return web.json_response(
            {"error": "license_key, udp_host, and udp_port are required"}, status=400
        )

    db = request.app["db"]
    fe = await db.get_frontend(license_key)
    if not fe:
        return web.json_response({"error": "Frontend not found"}, status=404)

    await db.set_frontend_address(license_key, udp_host, int(udp_port))
    return web.json_response({"ok": True})


async def handle_delete(request: web.Request) -> web.Response:
    data = await request.json()
    license_key = data.get("license_key", "")

    if not license_key:
        return web.json_response({"error": "license_key is required"}, status=400)

    db = request.app["db"]
    await db.delete_frontend(license_key)
    return web.json_response({"ok": True})


async def handle_user_info(request: web.Request) -> web.Response:
    license_key = request.match_info["license_key"]
    db = request.app["db"]
    fe = await db.get_frontend(license_key)
    if not fe:
        return web.json_response({"error": "Frontend not found"}, status=404)

    return web.json_response({
        "id": fe["id"],
        "license_key": fe["license_key"],
        "telegram_id": fe["telegram_id"],
        "udp_host": fe["udp_host"],
        "udp_port": fe["udp_port"],
        "registered_at": fe["registered_at"],
    })
