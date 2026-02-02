# ================== Telegram-Bot-NFT Makefile ==================
# Управление Python ботом и TypeScript API

SHELL := /bin/bash
VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Определяем директорию проекта
PROJECT_DIR := $(shell pwd)
MESSAGE_BOT_DIR := $(PROJECT_DIR)/Message_Bot
GIFT_API_DIR := $(PROJECT_DIR)/Gift_API
SCRIPTS_DIR := $(PROJECT_DIR)/scripts

# PID файлы для отслеживания процессов
TALKBOT_PID := $(PROJECT_DIR)/data/talkbot.pid
GIFTBOT_PID := $(PROJECT_DIR)/data/giftbot.pid

.PHONY: help all install install-python install-node venv clean full-clean \
        start start-talkbot start-giftbot \
        stop stop-talkbot stop-giftbot \
        restart status logs \
        docker-build docker-up docker-down docker-logs docker-restart \
        build-bin build-bin-deps release \
        license license-quick license-list license-admin license-public \
        docs docs-build docs-install

# ================== Справка ==================
help:
	@echo "Telegram-Bot-NFT - Makefile команды"
	@echo ""
	@echo "Быстрый старт:"
	@echo "  make all              - Установить зависимости и запустить бота"
	@echo ""
	@echo "Установка:"
	@echo "  make install          - Установить все зависимости (Python + Node.js)"
	@echo "  make install-python   - Установить только Python зависимости"
	@echo "  make install-node     - Установить только Node.js зависимости"
	@echo "  make venv             - Создать виртуальное окружение Python"
	@echo ""
	@echo "Управление ботами:"
	@echo "  make start            - Запустить все боты"
	@echo "  make start-talkbot    - Запустить только Telegram бот (aiogram)"
	@echo "  make start-giftbot    - Запустить только Gift API бот"
	@echo ""
	@echo "  make stop             - Остановить все боты"
	@echo "  make stop-talkbot     - Остановить Telegram бот"
	@echo "  make stop-giftbot     - Остановить Gift API бот"
	@echo ""
	@echo "  make restart          - Перезапустить все боты"
	@echo "  make status           - Показать статус ботов"
	@echo "  make logs             - Показать логи"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     - Собрать Docker образ"
	@echo "  make docker-up        - Запустить в Docker"
	@echo "  make docker-down      - Остановить Docker"
	@echo "  make docker-logs      - Логи Docker"
	@echo "  make docker-restart   - Перезапустить Docker"
	@echo ""
	@echo "Прочее:"
	@echo "  make clean            - Удалить виртуальное окружение и кэш"
	@echo "  make full-clean       - Полная очистка (логи, node_modules, dist)"
	@echo "  make build-bin        - Собрать бинарники для распространения"
	@echo "  make release          - Собрать и опубликовать релиз на GitHub"
	@echo ""
	@echo "Лицензии:"
	@echo "  make license          - Создать лицензию (интерактивно)"
	@echo "  make license-quick    - Быстрое создание (DAYS=30 INSTANCES=1 NOTE='')"
	@echo "  make license-list     - Показать все лицензии"
	@echo "  make license-admin    - Запустить admin сервер (локальный, :8081)"
	@echo "  make license-public   - Запустить public сервер (валидация, :8080)"
	@echo ""
	@echo "Документация:"
	@echo "  make docs             - Запустить Docusaurus dev-сервер"
	@echo "  make docs-install     - Установить зависимости документации"
	@echo "  make docs-build       - Собрать статическую документацию"
	@echo ""
	@echo "Перед запуском создайте файл .env (см. .env.example)"

# ================== Быстрый старт ==================
all: install start
	@echo ""
	@echo "🚀 Бот установлен и запущен!"

# ================== Docker ==================
DOCKER_DIR := $(PROJECT_DIR)/docker

docker-build:
	@echo "🐳 Сборка Docker образа..."
	docker compose -f $(DOCKER_DIR)/docker-compose.yml build

docker-up: docker-build
	@echo "🐳 Запуск в Docker..."
	docker compose -f $(DOCKER_DIR)/docker-compose.yml up -d
	@echo ""
	@echo "✅ Бот запущен в Docker!"
	@echo "Используйте 'make docker-logs' для просмотра логов"

docker-down:
	@echo "🐳 Остановка Docker..."
	docker compose -f $(DOCKER_DIR)/docker-compose.yml down
	@echo "✅ Docker остановлен"

docker-logs:
	docker compose -f $(DOCKER_DIR)/docker-compose.yml logs -f --tail=50

docker-restart: docker-down docker-up
	@echo "✅ Docker перезапущен"

# ================== Установка ==================
venv:
	@echo "Создание виртуального окружения..."
	@# Проверяем, что venv использует Python 3
	@if [ -d $(VENV) ]; then \
		if $(PYTHON) --version 2>&1 | grep -q "Python 2"; then \
			echo "Обнаружен Python 2 в venv, пересоздаём..."; \
			rm -rf $(VENV); \
		fi; \
	fi
	@if [ ! -d $(VENV) ]; then \
		python3 -m venv $(VENV); \
		echo "Виртуальное окружение создано в $(VENV)/"; \
	else \
		echo "Виртуальное окружение уже существует"; \
	fi

install-python: venv
	@echo "Установка Python зависимостей..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Python зависимости установлены!"

install-node:
	@echo "Установка Node.js зависимостей..."
	cd $(GIFT_API_DIR) && npm install
	@echo "Node.js зависимости установлены!"

install: install-python install-node
	@echo ""
	@echo "✅ Все зависимости установлены!"
	@echo ""
	@echo "Запустите: make start"

# ================== Запуск ботов ==================
start-talkbot:
	@echo "Запуск Telegram бота (talkbot)..."
	@mkdir -p $(PROJECT_DIR)/data
	@if [ -f $(TALKBOT_PID) ] && kill -0 $$(cat $(TALKBOT_PID)) 2>/dev/null; then \
		echo "Telegram бот уже запущен (PID: $$(cat $(TALKBOT_PID)))"; \
	else \
		cd $(MESSAGE_BOT_DIR) && \
		source $(PROJECT_DIR)/$(VENV)/bin/activate && \
		set -a && source $(PROJECT_DIR)/.env && set +a && \
		nohup $(PROJECT_DIR)/$(PYTHON) talkbot.py > $(PROJECT_DIR)/data/talkbot.log 2>&1 & \
		echo $$! > $(TALKBOT_PID); \
		echo "Telegram бот запущен (PID: $$(cat $(TALKBOT_PID)))"; \
	fi

start-giftbot:
	@echo "Запуск Gift API бота..."
	@mkdir -p $(PROJECT_DIR)/data
	@if [ -f $(GIFTBOT_PID) ] && kill -0 $$(cat $(GIFTBOT_PID)) 2>/dev/null; then \
		echo "Gift API бот уже запущен (PID: $$(cat $(GIFTBOT_PID)))"; \
	else \
		cd $(GIFT_API_DIR) && \
		set -a && source $(PROJECT_DIR)/.env && set +a && \
		nohup npm run dev > $(PROJECT_DIR)/data/giftbot.log 2>&1 & \
		echo $$! > $(GIFTBOT_PID); \
		echo "Gift API бот запущен (PID: $$(cat $(GIFTBOT_PID)))"; \
	fi

start: start-talkbot
	@echo ""
	@echo "✅ Боты запущены!"
	@echo "Используйте 'make logs' для просмотра логов"
	@echo "Используйте 'make status' для проверки статуса"

# ================== Остановка ботов ==================
stop-talkbot:
	@echo "Остановка Telegram бота..."
	@if [ -f $(TALKBOT_PID) ]; then \
		PID=$$(cat $(TALKBOT_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			sleep 1; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Принудительная остановка..."; \
				kill -9 $$PID; \
			fi; \
			echo "Telegram бот остановлен"; \
		else \
			echo "Telegram бот не запущен"; \
		fi; \
		rm -f $(TALKBOT_PID); \
	else \
		echo "Telegram бот не запущен"; \
	fi

stop-giftbot:
	@echo "Остановка Gift API бота..."
	@if [ -f $(GIFTBOT_PID) ]; then \
		PID=$$(cat $(GIFTBOT_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			sleep 1; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Принудительная остановка..."; \
				kill -9 $$PID; \
			fi; \
			echo "Gift API бот остановлен"; \
		else \
			echo "Gift API бот не запущен"; \
		fi; \
		rm -f $(GIFTBOT_PID); \
	else \
		echo "Gift API бот не запущен"; \
	fi
	@# Также убиваем процессы node если остались
	@pkill -f "node.*giftBot" 2>/dev/null || true

stop: stop-talkbot stop-giftbot
	@# Принудительно убиваем все оставшиеся процессы
	@pkill -f "python.*talkbot" 2>/dev/null || true
	@pkill -f "node.*giftBot" 2>/dev/null || true
	@echo ""
	@echo "✅ Все боты остановлены"

# ================== Перезапуск ==================
restart: stop start
	@echo "✅ Боты перезапущены"

# ================== Статус ==================
status:
	@echo "=== Статус ботов ==="
	@echo ""
	@if [ -f $(TALKBOT_PID) ] && kill -0 $$(cat $(TALKBOT_PID)) 2>/dev/null; then \
		echo "🟢 Telegram бот: запущен (PID: $$(cat $(TALKBOT_PID)))"; \
	else \
		echo "🔴 Telegram бот: остановлен"; \
	fi
	@if [ -f $(GIFTBOT_PID) ] && kill -0 $$(cat $(GIFTBOT_PID)) 2>/dev/null; then \
		echo "🟢 Gift API бот: запущен (PID: $$(cat $(GIFTBOT_PID)))"; \
	else \
		echo "🔴 Gift API бот: остановлен"; \
	fi
	@echo ""

# ================== Логи ==================
logs:
	@echo "=== Логи ботов ==="
	@echo ""
	@echo "--- Telegram бот (последние 20 строк) ---"
	@if [ -f $(PROJECT_DIR)/data/talkbot.log ]; then \
		tail -20 $(PROJECT_DIR)/data/talkbot.log; \
	else \
		echo "Лог файл не найден"; \
	fi
	@echo ""
	@echo "--- Gift API бот (последние 20 строк) ---"
	@if [ -f $(PROJECT_DIR)/data/giftbot.log ]; then \
		tail -20 $(PROJECT_DIR)/data/giftbot.log; \
	else \
		echo "Лог файл не найден"; \
	fi
	@echo ""
	@echo "--- Лог покупок (последние 20 строк) ---"
	@if [ -f $(PROJECT_DIR)/data/bot.log ]; then \
		tail -20 $(PROJECT_DIR)/data/bot.log; \
	else \
		echo "Лог файл не найден"; \
	fi

# ================== Очистка ==================
clean:
	@echo "Очистка..."
	rm -rf $(VENV)
	rm -rf $(MESSAGE_BOT_DIR)/__pycache__
	rm -rf $(PROJECT_DIR)/__pycache__
	find $(PROJECT_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find $(PROJECT_DIR) -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Очистка завершена"

full-clean: stop clean
	@echo "Полная очистка..."
	@# Удаляем логи
	rm -f $(PROJECT_DIR)/data/*.log
	@# Удаляем PID файлы
	rm -f $(PROJECT_DIR)/data/*.pid
	@# Удаляем node_modules и dist
	rm -rf $(GIFT_API_DIR)/node_modules
	rm -rf $(GIFT_API_DIR)/dist
	@echo ""
	@echo "✅ Полная очистка завершена"
	@echo "Для переустановки выполните: make install"

# ================== Сборка бинарников ==================
VERSION := $(shell cat .version 2>/dev/null || echo "0.0.0")
RELEASE_DIR := $(PROJECT_DIR)/../releases/v$(VERSION)

build-bin-deps:
	@echo "📦 Установка зависимостей для сборки..."
	$(PIP) install pyinstaller
	@if ! command -v bun &> /dev/null; then \
		echo "Установка bun..."; \
		curl -fsSL https://bun.sh/install | bash; \
	fi

build-bin: install build-bin-deps
	@echo ""
	@echo "📦 Сборка бинарников v$(VERSION)..."
	@echo ""
	@# Создаём структуру директорий
	mkdir -p $(RELEASE_DIR)/linux/data
	mkdir -p $(RELEASE_DIR)/macos/data
	mkdir -p $(RELEASE_DIR)/windows/data
	@# Копируем .env.example
	cp $(PROJECT_DIR)/.env.example $(RELEASE_DIR)/linux/
	cp $(PROJECT_DIR)/.env.example $(RELEASE_DIR)/macos/
	cp $(PROJECT_DIR)/.env.example $(RELEASE_DIR)/windows/
	@# Копируем LICENSE
	cp $(PROJECT_DIR)/LICENSE $(RELEASE_DIR)/linux/
	cp $(PROJECT_DIR)/LICENSE $(RELEASE_DIR)/macos/
	cp $(PROJECT_DIR)/LICENSE $(RELEASE_DIR)/windows/
	cp $(PROJECT_DIR)/LICENSE.ru $(RELEASE_DIR)/linux/
	cp $(PROJECT_DIR)/LICENSE.ru $(RELEASE_DIR)/macos/
	cp $(PROJECT_DIR)/LICENSE.ru $(RELEASE_DIR)/windows/
	@# Копируем шаблон status.json
	echo '{"is_running":false,"status_text":"Бот остановлен","distribution":"<1000 10","iterations_total":100,"iteration_current":0,"delay":1000}' > $(RELEASE_DIR)/linux/data/status.json
	echo '{"is_running":false,"status_text":"Бот остановлен","distribution":"<1000 10","iterations_total":100,"iteration_current":0,"delay":1000}' > $(RELEASE_DIR)/macos/data/status.json
	echo '{"is_running":false,"status_text":"Бот остановлен","distribution":"<1000 10","iterations_total":100,"iteration_current":0,"delay":1000}' > $(RELEASE_DIR)/windows/data/status.json
	@# Создаём пустой giftID.json
	echo '[]' > $(RELEASE_DIR)/linux/data/giftID.json
	echo '[]' > $(RELEASE_DIR)/macos/data/giftID.json
	echo '[]' > $(RELEASE_DIR)/windows/data/giftID.json
	@echo ""
	@echo "🐍 Сборка Python бота..."
	cd $(MESSAGE_BOT_DIR) && \
		$(PROJECT_DIR)/$(PYTHON) -m PyInstaller --onefile --clean \
		--name talkbot \
		--distpath $(RELEASE_DIR)/linux \
		--add-data "../config.py:." \
		talkbot.py
	@echo ""
	@echo "🟢 Сборка Node.js бота с Bun..."
	@# Сборка для Linux
	cd $(GIFT_API_DIR) && bun build src/giftBot.ts --compile --target=bun-linux-x64 --outfile $(RELEASE_DIR)/linux/giftBot
	@# Сборка для macOS
	cd $(GIFT_API_DIR) && bun build src/giftBot.ts --compile --target=bun-darwin-x64 --outfile $(RELEASE_DIR)/macos/giftBot-x64
	cd $(GIFT_API_DIR) && bun build src/giftBot.ts --compile --target=bun-darwin-arm64 --outfile $(RELEASE_DIR)/macos/giftBot-arm64
	@# Сборка для Windows
	cd $(GIFT_API_DIR) && bun build src/giftBot.ts --compile --target=bun-windows-x64 --outfile $(RELEASE_DIR)/windows/giftBot.exe
	@# Копируем в latest
	@echo ""
	@echo "📋 Копирование в releases/latest..."
	rm -rf $(PROJECT_DIR)/../releases/latest
	cp -r $(RELEASE_DIR) $(PROJECT_DIR)/../releases/latest
	@echo ""
	@echo "✅ Сборка завершена!"
	@echo "Релизы в: $(RELEASE_DIR)/"
	@echo "Latest:   $(PROJECT_DIR)/../releases/latest/"
	@echo ""
	@ls -la $(RELEASE_DIR)/

# Публикация релиза на GitHub
release: build-bin
	@echo ""
	@echo "📤 Публикация релиза v$(VERSION) на GitHub..."
	@echo ""
	@# Проверяем наличие gh CLI
	@if ! command -v gh &> /dev/null; then \
		echo "❌ Ошибка: gh CLI не установлен. Установите: brew install gh"; \
		exit 1; \
	fi
	@# Проверяем авторизацию
	@if ! gh auth status &> /dev/null; then \
		echo "❌ Ошибка: gh не авторизован. Выполните: gh auth login"; \
		exit 1; \
	fi
	@# Создаём zip-архив
	@echo "📦 Создание архива..."
	cd $(PROJECT_DIR)/../releases && zip -r v$(VERSION).zip v$(VERSION)/
	cd $(PROJECT_DIR)/../releases && cp v$(VERSION).zip latest.zip
	@# Создаём версионированный релиз
	cd $(PROJECT_DIR)/../releases && gh release create v$(VERSION) \
		--repo pluttan/Telegram-bot-NFT-releases \
		--title "Release v$(VERSION)" \
		--notes "Telegram Gift Bot v$(VERSION)" \
		v$(VERSION).zip
	@# Обновляем latest релиз (удаляем старый если есть, создаём новый)
	@echo ""
	@echo "📤 Обновление latest..."
	-gh release delete latest --repo pluttan/Telegram-bot-NFT-releases --yes 2>/dev/null || true
	-git -C $(PROJECT_DIR)/../releases push origin :refs/tags/latest 2>/dev/null || true
	cd $(PROJECT_DIR)/../releases && gh release create latest \
		--repo pluttan/Telegram-bot-NFT-releases \
		--title "Latest Release (v$(VERSION))" \
		--notes "Последняя версия Telegram Gift Bot (v$(VERSION))" \
		--prerelease \
		latest.zip
	@echo ""
	@echo "✅ Релизы опубликованы!"
	@echo "v$(VERSION): https://github.com/pluttan/Telegram-bot-NFT-releases/releases/tag/v$(VERSION)"
	@echo "latest:     https://github.com/pluttan/Telegram-bot-NFT-releases/releases/tag/latest"

# ================== Лицензии ==================
LICENSE_DIR := $(PROJECT_DIR)/licenses/server
LICENSE_DB := $(LICENSE_DIR)/licenses.db

# Интерактивное создание лицензии
license:
	@cd $(LICENSE_DIR) && python3 create_license.py create

# Быстрое создание с параметрами
license-quick:
	@cd $(LICENSE_DIR) && python3 create_license.py create-quick --days $(or $(DAYS),30) --instances $(or $(INSTANCES),1) --note "$(or $(NOTE),)"

# Список лицензий
license-list:
	@cd $(LICENSE_DIR) && python3 create_license.py list

# Admin сервер (ТОЛЬКО для локальной сети!)
license-admin:
	@echo ""
	@echo "⚠️  ADMIN SERVER - ТОЛЬКО ДЛЯ ЛОКАЛЬНОЙ СЕТИ!"
	@echo "Веб-интерфейс: http://127.0.0.1:8081"
	@echo ""
	cd $(LICENSE_DIR) && pip install -q -r requirements.txt && python3 admin_server.py

# Public сервер (для валидации лицензий в интернете)
license-public:
	@echo ""
	@echo "🌐 PUBLIC SERVER - для валидации лицензий"
	@echo "API: http://0.0.0.0:8080"
	@echo ""
	cd $(LICENSE_DIR) && pip install -q -r requirements.txt && python3 public_server.py

# ================== Документация ==================
DOCS_DIR := $(PROJECT_DIR)/docs

docs-install:
	@echo "📚 Установка зависимостей документации..."
	cd $(DOCS_DIR) && npm install
	@echo "✅ Зависимости документации установлены!"

docs: docs-install
	@echo ""
	@echo "📚 Запуск Docusaurus dev-сервера..."
	@echo "Документация: http://localhost:3000"
	@echo ""
	cd $(DOCS_DIR) && npm start

docs-build: docs-install
	@echo ""
	@echo "📚 Сборка статической документации..."
	cd $(DOCS_DIR) && npm run build
	@echo ""
	@echo "✅ Документация собрана в $(DOCS_DIR)/build/"
