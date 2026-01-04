# License Server Makefile
# Управление admin и public серверами лицензий

PROJECT_DIR := $(shell pwd)
SERVER_DIR := $(PROJECT_DIR)/server
DATA_DIR := $(PROJECT_DIR)/data
ADMIN_PID := $(DATA_DIR)/admin_server.pid
PUBLIC_PID := $(DATA_DIR)/public_server.pid

DAYS ?= 30
INSTANCES ?= 1
NOTE ?= 

.PHONY: help install start start-admin start-public stop stop-admin stop-public restart status logs license license-quick license-list clean

help:
	@echo "License Server - Make команды"
	@echo ""
	@echo "Управление серверами:"
	@echo "  make start            - Запустить оба сервера"
	@echo "  make start-admin      - Запустить admin сервер (:8081)"
	@echo "  make start-public     - Запустить public сервер (:8080)"
	@echo "  make stop             - Остановить оба сервера"
	@echo "  make stop-admin       - Остановить admin сервер"
	@echo "  make stop-public      - Остановить public сервер"
	@echo "  make restart          - Перезапустить оба сервера"
	@echo "  make status           - Показать статус серверов"
	@echo "  make logs             - Показать логи"
	@echo ""
	@echo "Лицензии:"
	@echo "  make license          - Создать лицензию (интерактивно)"
	@echo "  make license-quick    - Быстрое создание (DAYS=30 INSTANCES=1 NOTE=)"
	@echo "  make license-list     - Показать все лицензии"
	@echo ""
	@echo "Установка:"
	@echo "  make install          - Установить зависимости"
	@echo "  make clean            - Очистить логи и PID файлы"

install:
	@echo "Установка зависимостей..."
	@cd $(SERVER_DIR) && pip install -r requirements.txt
	@echo "Зависимости установлены!"

start-admin:
	@echo "Запуск admin сервера..."
	@mkdir -p $(DATA_DIR)
	@if [ -f $(ADMIN_PID) ] && kill -0 $$(cat $(ADMIN_PID)) 2>/dev/null; then \
		echo "Admin сервер уже запущен (PID: $$(cat $(ADMIN_PID)))"; \
	else \
		cd $(SERVER_DIR) && \
		pip install -q -r requirements.txt && \
		nohup python3 admin_server.py > $(DATA_DIR)/admin_server.log 2>&1 & \
		echo $$! > $(ADMIN_PID); \
		echo "Admin сервер запущен (PID: $$(cat $(ADMIN_PID)))"; \
		echo "Веб-интерфейс: http://127.0.0.1:8081"; \
	fi

start-public:
	@echo "Запуск public сервера..."
	@mkdir -p $(DATA_DIR)
	@if [ -f $(PUBLIC_PID) ] && kill -0 $$(cat $(PUBLIC_PID)) 2>/dev/null; then \
		echo "Public сервер уже запущен (PID: $$(cat $(PUBLIC_PID)))"; \
	else \
		cd $(SERVER_DIR) && \
		pip install -q -r requirements.txt && \
		nohup python3 public_server.py > $(DATA_DIR)/public_server.log 2>&1 & \
		echo $$! > $(PUBLIC_PID); \
		echo "Public сервер запущен (PID: $$(cat $(PUBLIC_PID)))"; \
		echo "API: http://0.0.0.0:8080"; \
	fi

start: start-admin start-public
	@echo ""
	@echo "Оба сервера запущены!"
	@echo "  Admin:  http://127.0.0.1:8081"
	@echo "  Public: http://0.0.0.0:8080"
	@echo ""
	@echo "Используйте 'make logs' для просмотра логов"
	@echo "Используйте 'make status' для проверки статуса"

stop-admin:
	@echo "Остановка admin сервера..."
	@if [ -f $(ADMIN_PID) ]; then \
		PID=$$(cat $(ADMIN_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			sleep 1; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Принудительная остановка..."; \
				kill -9 $$PID; \
			fi; \
			echo "Admin сервер остановлен"; \
		else \
			echo "Admin сервер не запущен"; \
		fi; \
		rm -f $(ADMIN_PID); \
	else \
		echo "Admin сервер не запущен"; \
	fi

stop-public:
	@echo "Остановка public сервера..."
	@if [ -f $(PUBLIC_PID) ]; then \
		PID=$$(cat $(PUBLIC_PID)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			sleep 1; \
			if kill -0 $$PID 2>/dev/null; then \
				echo "Принудительная остановка..."; \
				kill -9 $$PID; \
			fi; \
			echo "Public сервер остановлен"; \
		else \
			echo "Public сервер не запущен"; \
		fi; \
		rm -f $(PUBLIC_PID); \
	else \
		echo "Public сервер не запущен"; \
	fi

stop: stop-admin stop-public
	@pkill -f "python.*admin_server" 2>/dev/null || true
	@pkill -f "python.*public_server" 2>/dev/null || true
	@echo ""
	@echo "Оба сервера остановлены"

restart: stop start
	@echo "Серверы перезапущены"

status:
	@echo "=== Статус серверов ==="
	@echo ""
	@if [ -f $(ADMIN_PID) ] && kill -0 $$(cat $(ADMIN_PID)) 2>/dev/null; then \
		echo "Admin сервер:  ✅ запущен (PID: $$(cat $(ADMIN_PID))) - http://127.0.0.1:8081"; \
	else \
		echo "Admin сервер:  ❌ остановлен"; \
	fi
	@if [ -f $(PUBLIC_PID) ] && kill -0 $$(cat $(PUBLIC_PID)) 2>/dev/null; then \
		echo "Public сервер: ✅ запущен (PID: $$(cat $(PUBLIC_PID))) - http://0.0.0.0:8080"; \
	else \
		echo "Public сервер: ❌ остановлен"; \
	fi
	@echo ""

logs:
	@echo "=== Логи серверов ==="
	@echo ""
	@echo "--- Admin сервер (последние 20 строк) ---"
	@if [ -f $(DATA_DIR)/admin_server.log ]; then \
		tail -20 $(DATA_DIR)/admin_server.log; \
	else \
		echo "Лог файл не найден"; \
	fi
	@echo ""
	@echo "--- Public сервер (последние 20 строк) ---"
	@if [ -f $(DATA_DIR)/public_server.log ]; then \
		tail -20 $(DATA_DIR)/public_server.log; \
	else \
		echo "Лог файл не найден"; \
	fi

license:
	@cd $(SERVER_DIR) && python3 create_license.py create

license-quick:
	@cd $(SERVER_DIR) && python3 create_license.py create-quick --days $(DAYS) --instances $(INSTANCES) --note "$(NOTE)"

license-list:
	@cd $(SERVER_DIR) && python3 create_license.py list

clean: stop
	@echo "Очистка..."
	@rm -f $(DATA_DIR)/*.log
	@rm -f $(DATA_DIR)/*.pid
	@find $(PROJECT_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(PROJECT_DIR) -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Очистка завершена"
