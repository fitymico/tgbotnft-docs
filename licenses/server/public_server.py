"""
PUBLIC Server - для публичного доступа
Только проверка лицензий (activate, heartbeat, deactivate)
Никаких функций создания/управления!
"""
from datetime import datetime
from typing import Optional
import secrets
import os

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn

from database import Database, Instance

app = FastAPI(title="License Validation Server", version="1.0.0")

# Инициализация БД
DB_PATH = os.environ.get("DB_PATH", "licenses.db")
db = Database(DB_PATH)

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

@app.get("/")
async def health():
    """Health check"""
    return {"status": "ok", "service": "License Validation Server"}

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

# ==================== Main ====================

if __name__ == "__main__":
    print("=" * 50)
    print("🌐 PUBLIC SERVER - для валидации лицензий")
    print("=" * 50)
    print(f"База данных: {DB_PATH}")
    print("Слушает: http://0.0.0.0:8080")
    print("=" * 50)
    
    # Слушаем на всех интерфейсах
    uvicorn.run(app, host="0.0.0.0", port=8080)
