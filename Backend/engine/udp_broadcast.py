import asyncio
import logging
import socket

from .protocol import create_message

logger = logging.getLogger(__name__)


class UdpBroadcaster:
    def __init__(self):
        self._sock: socket.socket | None = None

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        logger.info("UDP broadcaster started")

    def stop(self):
        if self._sock:
            self._sock.close()
            self._sock = None
        logger.info("UDP broadcaster stopped")

    async def broadcast_gifts(
        self,
        frontends: list[dict],
        gifts: list[dict],
    ):
        """Send new_gifts message to all registered frontends."""
        if not frontends or not gifts:
            return

        loop = asyncio.get_event_loop()

        for fe in frontends:
            host = fe.get("udp_host")
            port = fe.get("udp_port")
            license_key = fe.get("license_key")
            if not host or not port or not license_key:
                continue

            try:
                msg = create_message(license_key, "new_gifts", {"gifts": gifts})
                await loop.sock_sendto(self._sock, msg, (host, port))
                logger.debug(
                    "Sent %d gifts to %s:%d (key=%s...)",
                    len(gifts), host, port, license_key[:8],
                )
            except Exception as e:
                logger.warning(
                    "Failed to send to %s:%d: %s", host, port, e
                )
