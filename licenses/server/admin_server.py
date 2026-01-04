"""
ADMIN Server - для локальной сети
Создание и управление лицензиями
Запускать ТОЛЬКО в локальной сети!
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import os

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from database import Database, License, Instance

app = FastAPI(title="License Admin Server", version="1.0.0")

# Инициализация БД
DB_PATH = os.environ.get("DB_PATH", "licenses.db")
db = Database(DB_PATH)

# Шаблоны
templates = Jinja2Templates(directory="templates")

# ==================== Web Interface ====================

@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Панель администратора"""
    licenses = db.get_all_licenses()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "licenses": licenses,
        "now": datetime.now()
    })

@app.post("/license/create")
async def create_license_form(
    days: int = Form(30),
    max_instances: int = Form(1),
    note: str = Form("")
):
    """Создание новой лицензии через форму"""
    license_key = generate_license_key(db)
    expires_at = datetime.now() + timedelta(days=days)
    
    license = License(
        license_key=license_key,
        expires_at=expires_at,
        max_instances=max_instances,
        note=note
    )
    db.create_license(license)
    
    return RedirectResponse(url="/", status_code=303)

@app.post("/license/{license_id}/extend")
async def extend_license(license_id: int, days: int = Form(30)):
    """Продление лицензии"""
    license = db.get_license_by_id(license_id)
    if license:
        new_expires = max(license.expires_at, datetime.now()) + timedelta(days=days)
        db.update_license_expiry(license_id, new_expires)
    return RedirectResponse(url="/", status_code=303)

@app.post("/license/{license_id}/delete")
async def delete_license(license_id: int):
    """Удаление лицензии"""
    db.delete_license(license_id)
    return RedirectResponse(url="/", status_code=303)

@app.post("/instance/{instance_id}/deactivate")
async def deactivate_instance_web(instance_id: int):
    """Деактивация экземпляра через веб"""
    db.deactivate_instance_by_id(instance_id)
    return RedirectResponse(url="/", status_code=303)

# ==================== Utils ====================

def generate_license_key(db: Database) -> str:
    """Генерация уникального ключа лицензии"""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    max_attempts = 100
    
    for _ in range(max_attempts):
        parts = []
        for _ in range(4):
            part = ''.join(secrets.choice(chars) for _ in range(4))
            parts.append(part)
        key = f"GIFT-{'-'.join(parts)}"
        
        # Проверяем уникальность
        if not db.get_license_by_key(key):
            return key
    
    raise RuntimeError("Не удалось сгенерировать уникальный ключ")

# ==================== Main ====================

if __name__ == "__main__":
    print("=" * 50)
    print("⚠️  ADMIN SERVER - ТОЛЬКО ДЛЯ ЛОКАЛЬНОЙ СЕТИ!")
    print("=" * 50)
    print(f"База данных: {DB_PATH}")
    print("Веб-интерфейс: http://127.0.0.1:8081")
    print("=" * 50)
    
    # Слушаем только localhost!
    uvicorn.run(app, host="127.0.0.1", port=8081)
