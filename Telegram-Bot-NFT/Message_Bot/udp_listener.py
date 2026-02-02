import asyncio
import logging

from .protocol import parse_message

logger = logging.getLogger(__name__)


class UdpListener:
    """Listens for UDP messages from Backend (new gift notifications)."""

    def __init__(self, license_key: str, host: str, port: int):
        self._license_key = license_key
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _UdpProtocol | None = None
        self._callback = None

    def on_gifts(self, callback):
        """Register callback: callback(gifts: list[dict])"""
        self._callback = callback

    async def start(self):
        loop = asyncio.get_event_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: _UdpProtocol(self._license_key, self._callback),
            local_addr=(self._host, self._port),
        )
        logger.info("UDP listener started on %s:%d", self._host, self._port)

    def stop(self):
        if self._transport:
            self._transport.close()
            self._transport = None
        logger.info("UDP listener stopped")


class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, license_key: str, callback):
        self._license_key = license_key
        self._callback = callback

    def datagram_received(self, data: bytes, addr: tuple):
        msg = parse_message(self._license_key, data)
        if msg is None:
            logger.warning("Invalid UDP message from %s", addr)
            return

        action = msg.get("a")
        if action == "new_gifts" and self._callback:
            gifts = msg.get("d", {}).get("gifts", [])
            if gifts:
                asyncio.get_event_loop().create_task(self._callback(gifts))

    def error_received(self, exc):
        logger.error("UDP error: %s", exc)
