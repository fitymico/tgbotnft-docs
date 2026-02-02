# NFT Gift Bot — Root Makefile
#
# make build          — собрать бинарник локально
# make build-remote   — собрать на удалённом сервере через SSH
# make release        — локальная сборка + пуш в release-репо
# make release-remote — сборка на удалённом сервере + пуш
# make release-all    — собрать локально + удалённо, запушить оба
#
# SSH-параметры (для remote-целей):
#   make build-remote SSH_HOST=user@1.2.3.4 SSH_PORT=22
#   Если не указаны — будут запрошены интерактивно.

RELEASE_REPO     = git@github.com:seventyzero/nft-gift-bot-release.git
RELEASE_CLONE    = .release-repo
FRONTEND_DIR     = Telegram-Bot-NFT
RELEASE_SRC_DIR  = nft-gift-bot-release
BINARY_NAME      = nft-gift-bot
REMOTE_BUILD_DIR = /tmp/nft-gift-bot-build

# SSH (можно задать: make build-remote SSH_HOST=user@host SSH_PORT=22)
SSH_HOST ?=
SSH_PORT ?= 22

# Локальная архитектура
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),x86_64)
  ARCH = amd64
else ifeq ($(UNAME_M),aarch64)
  ARCH = arm64
else ifeq ($(UNAME_M),arm64)
  ARCH = arm64
else
  ARCH = $(UNAME_M)
endif

.PHONY: build build-remote release release-remote release-all push clean

# ── Локальная сборка ─────────────────────────────────────────────────────────

build:
	@echo "==> Локальная сборка ($(ARCH))..."
	cd $(FRONTEND_DIR) && bash build.sh
	mkdir -p $(FRONTEND_DIR)/dist
	cp $(FRONTEND_DIR)/dist/$(BINARY_NAME) $(FRONTEND_DIR)/dist/$(BINARY_NAME)-linux-$(ARCH)
	@echo "==> Готово: $(FRONTEND_DIR)/dist/$(BINARY_NAME)-linux-$(ARCH)"

# ── Удалённая сборка ─────────────────────────────────────────────────────────

build-remote:
	@ssh_host="$(SSH_HOST)"; \
	ssh_port="$(SSH_PORT)"; \
	if [ -z "$$ssh_host" ]; then \
		printf "\033[1mSSH user@host\033[0m: "; read ssh_host; \
		printf "\033[1mSSH порт [22]\033[0m: "; read ssh_port; \
		ssh_port=$${ssh_port:-22}; \
	fi; \
	echo "==> Подключаюсь к $$ssh_host:$$ssh_port..."; \
	ssh -p $$ssh_port $$ssh_host "mkdir -p $(REMOTE_BUILD_DIR)"; \
	echo "==> Копирую исходники..."; \
	rsync -az --delete \
		--exclude='.build-venv' --exclude='dist' --exclude='build' \
		--exclude='__pycache__' --exclude='node_modules' --exclude='.git' \
		--exclude='Gift_API/node_modules' --exclude='data' \
		-e "ssh -p $$ssh_port" \
		$(FRONTEND_DIR)/ $$ssh_host:$(REMOTE_BUILD_DIR)/; \
	echo "==> Сборка на $$ssh_host..."; \
	ssh -p $$ssh_port $$ssh_host "cd $(REMOTE_BUILD_DIR) && bash build.sh"; \
	remote_arch=$$(ssh -p $$ssh_port $$ssh_host "uname -m"); \
	case "$$remote_arch" in \
		x86_64)        remote_arch="amd64" ;; \
		aarch64|arm64) remote_arch="arm64" ;; \
	esac; \
	echo "==> Скачиваю бинарник ($$remote_arch)..."; \
	mkdir -p $(FRONTEND_DIR)/dist; \
	scp -P $$ssh_port $$ssh_host:$(REMOTE_BUILD_DIR)/dist/$(BINARY_NAME) \
		$(FRONTEND_DIR)/dist/$(BINARY_NAME)-linux-$$remote_arch; \
	echo "==> Чищу удалённый сервер..."; \
	ssh -p $$ssh_port $$ssh_host "rm -rf $(REMOTE_BUILD_DIR)"; \
	echo "==> Готово: $(FRONTEND_DIR)/dist/$(BINARY_NAME)-linux-$$remote_arch"

# ── Release: подготовка репо + пуш ───────────────────────────────────────────

push:
	@echo "==> Подготовка release-репо..."
	@if [ -d "$(RELEASE_CLONE)/.git" ]; then \
		cd $(RELEASE_CLONE) && git pull --ff-only; \
	else \
		rm -rf $(RELEASE_CLONE); \
		git clone $(RELEASE_REPO) $(RELEASE_CLONE); \
	fi
	@echo "==> Копирую файлы..."
	cp $(RELEASE_SRC_DIR)/install.sh  $(RELEASE_CLONE)/
	cp $(RELEASE_SRC_DIR)/README.md   $(RELEASE_CLONE)/
	cp $(RELEASE_SRC_DIR)/.gitignore  $(RELEASE_CLONE)/
	@for f in $(FRONTEND_DIR)/dist/$(BINARY_NAME)-linux-*; do \
		if [ -f "$$f" ]; then \
			name=$$(basename $$f); \
			cp $$f $(RELEASE_CLONE)/$$name; \
			echo "    $$name"; \
		fi; \
	done
	@echo "==> Коммит и пуш..."
	cd $(RELEASE_CLONE) && \
		git add -A && \
		git diff --cached --quiet || \
		(git commit -m "release: $$(date +%Y-%m-%d_%H%M)" && git push)
	@echo "==> Готово: https://github.com/seventyzero/nft-gift-bot-release"

release: build push

release-remote: build-remote push

release-all: build build-remote push

# ── Очистка ──────────────────────────────────────────────────────────────────

clean:
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/build $(FRONTEND_DIR)/.build-venv
	rm -rf $(RELEASE_CLONE)
