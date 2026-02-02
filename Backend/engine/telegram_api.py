import asyncio
import logging

from telethon import TelegramClient

logger = logging.getLogger(__name__)


async def _retry(fn, attempts: int = 3, base_delay: float = 0.5):
    last_err = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last_err = e
            delay = base_delay * (2 ** i)
            logger.warning("Retry %d/%d failed: %s", i + 1, attempts, e)
            await asyncio.sleep(delay)
    raise last_err


async def get_star_gifts(client: TelegramClient) -> list[dict]:
    from telethon.tl import functions as tl_functions
    from telethon import _tl as Api

    async def _call():
        Ctor = getattr(getattr(Api, "payments", None), "GetStarGiftsRequest", None)
        if Ctor is None:
            Ctor = getattr(getattr(tl_functions, "payments", None), "GetStarGiftsRequest", None)
        if Ctor is None:
            try:
                from telethon.tl.functions.payments import GetStarGiftsRequest as Ctor2
                Ctor = Ctor2
            except ImportError:
                pass
        if Ctor is None:
            raise ImportError("GetStarGiftsRequest not found in Telethon")

        res = await client(Ctor())
        gifts_raw = getattr(res, "gifts", None)
        if gifts_raw is None and isinstance(res, (list, tuple)):
            gifts_raw = res
        if gifts_raw is None:
            return []

        result = []
        for g in gifts_raw:
            gid = _to_str(getattr(g, "id", None))
            stars = _to_int(getattr(g, "stars", 0))
            avail = getattr(g, "availability_remains", None)
            if avail is None:
                avail = getattr(g, "availabilityRemains", None)
            result.append({
                "id": gid,
                "stars": stars,
                "availability_remains": _to_int_or_none(avail),
            })
        return result

    return await _retry(_call)


def _to_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, int):
        return str(val)
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


def _to_int(val) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        return int(val) if val.isdigit() else 0
    if hasattr(val, "value"):
        return int(val.value)
    return int(val)


def _to_int_or_none(val):
    if val is None:
        return None
    return _to_int(val)
