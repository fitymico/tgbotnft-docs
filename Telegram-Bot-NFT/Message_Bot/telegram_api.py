import asyncio
import logging

from telethon import TelegramClient
from telethon.tl import types as tl_types

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


async def get_stars_balance(client: TelegramClient) -> int:
    from telethon.tl.functions.payments import GetStarsStatusRequest

    try:
        res = await client(GetStarsStatusRequest(peer=tl_types.InputPeerSelf()))
        return _extract_balance(res)
    except Exception:
        try:
            me = await client.get_me()
            peer = await client.get_input_entity(me)
            res = await client(GetStarsStatusRequest(peer=peer))
            return _extract_balance(res)
        except Exception as e:
            logger.error("get_stars_balance failed: %s", e)
            return 0


def _extract_balance(res) -> int:
    balance = getattr(res, "balance", None)
    if balance is None:
        return 0
    amount = getattr(balance, "amount", balance)
    val = getattr(amount, "value", amount)
    return int(val)


async def pay_star_gift(
    client: TelegramClient,
    gift_id: int,
    peer,
    message: str | None = None,
    hide_name: bool = True,
    include_upgrade: bool = False,
):
    from telethon import _tl as Api

    InputInvoiceStarGift = getattr(Api, "InputInvoiceStarGift", None)
    if InputInvoiceStarGift is None:
        try:
            from telethon.tl.types import InputInvoiceStarGift
        except ImportError:
            raise ImportError("InputInvoiceStarGift not found in Telethon")

    GetPaymentForm = getattr(getattr(Api, "payments", None), "GetPaymentFormRequest", None)
    if GetPaymentForm is None:
        try:
            from telethon.tl.functions.payments import GetPaymentFormRequest as GetPaymentForm
        except ImportError:
            raise ImportError("GetPaymentFormRequest not found in Telethon")

    SendStarsForm = getattr(getattr(Api, "payments", None), "SendStarsFormRequest", None)
    if SendStarsForm is None:
        try:
            from telethon.tl.functions.payments import SendStarsFormRequest as SendStarsForm
        except ImportError:
            raise ImportError("SendStarsFormRequest not found in Telethon")

    invoice_params = {
        "gift_id": gift_id,
        "peer": peer,
        "hide_name": hide_name,
        "include_upgrade": include_upgrade,
    }
    if message:
        TextWithEntities = getattr(Api, "TextWithEntities", None)
        if TextWithEntities is None:
            from telethon.tl.types import TextWithEntities
        invoice_params["message"] = TextWithEntities(text=message, entities=[])

    invoice = InputInvoiceStarGift(**invoice_params)

    payment_form = await client(GetPaymentForm(invoice=invoice))
    result = await client(SendStarsForm(
        form_id=payment_form.form_id,
        invoice=invoice,
    ))
    return result
