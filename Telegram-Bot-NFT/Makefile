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
        docker-build docker-up docker-down docker-logs docker-restart

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
	python3 -m venv $(VENV)
	@echo "Виртуальное окружение создано в $(VENV)/"

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
	@pkill -f "dist/giftBot.js" 2>/dev/null || true

stop: stop-talkbot stop-giftbot
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
