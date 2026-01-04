#!/usr/bin/env python3
"""
CLI для создания лицензий (интерактивный режим)
"""
import sys
import os
import sqlite3
import secrets
import argparse
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "licenses.db")

def generate_license_key() -> str:
    """Генерация ключа лицензии в формате GIFT-XXXX-XXXX-XXXX-XXXX"""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    parts = []
    for _ in range(4):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return f"GIFT-{'-'.join(parts)}"

def key_exists(conn: sqlite3.Connection, key: str) -> bool:
    """Проверка существования ключа в БД"""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM licenses WHERE license_key = ?", (key,))
    return cursor.fetchone() is not None

def init_db(conn: sqlite3.Connection):
    """Инициализация таблиц если их нет"""
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

def create_license(days: int, max_instances: int, note: str) -> tuple:
    """Создание новой лицензии"""
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    
    # Генерируем уникальный ключ
    max_attempts = 100
    for _ in range(max_attempts):
        license_key = generate_license_key()
        if not key_exists(conn, license_key):
            break
    else:
        conn.close()
        raise RuntimeError("Не удалось сгенерировать уникальный ключ после 100 попыток")
    
    expires_at = datetime.now() + timedelta(days=days)
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO licenses (license_key, expires_at, max_instances, note)
        VALUES (?, ?, ?, ?)
    """, (license_key, expires_at, max_instances, note))
    
    conn.commit()
    conn.close()
    
    return license_key, expires_at

def list_licenses():
    """Список всех лицензий"""
    if not os.path.exists(DB_PATH):
        print("База данных не найдена. Создайте первую лицензию.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, license_key, expires_at, max_instances, note, created_at 
        FROM licenses 
        ORDER BY created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("Лицензий нет.")
        return
    
    now = datetime.now()
    print("\n" + "=" * 90)
    print(f"{'ID':>4} | {'Ключ лицензии':<25} | {'Истекает':<20} | {'Экз':>3} | {'Статус':<12} | Заметка")
    print("=" * 90)
    
    for row in rows:
        id_, key, expires, max_inst, note, created = row
        expires_dt = datetime.fromisoformat(expires)
        days_left = (expires_dt - now).days
        
        if days_left < 0:
            status = "❌ ИСТЕКЛА"
        elif days_left < 7:
            status = f"⚠️  {days_left}д"
        else:
            status = f"✅ {days_left}д"
        
        note_short = (note[:20] + "...") if note and len(note) > 20 else (note or "-")
        print(f"{id_:>4} | {key:<25} | {expires_dt.strftime('%d.%m.%Y %H:%M'):<20} | {max_inst:>3} | {status:<12} | {note_short}")
    
    print("=" * 90 + "\n")

def interactive_create():
    """Интерактивное создание лицензии"""
    print("\n" + "=" * 50)
    print("📝 СОЗДАНИЕ НОВОЙ ЛИЦЕНЗИИ")
    print("=" * 50)
    
    # Дни
    while True:
        days_input = input("\nСрок действия в днях [30]: ").strip()
        if not days_input:
            days = 30
            break
        try:
            days = int(days_input)
            if days < 1:
                print("❌ Минимум 1 день")
                continue
            if days > 365:
                print("⚠️  Максимум 365 дней, устанавливаю 365")
                days = 365
            break
        except ValueError:
            print("❌ Введите число")
    
    # Экземпляры
    while True:
        instances_input = input("Макс. кол-во экземпляров [1]: ").strip()
        if not instances_input:
            instances = 1
            break
        try:
            instances = int(instances_input)
            if instances < 1:
                print("❌ Минимум 1")
                continue
            if instances > 10:
                print("⚠️  Максимум 10, устанавливаю 10")
                instances = 10
            break
        except ValueError:
            print("❌ Введите число")
    
    # Заметка
    note = input("Заметка (имя клиента, комментарий) []: ").strip()
    
    # Подтверждение
    print("\n" + "-" * 50)
    print(f"Срок:       {days} дней")
    print(f"Экземпляры: {instances}")
    print(f"Заметка:    {note or '(нет)'}")
    print("-" * 50)
    
    confirm = input("\nСоздать лицензию? [Y/n]: ").strip().lower()
    if confirm and confirm != 'y' and confirm != 'yes' and confirm != 'д' and confirm != 'да':
        print("❌ Отменено")
        return
    
    # Создаём
    key, expires = create_license(days, instances, note)
    
    print("\n" + "=" * 50)
    print("✅ ЛИЦЕНЗИЯ СОЗДАНА")
    print("=" * 50)
    print(f"Ключ:      {key}")
    print(f"Истекает:  {expires.strftime('%d.%m.%Y %H:%M')}")
    print(f"Срок:      {days} дней")
    print(f"Экз-ры:    {instances}")
    if note:
        print(f"Заметка:   {note}")
    print("=" * 50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Управление лицензиями")
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    
    # create - интерактивный
    subparsers.add_parser("create", help="Создать лицензию (интерактивно)")
    
    # create-quick - быстрый с параметрами
    quick_parser = subparsers.add_parser("create-quick", help="Создать лицензию быстро")
    quick_parser.add_argument("--days", type=int, default=30, help="Срок действия в днях")
    quick_parser.add_argument("--instances", type=int, default=1, help="Макс. экземпляров")
    quick_parser.add_argument("--note", type=str, default="", help="Заметка")
    
    # list
    subparsers.add_parser("list", help="Показать все лицензии")
    
    args = parser.parse_args()
    
    if args.command == "create":
        interactive_create()
        
    elif args.command == "create-quick":
        key, expires = create_license(args.days, args.instances, args.note)
        print("\n" + "=" * 50)
        print("✅ ЛИЦЕНЗИЯ СОЗДАНА")
        print("=" * 50)
        print(f"Ключ:      {key}")
        print(f"Истекает:  {expires.strftime('%d.%m.%Y %H:%M')}")
        print("=" * 50 + "\n")
        
    elif args.command == "list":
        list_licenses()
        
    else:
        # По умолчанию - интерактивное создание
        interactive_create()

if __name__ == "__main__":
    main()
