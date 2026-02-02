import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from .distribution import parse_distribution, PurchaseRule
from .telegram_api import get_stars_balance, pay_star_gift

logger = logging.getLogger(__name__)


class GiftBuyer:
    """Receives new gift notifications and purchases based on distribution rules."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_string: str,
        status_file: str,
        log_file: str,
    ):
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_string = session_string
        self._status_file = status_file
        self._log_file = log_file
        self._client: TelegramClient | None = None
        self._peer = None
        self._lock = asyncio.Lock()

    async def connect(self):
        self._client = TelegramClient(
            StringSession(self._session_string),
            self._api_id,
            self._api_hash,
            connection_retries=5,
        )
        await self._client.connect()
        me = await self._client.get_me()
        self._peer = await self._client.get_input_entity(me)
        logger.info("GiftBuyer Telethon client connected")

    async def disconnect(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        logger.info("GiftBuyer disconnected")

    def read_status(self) -> dict:
        try:
            with open(self._status_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def write_status(self, data: dict):
        os.makedirs(os.path.dirname(self._status_file), exist_ok=True)
        tmp = self._status_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._status_file)

    def _append_log(self, line: str):
        os.makedirs(os.path.dirname(self._log_file), exist_ok=True)
        with open(self._log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {line}\n")

    async def handle_new_gifts(self, gifts: list[dict]):
        """Called by UDP listener when Backend broadcasts new gifts."""
        async with self._lock:
            status = self.read_status()
            if not status.get("isActive"):
                return

            distribution_text = status.get("distribution", "")
            if not distribution_text:
                return

            rules = parse_distribution(distribution_text)
            if not rules:
                return

            if not self._client or not self._client.is_connected():
                logger.warning("Telethon client not connected, skipping gifts")
                return

            try:
                stars = await get_stars_balance(self._client)
            except Exception as e:
                logger.error("Failed to get balance: %s", e)
                return

            if stars <= 0:
                return

            # Build range counters
            range_counters: dict[str, dict] = {}
            for rule in rules:
                range_key = f"{rule.min}-{rule.max}"
                range_counters[range_key] = {"rule": rule, "bought": 0}

            # Filter and sort gifts
            available = [
                g for g in gifts
                if g.get("id") and g.get("availability_remains") and g["availability_remains"] > 0
            ]
            available.sort(key=lambda g: g.get("stars", 0), reverse=True)

            for gift in available:
                gid = str(gift["id"])
                gift_stars = gift.get("stars", 0)
                gift_avail = gift.get("availability_remains", 0)

                applicable_rules = []
                for rule in rules:
                    range_key = f"{rule.min}-{rule.max}"
                    counter = range_counters.get(range_key)
                    if not counter:
                        continue
                    if gift_stars >= rule.min and gift_stars <= rule.max and counter["bought"] < rule.count:
                        applicable_rules.append({"rule": rule, "range_key": range_key})

                if not applicable_rules:
                    continue

                while gift_avail > 0 and stars >= gift_stars:
                    active_rules = [
                        ar for ar in applicable_rules
                        if range_counters[ar["range_key"]]["bought"] < ar["rule"].count
                    ]
                    if not active_rules:
                        break

                    try:
                        result = await pay_star_gift(
                            self._client,
                            int(gid),
                            self._peer,
                            message=None,
                            hide_name=True,
                            include_upgrade=False,
                        )
                    except Exception as e:
                        logger.error("pay_star_gift(%s) failed: %s", gid, e)
                        break

                    if not result:
                        logger.warning("pay_star_gift(%s) returned empty", gid)
                        break

                    stars -= gift_stars
                    gift_avail -= 1

                    for ar in active_rules:
                        range_counters[ar["range_key"]]["bought"] += 1

                    range_info = ", ".join(
                        f"{ar['range_key']} ({range_counters[ar['range_key']]['bought']}/{ar['rule'].count})"
                        for ar in active_rules
                    )
                    log_line = f"Bought gift {gid}, cost {gift_stars} stars, balance {stars}. Ranges: {range_info}"
                    logger.info(log_line)
                    self._append_log(log_line)

                    await asyncio.sleep(0.2)
