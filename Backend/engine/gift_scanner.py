import asyncio
import logging

from telethon import TelegramClient
from telethon.sessions import StringSession

from .telegram_api import get_star_gifts
from .udp_broadcast import UdpBroadcaster

logger = logging.getLogger(__name__)


class GiftScanner:
    def __init__(
        self,
        db,
        broadcaster: UdpBroadcaster,
        api_id: int,
        api_hash: str,
        session_string: str,
        scan_interval: float = 1.0,
    ):
        self._db = db
        self._broadcaster = broadcaster
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_string = session_string
        self._scan_interval = scan_interval
        self._client: TelegramClient | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        self._client = TelegramClient(
            StringSession(self._session_string),
            self._api_id,
            self._api_hash,
            connection_retries=5,
        )
        await self._client.connect()
        logger.info("Scanner Telethon client connected")

        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("GiftScanner started (interval=%.1fs)", self._scan_interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        logger.info("GiftScanner stopped")

    async def _loop(self):
        while self._running:
            try:
                await self._scan_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scanner loop error: %s", e)
            await asyncio.sleep(self._scan_interval)

    async def _scan_cycle(self):
        all_gifts = await get_star_gifts(self._client)
        if not all_gifts:
            return

        seen = await self._db.get_seen_gift_ids()

        new_gifts = [g for g in all_gifts if g["id"] and g["id"] not in seen]
        if not new_gifts:
            return

        # Mark unavailable gifts as seen immediately
        unavailable = [
            g for g in new_gifts
            if g["availability_remains"] is None or g["availability_remains"] == 0
        ]
        available = [
            g for g in new_gifts
            if g["availability_remains"] is not None and g["availability_remains"] > 0
        ]

        all_new_ids = [g["id"] for g in new_gifts]
        await self._db.add_seen_gifts(all_new_ids)

        if not available:
            return

        # Broadcast available new gifts to all frontends
        frontends = await self._db.get_all_frontends_with_address()
        if not frontends:
            logger.debug("No frontends registered, skipping broadcast")
            return

        logger.info(
            "Broadcasting %d new gifts to %d frontends",
            len(available), len(frontends),
        )
        await self._broadcaster.broadcast_gifts(frontends, available)
