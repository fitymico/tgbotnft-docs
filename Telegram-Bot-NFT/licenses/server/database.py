"""
Database module для License Server
SQLite + Pydantic models
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
import sqlite3

@dataclass
class License:
    license_key: str
    expires_at: datetime
    max_instances: int = 1
    note: str = ""
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Instance:
    license_id: int
    instance_id: str
    session_token: str
    ip_address: str = ""
    id: Optional[int] = None
    last_heartbeat: datetime = field(default_factory=datetime.now)
    is_active: bool = True

class Database:
    def __init__(self, db_path: str = "licenses.db"):
        self.db_path = db_path
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Инициализация таблиц"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                max_instances INTEGER DEFAULT 1,
                note TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_id INTEGER REFERENCES licenses(id) ON DELETE CASCADE,
                instance_id TEXT UNIQUE NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                ip_address TEXT DEFAULT '',
                last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ==================== Licenses ====================
    
    def create_license(self, license: License) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO licenses (license_key, expires_at, max_instances, note)
            VALUES (?, ?, ?, ?)
        """, (license.license_key, license.expires_at, license.max_instances, license.note))
        license_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return license_id
    
    def get_license_by_key(self, license_key: str) -> Optional[License]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return License(
                id=row["id"],
                license_key=row["license_key"],
                expires_at=datetime.fromisoformat(row["expires_at"]),
                max_instances=row["max_instances"],
                note=row["note"] or "",
                created_at=datetime.fromisoformat(row["created_at"])
            )
        return None
    
    def get_license_by_id(self, license_id: int) -> Optional[License]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM licenses WHERE id = ?", (license_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return License(
                id=row["id"],
                license_key=row["license_key"],
                expires_at=datetime.fromisoformat(row["expires_at"]),
                max_instances=row["max_instances"],
                note=row["note"] or "",
                created_at=datetime.fromisoformat(row["created_at"])
            )
        return None
    
    def get_all_licenses(self) -> List[dict]:
        """Получить все лицензии с информацией об экземплярах"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM licenses ORDER BY created_at DESC")
        licenses = []
        for row in cursor.fetchall():
            lic = dict(row)
            lic["expires_at"] = datetime.fromisoformat(lic["expires_at"])
            lic["created_at"] = datetime.fromisoformat(lic["created_at"])
            # Получаем экземпляры
            cursor.execute("""
                SELECT * FROM instances 
                WHERE license_id = ? 
                ORDER BY last_heartbeat DESC
            """, (lic["id"],))
            instances = []
            for inst_row in cursor.fetchall():
                inst = dict(inst_row)
                inst["last_heartbeat"] = datetime.fromisoformat(inst["last_heartbeat"])
                instances.append(inst)
            lic["instances"] = instances
            lic["active_count"] = sum(1 for i in instances if i["is_active"])
            licenses.append(lic)
        conn.close()
        return licenses
    
    def update_license_expiry(self, license_id: int, new_expires: datetime):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE licenses SET expires_at = ? WHERE id = ?",
            (new_expires, license_id)
        )
        conn.commit()
        conn.close()
    
    def delete_license(self, license_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM instances WHERE license_id = ?", (license_id,))
        cursor.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
        conn.commit()
        conn.close()
    
    # ==================== Instances ====================
    
    def create_instance(self, instance: Instance) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO instances (license_id, instance_id, session_token, ip_address)
            VALUES (?, ?, ?, ?)
        """, (instance.license_id, instance.instance_id, instance.session_token, instance.ip_address))
        instance_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return instance_id
    
    def get_instance_by_token(self, session_token: str) -> Optional[Instance]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM instances WHERE session_token = ?", (session_token,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Instance(
                id=row["id"],
                license_id=row["license_id"],
                instance_id=row["instance_id"],
                session_token=row["session_token"],
                ip_address=row["ip_address"],
                last_heartbeat=datetime.fromisoformat(row["last_heartbeat"]),
                is_active=bool(row["is_active"])
            )
        return None
    
    def get_instance_by_instance_id(self, instance_id: str) -> Optional[Instance]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM instances WHERE instance_id = ?", (instance_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Instance(
                id=row["id"],
                license_id=row["license_id"],
                instance_id=row["instance_id"],
                session_token=row["session_token"],
                ip_address=row["ip_address"],
                last_heartbeat=datetime.fromisoformat(row["last_heartbeat"]),
                is_active=bool(row["is_active"])
            )
        return None
    
    def get_active_instances(self, license_id: int) -> List[Instance]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM instances WHERE license_id = ? AND is_active = 1",
            (license_id,)
        )
        instances = []
        for row in cursor.fetchall():
            instances.append(Instance(
                id=row["id"],
                license_id=row["license_id"],
                instance_id=row["instance_id"],
                session_token=row["session_token"],
                ip_address=row["ip_address"],
                last_heartbeat=datetime.fromisoformat(row["last_heartbeat"]),
                is_active=bool(row["is_active"])
            ))
        conn.close()
        return instances
    
    def update_heartbeat(self, session_token: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE instances SET last_heartbeat = ? WHERE session_token = ?",
            (datetime.now(), session_token)
        )
        conn.commit()
        conn.close()
    
    def deactivate_instance(self, session_token: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE instances SET is_active = 0 WHERE session_token = ?",
            (session_token,)
        )
        conn.commit()
        conn.close()
    
    def deactivate_instance_by_id(self, instance_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE instances SET is_active = 0 WHERE id = ?",
            (instance_id,)
        )
        conn.commit()
        conn.close()
