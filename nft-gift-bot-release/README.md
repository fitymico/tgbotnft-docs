# NFT Gift Bot — Self-Host

Telegram-бот для автоматической покупки Star Gift на Telegram.

Self-Host версия работает на вашем сервере и получает данные о новых подарках от центрального сервера через UDP.

## Требования

- Linux (x86_64 или ARM64)
- Подписка SELF-HOST (приобретается в Service-Bot)
- Telegram Bot Token (от @BotFather)
- Telegram API credentials (https://my.telegram.org)
- Session String (получается при авторизации через Service-Bot)
- Открытый UDP-порт для приёма данных

## Быстрая установка

```bash
curl -fsSL https://raw.githubusercontent.com/seventyzero/nft-gift-bot-release/main/install.sh | sudo bash
```

или

```bash
wget -qO- https://raw.githubusercontent.com/seventyzero/nft-gift-bot-release/main/install.sh | sudo bash
```

Установщик автоматически:
1. Определит дистрибутив и архитектуру
2. Скачает бинарник
3. Запросит конфигурацию (6 параметров)
4. Откроет UDP-порт в файрволе
5. Создаст и запустит systemd/OpenRC сервис

## Ручная установка

### 1. Скачайте бинарник

Доступные бинарники:
- `nft-gift-bot-linux-amd64` — для x86_64
- `nft-gift-bot-linux-arm64` — для ARM64 (Raspberry Pi 4, Oracle Cloud и т.д.)

```bash
sudo mkdir -p /opt/nft-gift-bot
sudo curl -fsSL https://github.com/seventyzero/nft-gift-bot-release/raw/main/nft-gift-bot-linux-amd64 \
    -o /opt/nft-gift-bot/nft-gift-bot
sudo chmod +x /opt/nft-gift-bot/nft-gift-bot
```

### 2. Создайте конфигурацию

```bash
sudo cat > /opt/nft-gift-bot/.env << 'EOF'
BOT_TOKEN=123456789:AABBCC...
ADMIN_ID=123456789
LICENSE_KEY=ваш-лицензионный-ключ
API_ID=12345
API_HASH=abcdef1234567890abcdef1234567890
SESSION_STRING=ваша-session-string
UDP_LISTEN_HOST=0.0.0.0
UDP_LISTEN_PORT=9200
EOF

sudo chmod 600 /opt/nft-gift-bot/.env
```

### 3. Создайте директорию для данных

```bash
sudo mkdir -p /opt/nft-gift-bot/data
```

### 4. Создайте systemd-сервис

```bash
sudo cat > /etc/systemd/system/nft-gift-bot.service << 'EOF'
[Unit]
Description=NFT Gift Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/nft-gift-bot
EnvironmentFile=/opt/nft-gift-bot/.env
ExecStart=/opt/nft-gift-bot/nft-gift-bot
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nft-gift-bot
sudo systemctl start nft-gift-bot
```

### 5. Откройте UDP-порт

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 9200/udp

# firewalld (CentOS/Fedora)
sudo firewall-cmd --permanent --add-port=9200/udp
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p udp --dport 9200 -j ACCEPT
```

### 6. Сообщите адрес в Service-Bot

После установки сообщите в Service-Bot ваш внешний IP и UDP-порт, чтобы сервер начал отправлять данные о подарках.

## Конфигурация

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен Telegram-бота от @BotFather |
| `ADMIN_ID` | Ваш Telegram ID (числовой) |
| `LICENSE_KEY` | Лицензионный ключ SELF-HOST подписки |
| `API_ID` | Telegram API ID (https://my.telegram.org) |
| `API_HASH` | Telegram API Hash |
| `SESSION_STRING` | Строка сессии Telethon (из Service-Bot) |
| `UDP_LISTEN_HOST` | Адрес прослушивания UDP (обычно `0.0.0.0`) |
| `UDP_LISTEN_PORT` | Порт UDP (по умолчанию `9200`) |

## Управление

```bash
# Статус
sudo systemctl status nft-gift-bot

# Логи (в реальном времени)
sudo journalctl -u nft-gift-bot -f

# Перезапуск
sudo systemctl restart nft-gift-bot

# Остановка
sudo systemctl stop nft-gift-bot
```

## Обновление

Повторно запустите установщик — он обновит бинарник, сохранив существующую конфигурацию `.env`:

```bash
curl -fsSL https://raw.githubusercontent.com/seventyzero/nft-gift-bot-release/main/install.sh | sudo bash
```

Или вручную:

```bash
sudo systemctl stop nft-gift-bot
sudo curl -fsSL https://github.com/seventyzero/nft-gift-bot-release/raw/main/nft-gift-bot-linux-amd64 \
    -o /opt/nft-gift-bot/nft-gift-bot
sudo chmod +x /opt/nft-gift-bot/nft-gift-bot
sudo systemctl start nft-gift-bot
```

## Удаление

```bash
sudo bash /opt/nft-gift-bot/uninstall.sh
```

Или вручную:

```bash
sudo systemctl stop nft-gift-bot
sudo systemctl disable nft-gift-bot
sudo rm /etc/systemd/system/nft-gift-bot.service
sudo systemctl daemon-reload
sudo rm -rf /opt/nft-gift-bot
```

## Поддерживаемые дистрибутивы

| Дистрибутив | Версия | Init-система |
|---|---|---|
| Ubuntu | 20.04+ | systemd |
| Debian | 11+ | systemd |
| CentOS / RHEL | 8+ | systemd |
| Fedora | 36+ | systemd |
| Arch Linux | rolling | systemd |
| Alpine | 3.17+ | OpenRC |
| openSUSE | Leap 15.4+ | systemd |

## Поддержка

При возникновении проблем обратитесь в Service-Bot.
