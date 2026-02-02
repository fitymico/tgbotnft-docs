import logging

from aiohttp import web

from config import (
    HOST, PORT, SERVER_API_ID, SERVER_API_HASH, SERVER_SESSION_STRING,
    LICENSE_SERVER_URL, INTERNAL_API_SECRET, DB_PATH, SCAN_INTERVAL,
)
from db.database import Database
from engine.gift_scanner import GiftScanner
from engine.udp_broadcast import UdpBroadcaster
from license.license_client import LicenseClient
from api.middleware import auth_middleware
from api.internal_routes import setup_internal_routes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def on_startup(app: web.Application):
    db = Database(DB_PATH)
    await db.connect()

    broadcaster = UdpBroadcaster()
    broadcaster.start()

    license_client = LicenseClient(LICENSE_SERVER_URL)
    await license_client.start()

    scanner = GiftScanner(
        db=db,
        broadcaster=broadcaster,
        api_id=SERVER_API_ID,
        api_hash=SERVER_API_HASH,
        session_string=SERVER_SESSION_STRING,
        scan_interval=SCAN_INTERVAL,
    )
    await scanner.start()

    app["db"] = db
    app["broadcaster"] = broadcaster
    app["license_client"] = license_client
    app["scanner"] = scanner
    app["internal_secret"] = INTERNAL_API_SECRET

    logger.info("Backend started on %s:%d", HOST, PORT)


async def on_cleanup(app: web.Application):
    await app["scanner"].stop()
    app["broadcaster"].stop()
    await app["license_client"].stop()
    await app["db"].close()
    logger.info("Backend stopped")


def create_app() -> web.Application:
    app = web.Application(middlewares=[auth_middleware])

    setup_internal_routes(app)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host=HOST, port=PORT)
