---
sidebar_position: 6
---

# SELF-HOST: установка на своём сервере

Тариф **SELF-HOST** предназначен для тех, кто хочет запустить фронтенд бота на собственном сервере. Бот подключается к нашему центральному бэкенду и получает данные о новых подарках через UDP.

## Что Вам понадобится

- Сервер (VPS/VDS) с **Linux** (Ubuntu 20.04+ рекомендуется)
- **Bot Token** от [@BotFather](https://t.me/BotFather)
- **Лицензионный ключ** (получен после оплаты в Service Bot)
- **Telegram API ID и Hash** (https://my.telegram.org)
- **Session String** (получена при авторизации через Service-Bot)
- Открытый **UDP-порт** для приёма данных от сервера

## Шаг 1. Получите лицензионный ключ

После оплаты тарифа SELF-HOST в Service Bot нажмите **"Показать лицензионный ключ"**. Ключ имеет формат:

```
SB-XXXXXXXXXXXXXXXX
```

Сохраните его — он понадобится для настройки.

## Шаг 2. Создайте бота в BotFather

Если Вы ещё не создали бота — следуйте инструкции в разделе [Создание бота через BotFather](./create-bot).

## Шаг 3. Получите Telegram API credentials

1. Перейдите на https://my.telegram.org
2. Войдите с номером телефона
3. Перейдите в **API development tools**
4. Создайте приложение (любое название)
5. Скопируйте **API ID** (число) и **API Hash** (строка)

## Шаг 4. Пройдите авторизацию в Service-Bot

В Service-Bot нажмите кнопку авторизации — откроется веб-страница. После авторизации Вы получите **Session String**. Сохраните её.

## Шаг 5. Установка (автоматическая)

Подключитесь к серверу и выполните:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/nft-gift-bot-release/main/install.sh | sudo bash
```

Установщик автоматически:
1. Определит Ваш дистрибутив и архитектуру
2. Скачает бинарник
3. Запросит конфигурацию (6 параметров)
4. Откроет UDP-порт в файрволе
5. Создаст и запустит systemd-сервис

### Параметры, которые запросит установщик

| # | Параметр | Где получить |
|---|----------|-------------|
| 1 | BOT_TOKEN | @BotFather |
| 2 | ADMIN_ID | @userinfobot |
| 3 | LICENSE_KEY | Service-Bot (после оплаты) |
| 4 | API_ID, API_HASH | https://my.telegram.org |
| 5 | SESSION_STRING | Service-Bot (авторизация) |
| 6 | UDP_LISTEN_PORT | По умолчанию 9200 |

## Шаг 5 (альтернатива). Ручная установка

### 5.1. Скачайте бинарник

```bash
sudo mkdir -p /opt/nft-gift-bot
sudo curl -fsSL https://github.com/YOUR_ORG/nft-gift-bot-release/releases/latest/download/nft-gift-bot-linux-amd64 \
    -o /opt/nft-gift-bot/nft-gift-bot
sudo chmod +x /opt/nft-gift-bot/nft-gift-bot
```

Для ARM64 (Raspberry Pi 4, Oracle Cloud) замените `amd64` на `arm64`.

### 5.2. Создайте конфигурацию

```bash
sudo nano /opt/nft-gift-bot/.env
```

Содержимое:

```env
BOT_TOKEN=123456789:AABBCC...
ADMIN_ID=123456789
LICENSE_KEY=SB-XXXXXXXXXXXXXXXX
API_ID=12345
API_HASH=abcdef1234567890abcdef1234567890
SESSION_STRING=ваша-session-string
UDP_LISTEN_HOST=0.0.0.0
UDP_LISTEN_PORT=9200
```

```bash
sudo chmod 600 /opt/nft-gift-bot/.env
sudo mkdir -p /opt/nft-gift-bot/data
```

### 5.3. Создайте systemd-сервис

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

### 5.4. Откройте UDP-порт

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 9200/udp

# firewalld (CentOS/Fedora)
sudo firewall-cmd --permanent --add-port=9200/udp && sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p udp --dport 9200 -j ACCEPT
```

## Шаг 6. Сообщите адрес серверу

После установки сообщите в Service-Bot Ваш **внешний IP** и **UDP-порт**. Это необходимо для того, чтобы центральный сервер начал отправлять Вам данные о новых подарках.

Узнать внешний IP:

```bash
curl -s https://api.ipify.org
```

---

## Управление ботом

| Команда | Описание |
|---------|----------|
| `sudo systemctl status nft-gift-bot` | Статус бота |
| `sudo systemctl restart nft-gift-bot` | Перезапуск |
| `sudo systemctl stop nft-gift-bot` | Остановка |
| `sudo journalctl -u nft-gift-bot -f` | Логи в реальном времени |

## Обновление

Повторно запустите установщик:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/nft-gift-bot-release/main/install.sh | sudo bash
```

Существующая конфигурация `.env` сохранится — установщик подставит текущие значения как умолчания.

Или вручную:

```bash
sudo systemctl stop nft-gift-bot
sudo curl -fsSL https://github.com/YOUR_ORG/nft-gift-bot-release/releases/latest/download/nft-gift-bot-linux-amd64 \
    -o /opt/nft-gift-bot/nft-gift-bot
sudo chmod +x /opt/nft-gift-bot/nft-gift-bot
sudo systemctl start nft-gift-bot
```

## Удаление

```bash
sudo bash /opt/nft-gift-bot/uninstall.sh
```

## Безопасность

- Файл `.env` содержит секретные данные — не публикуйте его содержимое
- Session String даёт доступ к Вашему Telegram-аккаунту — храните её в безопасности
- UDP-порт должен быть открыт только для протокола UDP, не для TCP
- Рекомендуется ограничить доступ к UDP-порту по IP-адресу сервера (если известен)

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
