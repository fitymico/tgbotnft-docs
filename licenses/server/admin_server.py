"""
ADMIN Server - для локальной сети
Создание и управление лицензиями
Запускать ТОЛЬКО в локальной сети!
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import os

from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
import uvicorn

from database import Database, License, Instance

app = FastAPI(title="License Admin Server", version="1.0.0")
security = HTTPBasic()

# Инициализация БД
DB_PATH = os.environ.get("DB_PATH", "licenses.db")
db = Database(DB_PATH)

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Аутентификация
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD не задан. Установите переменную окружения ADMIN_PASSWORD.")

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Проверка HTTP Basic Auth"""
    if not secrets.compare_digest(credentials.username, ADMIN_USER) or \
       not secrets.compare_digest(credentials.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Неверные учётные данные",
                            headers={"WWW-Authenticate": "Basic"})
    return credentials.username

async def verify_csrf(request: Request):
    """Проверка CSRF через Origin/Referer заголовки"""
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    host = request.headers.get("host", "")
    host_name = host.split(":")[0] if host else ""
    allowed = {host_name, "localhost", "127.0.0.1"}

    if origin:
        if urlparse(origin).hostname not in allowed:
            raise HTTPException(status_code=403, detail="CSRF: недопустимый Origin")
        return
    if referer:
        if urlparse(referer).hostname not in allowed:
            raise HTTPException(status_code=403, detail="CSRF: недопустимый Referer")
        return
    # Браузеры всегда отправляют Origin или Referer при POST из формы
    raise HTTPException(status_code=403, detail="CSRF: отсутствует Origin/Referer")

# ==================== Web Interface ====================

@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _user: str = Depends(verify_admin)):
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
    note: str = Form(""),
    _user: str = Depends(verify_admin),
    _csrf: None = Depends(verify_csrf)
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
async def extend_license(license_id: int, days: int = Form(30), _user: str = Depends(verify_admin), _csrf: None = Depends(verify_csrf)):
    """Продление лицензии"""
    license = db.get_license_by_id(license_id)
    if license:
        new_expires = max(license.expires_at, datetime.now()) + timedelta(days=days)
        db.update_license_expiry(license_id, new_expires)
    return RedirectResponse(url="/", status_code=303)

@app.post("/license/{license_id}/delete")
async def delete_license(license_id: int, _user: str = Depends(verify_admin), _csrf: None = Depends(verify_csrf)):
    """Удаление лицензии"""
    db.delete_license(license_id)
    return RedirectResponse(url="/", status_code=303)

@app.post("/instance/{instance_id}/deactivate")
async def deactivate_instance_web(instance_id: int, _user: str = Depends(verify_admin), _csrf: None = Depends(verify_csrf)):
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
