import hashlib
import hmac
import json
import os
import time

MAGIC = b"NFTB"
MAX_TS_DRIFT = 120  # seconds


def _derive_key(license_key: str) -> bytes:
    return hashlib.sha256(license_key.encode()).digest()


def create_message(license_key: str, action: str, data: dict | None = None) -> bytes:
    if data is None:
        data = {}
    nonce = os.urandom(16).hex()
    ts = int(time.time())
    payload_dict = {
        "a": action,
        "d": data,
        "n": nonce,
        "ts": ts,
    }
    payload = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode()
    key = _derive_key(license_key)
    mac = hmac.new(key, payload, hashlib.sha256).digest()
    return MAGIC + mac + payload


def parse_message(license_key: str, raw: bytes) -> dict | None:
    if len(raw) < 4 + 32:
        return None
    if raw[:4] != MAGIC:
        return None
    received_mac = raw[4:36]
    payload = raw[36:]
    key = _derive_key(license_key)
    expected_mac = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(received_mac, expected_mac):
        return None
    try:
        msg = json.loads(payload)
    except json.JSONDecodeError:
        return None
    ts = msg.get("ts", 0)
    if abs(time.time() - ts) > MAX_TS_DRIFT:
        return None
    return msg
