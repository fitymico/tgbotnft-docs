from pathlib import Path

import aiosqlite


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()
        await self._db.executescript(schema)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    # ── frontends ──

    async def register_frontend(self, license_key: str, telegram_id: int | None = None) -> dict:
        await self._db.execute(
            "INSERT OR IGNORE INTO frontends (license_key, telegram_id) VALUES (?, ?)",
            (license_key, telegram_id),
        )
        if telegram_id is not None:
            await self._db.execute(
                "UPDATE frontends SET telegram_id = ? WHERE license_key = ?",
                (telegram_id, license_key),
            )
        await self._db.commit()
        return await self.get_frontend(license_key)

    async def get_frontend(self, license_key: str) -> dict | None:
        cur = await self._db.execute(
            "SELECT * FROM frontends WHERE license_key = ?", (license_key,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def set_frontend_address(self, license_key: str, udp_host: str, udp_port: int):
        await self._db.execute(
            "UPDATE frontends SET udp_host = ?, udp_port = ? WHERE license_key = ?",
            (udp_host, udp_port, license_key),
        )
        await self._db.commit()

    async def get_all_frontends_with_address(self) -> list[dict]:
        cur = await self._db.execute(
            "SELECT * FROM frontends WHERE udp_host IS NOT NULL AND udp_port IS NOT NULL"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def delete_frontend(self, license_key: str):
        await self._db.execute(
            "DELETE FROM frontends WHERE license_key = ?", (license_key,)
        )
        await self._db.commit()

    # ── seen_gifts ──

    async def get_seen_gift_ids(self) -> set[str]:
        cur = await self._db.execute("SELECT gift_id FROM seen_gifts")
        rows = await cur.fetchall()
        return {r["gift_id"] for r in rows}

    async def add_seen_gifts(self, gift_ids: list[str]):
        if not gift_ids:
            return
        await self._db.executemany(
            "INSERT OR IGNORE INTO seen_gifts (gift_id) VALUES (?)",
            [(gid,) for gid in gift_ids],
        )
        await self._db.commit()
