# License Server

Система лицензий для Telegram Gift Bot.

## Архитектура

```
┌─────────────────────┐         ┌─────────────────────┐
│   Admin Server      │         │   Public Server     │
│   (локальная сеть)  │         │   (интернет)        │
│   :8081             │         │   :8080             │
├─────────────────────┤         ├─────────────────────┤
│ • Создание лицензий │         │ • /api/activate     │
│ • Управление        │         │ • /api/heartbeat    │
│ • Веб-интерфейс     │         │ • /api/deactivate   │
└─────────────────────┘         └─────────────────────┘
          │                               │
          └───────────┬───────────────────┘
                      │
              ┌───────▼───────┐
              │  licenses.db  │
              │   (SQLite)    │
              └───────────────┘
```

## Команды Makefile

```bash
# Создание лицензий
make license          # Интерактивное создание
make license-quick DAYS=60 INSTANCES=2 NOTE="Клиент"
make license-list     # Показать все лицензии

# Серверы
make license-admin    # Admin сервер (127.0.0.1:8081) - только локально!
make license-public   # Public сервер (0.0.0.0:8080) - для интернета
```

## Развёртывание

### На сервере с белым IP

1. **Скопировать файлы:**
```bash
scp -r licenses/server/ user@server:/opt/license-server/
```

2. **Запустить public сервер:**
```bash
cd /opt/license-server
pip install -r requirements.txt
python3 public_server.py
```

3. **Опционально: systemd сервис**
```bash
# /etc/systemd/system/license-server.service
[Unit]
Description=License Validation Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/license-server
ExecStart=/usr/bin/python3 public_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable license-server
sudo systemctl start license-server
```

### Локально (для создания лицензий)

```bash
make license-admin  # Открыть http://127.0.0.1:8081
```

## API Endpoints (Public Server)

### POST /api/activate
```json
{
  "license_key": "GIFT-XXXX-XXXX-XXXX-XXXX",
  "instance_id": "unique-machine-id"
}
```

### POST /api/heartbeat
```json
{
  "session_token": "..."
}
```

### POST /api/deactivate
```json
{
  "session_token": "..."
}
```

## Безопасность

- **Admin Server** слушает ТОЛЬКО на `127.0.0.1` — недоступен из интернета
- **Public Server** предоставляет ТОЛЬКО валидацию — нельзя создать/удалить лицензию
- База данных `licenses.db` должна быть общей для обоих серверов
