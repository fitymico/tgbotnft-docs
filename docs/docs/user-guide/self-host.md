---
sidebar_position: 6
---

# SELF-HOST: установка на своём сервере

Тариф **SELF-HOST** предназначен для тех, кто хочет запустить фронтенд бота на собственном сервере. Бот подключается к нашему центральному бэкенду и получает данные о новых подарках через UDP.

## Что Вам понадобится

- Сервер (VPS/VDS) с **Linux** (Ubuntu 20.04+ рекомендуется)
- **Bot Token** от [@BotFather](https://t.me/BotFather)
- **Лицензионный ключ** (получен после оплаты в Service Bot)

## Шаг 1. Получите лицензионный ключ

После оплаты тарифа SELF-HOST в Service Bot нажмите **"Показать лицензионный ключ"**. Ключ имеет формат:

```
SB-XXXXXXXXXXXXXXXX
```

Сохраните его — он понадобится для настройки.

## Шаг 2. Создайте бота в BotFather

Если Вы ещё не создали бота — следуйте инструкции в разделе [Создание бота через BotFather](./create-bot).

## Шаг 3. Установка (автоматическая)

Подключитесь к серверу и выполните:

```bash
curl -fsSL https://raw.githubusercontent.com/seventyzero/nft-gift-bot-release/main/install.sh | sudo bash
```

Установщик автоматически:
1. Определит Ваш дистрибутив и архитектуру
2. Скачает бинарник
3. Запросит конфигурацию (3 параметра)
4. Создаст и запустит systemd-сервис

### Параметры, которые запросит установщик

| # | Параметр | Где получить |
|---|----------|-------------|
| 1 | BOT_TOKEN | @BotFather |
| 2 | ADMIN_ID | @userinfobot |
| 3 | LICENSE_KEY | Service-Bot (после оплаты) |

## Шаг 4. Авторизация Telegram-аккаунта

После установки бот запущен, но требуется авторизация Telegram-аккаунта:

1. Откройте бота в Telegram и отправьте `/start`
2. Бот предложит пройти авторизацию — отправьте `/auth`
3. Введите номер телефона (в формате `+7XXXXXXXXXX`)
4. Введите код подтверждения из Telegram (через пробелы или дефисы: `1 2 3 4 5`)
5. Если включена двухфакторная аутентификация — введите пароль

После успешной авторизации бот сохранит сессию локально. Повторная авторизация не потребуется после перезапуска.

:::tip
Код подтверждения рекомендуется вводить через пробелы или дефисы (например, `1 2 3 4 5` вместо `12345`), чтобы Telegram не заблокировал сообщение с кодом.
:::

## Шаг 3 (альтернатива). Ручная установка

### 3a.1. Скачайте бинарник

```bash
sudo mkdir -p /opt/nft-gift-bot
sudo curl -fsSL https://github.com/seventyzero/nft-gift-bot-release/raw/main/nft-gift-bot-linux-amd64 \
    -o /opt/nft-gift-bot/nft-gift-bot
sudo chmod +x /opt/nft-gift-bot/nft-gift-bot
```

Для ARM64 (Raspberry Pi 4, Oracle Cloud) замените `amd64` на `arm64`.

### 3a.2. Создайте конфигурацию

```bash
sudo nano /opt/nft-gift-bot/.env
```

Содержимое:

```env
BOT_TOKEN=123456789:AABBCC...
ADMIN_ID=123456789
LICENSE_KEY=SB-XXXXXXXXXXXXXXXX
```

```bash
sudo chmod 600 /opt/nft-gift-bot/.env
sudo mkdir -p /opt/nft-gift-bot/data
```

### 3a.3. Создайте systemd-сервис

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
curl -fsSL https://raw.githubusercontent.com/seventyzero/nft-gift-bot-release/main/install.sh | sudo bash
```

Существующая конфигурация `.env` сохранится — установщик подставит текущие значения как умолчания.

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

## Безопасность

- Файл `.env` содержит секретные данные — не публикуйте его содержимое
- Сессия Telegram хранится в `data/session.string` — этот файл даёт доступ к Вашему аккаунту

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
