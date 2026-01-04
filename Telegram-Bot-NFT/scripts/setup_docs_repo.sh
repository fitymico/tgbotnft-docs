#!/bin/bash

# setup_docs_repo.sh
# Инициализация docs как отдельного git репозитория

DOCS_DIR="$(pwd)/docs"
REMOTE_URL="https://github.com/pluttan/Telegram-Bot-NFT-docs.git"

echo "📦 Подготовка docs как отдельного репозитория..."

if [ ! -d "$DOCS_DIR" ]; then
    echo "❌ Директория docs не найдена!"
    exit 1
fi

cd "$DOCS_DIR" || exit

# Инициализация git если еще нет
if [ ! -d ".git" ]; then
    echo "git init..."
    git init
    git branch -M main
else
    echo "git уже инициализирован в docs"
fi

# Проверка remote
if git remote | grep -q "origin"; then
    echo "Remote origin уже существует"
    git remote set-url origin "$REMOTE_URL"
    echo "Remote origin обновлен на $REMOTE_URL"
else
    git remote add origin "$REMOTE_URL"
    echo "Remote origin добавлен: $REMOTE_URL"
fi

# Игнорирование в основном репозитории (если docs там отслеживается)
# Это нужно делать в корне, но мы сейчас в docs
# cd ..
# if grep -q "docs/" .gitignore; then
#    echo "docs/ уже в .gitignore основного репозитория"
# else
#    echo "docs/" >> .gitignore
#    echo "Добавлено docs/ в .gitignore основного репозитория"
# fi

echo ""
echo "✅ Репозиторий готов!"
echo ""
echo "Для отправки кода выполните:"
echo "  cd docs"
echo "  git add ."
echo "  git commit -m \"Initial docs commit\""
echo "  git push -u origin main --force"
echo ""
