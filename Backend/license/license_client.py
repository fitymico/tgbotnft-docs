import asyncio
import hashlib
import logging
import os
import platform
import socket
import ssl
import uuid

import aiohttp

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 3600  # 1 hour
MAX_HEARTBEAT_RETRIES = 3


def _generate_instance_id() -> str:
    try:
        import netifaces
        ifaces = netifaces.interfaces()
        mac = ""
        for iface in ifaces:
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_LINK in addrs:
                for a in addrs[netifaces.AF_LINK]:
                    m = a.get("addr", "")
                    if m and m != "00:00:00:00:00:00":
                        mac = m
                        break
            if mac:
                break
    except ImportError:
        mac = hex(uuid.getnode())[2:]

    data = f"{mac}-{socket.gethostname()}-{platform.system()}-{platform.machine()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


class LicenseClient:
    def __init__(self, server_url: str):
        self._server_url = server_url.rstrip("/")
        self._sessions: dict[str, str] = {}  # license_key -> session_token
        self._task: asyncio.Task | None = None
        self._running = False
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("LicenseClient started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        for lk in list(self._sessions):
            await self.deactivate(lk)
        logger.info("LicenseClient stopped")

    async def activate(self, license_key: str) -> bool:
        instance_id = _generate_instance_id()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._server_url}/api/activate",
                    json={"license_key": license_key, "instance_id": instance_id},
                    ssl=self._ssl_ctx,
                ) as resp:
                    if resp.status != 200:
                        data = await resp.json()
                        logger.error("License activate failed: %s", data.get("detail", resp.status))
                        return False
                    data = await resp.json()
                    if data.get("success") and data.get("session_token"):
                        self._sessions[license_key] = data["session_token"]
                        logger.info("License %s activated", license_key[:8])
                        return True
                    return False
        except Exception as e:
            logger.error("License activate error: %s", e)
            return False

    async def heartbeat(self, license_key: str) -> bool:
        token = self._sessions.get(license_key)
        if not token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._server_url}/api/heartbeat",
                    json={"session_token": token},
                    ssl=self._ssl_ctx,
                ) as resp:
                    if resp.status != 200:
                        logger.warning("Heartbeat failed for %s", license_key[:8])
                        return False
                    logger.info("Heartbeat OK for %s", license_key[:8])
                    return True
        except Exception as e:
            logger.error("Heartbeat error: %s", e)
            return False

    async def deactivate(self, license_key: str):
        token = self._sessions.pop(license_key, None)
        if not token:
            return
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self._server_url}/api/deactivate",
                    json={"session_token": token},
                    ssl=self._ssl_ctx,
                )
            logger.info("License %s deactivated", license_key[:8])
        except Exception:
            pass

    async def _heartbeat_loop(self):
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            for lk in list(self._sessions):
                success = False
                for attempt in range(1, MAX_HEARTBEAT_RETRIES + 1):
                    success = await self.heartbeat(lk)
                    if success:
                        break
                    logger.warning("Heartbeat attempt %d/%d failed for %s", attempt, MAX_HEARTBEAT_RETRIES, lk[:8])
                    if attempt < MAX_HEARTBEAT_RETRIES:
                        await asyncio.sleep(5 * attempt)
                if not success:
                    logger.error("License %s invalid after %d retries", lk[:8], MAX_HEARTBEAT_RETRIES)
                    self._sessions.pop(lk, None)
