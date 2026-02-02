# NFT Gift Bot — Root Makefile
#
# make build    — собрать бинарник Frontend (PyInstaller)
# make release  — собрать + запушить в seventyzero/nft-gift-bot-release

RELEASE_REPO     = git@github.com:seventyzero/nft-gift-bot-release.git
RELEASE_CLONE    = .release-repo
FRONTEND_DIR     = Telegram-Bot-NFT
RELEASE_SRC_DIR  = nft-gift-bot-release
BINARY_NAME      = nft-gift-bot

.PHONY: build release release-push clean

build:
	@echo "==> Сборка бинарника..."
	cd $(FRONTEND_DIR) && bash build.sh
	@echo "==> Бинарник: $(FRONTEND_DIR)/dist/$(BINARY_NAME)"

release: build
	@echo "==> Подготовка release-репо..."
	@if [ -d "$(RELEASE_CLONE)/.git" ]; then \
		cd $(RELEASE_CLONE) && git pull --ff-only; \
	else \
		rm -rf $(RELEASE_CLONE); \
		git clone $(RELEASE_REPO) $(RELEASE_CLONE); \
	fi
	@echo "==> Копирую файлы..."
	cp $(RELEASE_SRC_DIR)/install.sh     $(RELEASE_CLONE)/
	cp $(RELEASE_SRC_DIR)/README.md      $(RELEASE_CLONE)/
	cp $(RELEASE_SRC_DIR)/.gitignore     $(RELEASE_CLONE)/
	cp $(FRONTEND_DIR)/dist/$(BINARY_NAME) $(RELEASE_CLONE)/$(BINARY_NAME)-linux-amd64
	@echo "==> Коммит и пуш..."
	cd $(RELEASE_CLONE) && \
		git add -A && \
		git diff --cached --quiet || \
		(git commit -m "release: update $$(date +%Y-%m-%d_%H%M)" && git push)
	@echo "==> Готово: https://github.com/seventyzero/nft-gift-bot-release"

clean:
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/build $(FRONTEND_DIR)/.build-venv
	rm -rf $(RELEASE_CLONE)
