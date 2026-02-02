<p align="center">
  <img src="Telegram-Bot-NFT/logo.webp" alt="Telegram Bot NFT" width="120" />
</p>

<h1 align="center">Telegram Bot NFT</h1>

<p align="center">
  <strong>Автоматическая покупка NFT-подарков в Telegram</strong>
</p>

<p align="center">
  <a href="https://pluttan.github.io/Telegram-Bot-NFT-docs/">Документация</a> &bull;
  <a href="https://pluttan.github.io/Telegram-Bot-NFT-docs/purchase">Купить лицензию</a> &bull;
  <a href="https://t.me/l_servicebot">Service Bot</a>
</p>

---

## Возможности

- **Автоматическое сканирование** — мониторинг новых подарков в реальном времени
- **Мгновенная покупка** — автоматический выкуп сразу после появления
- **Гибкие правила** — настройка распределения звезд по цене подарков
- **Service Bot** — покупка лицензии, настройка и управление ботом через Telegram
- **Система лицензирования** — admin/public серверы для выдачи и валидации ключей

## Структура монорепозитория

```
tgbotnft/
├── Telegram-Bot-NFT/     # Основной бот (Python + TypeScript)
│   ├── Message_Bot/      #   Telegram-бот на aiogram
│   ├── Gift_API/         #   API покупки подарков (TS)
│   ├── docker/           #   Docker-конфигурация
│   └── scripts/          #   Bash-скрипты запуска
│
├── Service-Bot/          # Сервисный бот для пользователей
│                         #   Покупка лицензий, настройка, управление
│
├── licenses/             # Сервер лицензий
│   └── server/           #   Admin (:8081) + Public (:8080) серверы
│
└── docs/                 # Документация (Docusaurus)
                          #   Отдельный деплой на GitHub Pages
```

## Быстрый старт

### Требования

- Python 3.10+
- Node.js 18+

### Telegram-Bot-NFT

```bash
cd Telegram-Bot-NFT
cp .env.example .env     # Заполнить переменные
make all                 # Установить зависимости и запустить
```

### Service-Bot

```bash
cd Service-Bot
pip install -r requirements.txt
python service_bot.py
```

### License Server

```bash
cd licenses
make install
make start
```

### Документация (локально)

```bash
cd docs
npm install
npm start                # http://localhost:3000
```

## Конфигурация (.env)

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | Ваш Telegram ID |
| `API_ID` | API ID от [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | API Hash от [my.telegram.org](https://my.telegram.org) |
| `LICENSE_KEY` | Ключ лицензии |

## Тарифные планы

|  | SELF-HOST | HOSTING | HOSTING-PRO |
|--|-----------|---------|-------------|
| Месяц | 109 Stars (~199 RUB) | 169 Stars (~299 RUB) | 249 Stars (~449 RUB) |
| Год | 1090 Stars (~1990 RUB) | 1690 Stars (~2990 RUB) | 2490 Stars (~4490 RUB) |

## Репозитории

| Репозиторий | Назначение |
|-------------|------------|
| [seventyzero/tgbotnft](https://github.com/seventyzero/tgbotnft) | Монорепозиторий (этот) |
| [seventyzero/tgbotnft-docs](https://github.com/seventyzero/tgbotnft-docs) | Документация (деплой на GitHub Pages) |

## Лицензия

Проприетарное ПО. Подробнее в файле [LICENSE](Telegram-Bot-NFT/LICENSE).

**&copy; 2026 seventyzero. Все права защищены.**
