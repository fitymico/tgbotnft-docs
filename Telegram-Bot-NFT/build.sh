#!/usr/bin/env bash
# ============================================================================
#  NFT Gift Bot — Build Script
#
#  Produces a single Linux binary using PyInstaller.
#
#  Prerequisites:
#    - Python 3.10+
#    - pip install pyinstaller
#    - pip install -r requirements.txt
#
#  Usage:
#    ./build.sh                    # build with auto-detected Python
#    PYTHON=python3.12 ./build.sh  # build with specific Python
#
#  Output:
#    dist/nft-gift-bot             # standalone Linux binary (~60-80 MB)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
err()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; exit 1; }

# ── Find Python ──────────────────────────────────────────────────────────────

PYTHON="${PYTHON:-}"

if [[ -z "$PYTHON" ]]; then
    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    done
fi

[[ -z "$PYTHON" ]] && err "Python 3.10+ не найден. Установите Python или задайте PYTHON=..."

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 10) )); then
    err "Python $PY_VERSION слишком старый. Требуется >= 3.10"
fi

info "Python: $("$PYTHON" --version)"

# ── Setup build venv ─────────────────────────────────────────────────────────

BUILD_VENV="$SCRIPT_DIR/.build-venv"

if [[ ! -d "$BUILD_VENV" ]]; then
    info "Создаю виртуальное окружение для сборки..."
    "$PYTHON" -m venv "$BUILD_VENV"
fi

PIP="$BUILD_VENV/bin/pip"
PYINSTALLER="$BUILD_VENV/bin/pyinstaller"

info "Устанавливаю зависимости..."
"$PIP" install --upgrade pip -q
"$PIP" install -r requirements.txt -q
"$PIP" install pyinstaller -q

# ── Build ────────────────────────────────────────────────────────────────────

info "Собираю бинарник..."
"$PYINSTALLER" nft-gift-bot.spec --noconfirm --clean 2>&1 | tail -5

# ── Result ───────────────────────────────────────────────────────────────────

BINARY="$SCRIPT_DIR/dist/nft-gift-bot"

if [[ -f "$BINARY" ]]; then
    SIZE=$(du -sh "$BINARY" | cut -f1)
    ok "Бинарник собран: $BINARY ($SIZE)"
    echo
    printf "${BOLD}Использование:${NC}\n"
    echo "  1. Скопируйте '$BINARY' на целевой сервер"
    echo "  2. Создайте .env файл рядом с бинарником"
    echo "  3. Запустите: ./nft-gift-bot"
    echo
else
    err "Сборка не удалась. Проверьте вывод PyInstaller выше."
fi
