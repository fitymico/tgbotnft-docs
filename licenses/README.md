# Telegram Gift Bot — License Server

Система лицензирования для [Telegram Gift Bot](https://github.com/pluttan/Telegram-Bot-NFT).

## Быстрый старт

```bash
# Установка task (если не установлен)
brew install go-task/tap/go-task  # macOS
# или: sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d

# Установка зависимостей
task install

# Запуск обоих серверов
task start
```

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

## Команды

| Команда | Описание |
|---------|----------|
| `task start` | Запустить оба сервера |
| `task stop` | Остановить оба сервера |
| `task status` | Показать статус |
| `task logs` | Показать логи |
| `task license` | Создать лицензию (интерактивно) |
| `task license-list` | Список всех лицензий |

## Лицензия

[LICENSE](LICENSE) • [LICENSE.ru](LICENSE.ru)
