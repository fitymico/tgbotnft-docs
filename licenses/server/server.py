"""
License Server для Telegram Gift Bot
FastAPI + SQLite + Веб-интерфейс
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import os

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from database import Database, License, Instance

app = FastAPI(title="License Server", version="1.0.0")

# Инициализация БД
db = Database()

# Шаблоны
templates = Jinja2Templates(directory="templates")

# ==================== API Models ====================

class ActivateRequest(BaseModel):
    license_key: str
    instance_id: str

class ActivateResponse(BaseModel):
    success: bool
    session_token: Optional[str] = None
    expires_at: Optional[str] = None
    message: str

class HeartbeatRequest(BaseModel):
    session_token: str

class HeartbeatResponse(BaseModel):
    success: bool
    expires_at: Optional[str] = None
    message: str

# ==================== API Endpoints ====================

@app.post("/api/activate", response_model=ActivateResponse)
async def activate_license(req: ActivateRequest, request: Request):
    """Активация лицензии"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Проверяем лицензию
    license = db.get_license_by_key(req.license_key)
    if not license:
        raise HTTPException(status_code=404, detail="Лицензия не найдена")
    
    # Проверяем срок действия
    if license.expires_at < datetime.now():
        raise HTTPException(status_code=403, detail="Лицензия истекла")
    
    # Проверяем количество активных экземпляров
    active_instances = db.get_active_instances(license.id)
    
    # Проверяем, не этот ли instance уже активирован
    existing = db.get_instance_by_instance_id(req.instance_id)
    if existing and existing.license_id == license.id and existing.is_active:
        # Обновляем heartbeat и возвращаем токен
        db.update_heartbeat(existing.session_token)
        return ActivateResponse(
            success=True,
            session_token=existing.session_token,
            expires_at=license.expires_at.isoformat(),
            message="Лицензия уже активирована на этом устройстве"
        )
    
    # Проверяем лимит экземпляров
    if len(active_instances) >= license.max_instances:
        raise HTTPException(
            status_code=403, 
            detail=f"Достигнут лимит активных экземпляров ({license.max_instances})"
        )
    
    # Создаём новый экземпляр
    session_token = secrets.token_hex(32)
    instance = Instance(
        license_id=license.id,
        instance_id=req.instance_id,
        session_token=session_token,
        ip_address=client_ip
    )
    db.create_instance(instance)
    
    return ActivateResponse(
        success=True,
        session_token=session_token,
        expires_at=license.expires_at.isoformat(),
        message="Лицензия успешно активирована"
    )

@app.post("/api/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(req: HeartbeatRequest):
    """Проверка активности лицензии (вызывается каждый час)"""
    instance = db.get_instance_by_token(req.session_token)
    if not instance or not instance.is_active:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    
    license = db.get_license_by_id(instance.license_id)
    if not license:
        raise HTTPException(status_code=404, detail="Лицензия не найдена")
    
    if license.expires_at < datetime.now():
        db.deactivate_instance(req.session_token)
        raise HTTPException(status_code=403, detail="Лицензия истекла")
    
    # Обновляем время последнего heartbeat
    db.update_heartbeat(req.session_token)
    
    return HeartbeatResponse(
        success=True,
        expires_at=license.expires_at.isoformat(),
        message="OK"
    )

@app.post("/api/deactivate")
async def deactivate(req: HeartbeatRequest):
    """Деактивация экземпляра"""
    db.deactivate_instance(req.session_token)
    return {"success": True, "message": "Экземпляр деактивирован"}

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
    license_key = generate_license_key()
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

def generate_license_key() -> str:
    """Генерация ключа лицензии в формате GIFT-XXXX-XXXX-XXXX-XXXX"""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без путающихся символов
    parts = []
    for _ in range(4):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return f"GIFT-{'-'.join(parts)}"

# ==================== Main ====================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
