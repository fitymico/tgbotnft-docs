#!/usr/bin/env bash
# ============================================================================
#  NFT Gift Bot — Self-Host Installer
#
#  Usage:
#    curl -fsSL https://your-domain.com/install.sh | bash
#    wget -qO- https://your-domain.com/install.sh | bash
#
#  Два режима установки:
#    1. Docker (рекомендуется) — ставит Docker, собирает образ, запускает
#    2. Bare metal — ставит Python, venv, systemd-сервис
#
#  Supported:
#    Ubuntu 20.04+ / Debian 11+
#    CentOS 8+ / RHEL 8+ / Rocky / Alma
#    Fedora 36+
#    Arch Linux
#    Alpine 3.17+
#    openSUSE Leap 15.4+ / Tumbleweed
# ============================================================================

set -euo pipefail

# ── Colours & helpers ────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
die()   { err "$*"; exit 1; }

ask() {
    local prompt="$1" default="${2:-}" value
    if [[ -n "$default" ]]; then
        printf "${BOLD}%s${NC} [%s]: " "$prompt" "$default"
    else
        printf "${BOLD}%s${NC}: " "$prompt"
    fi
    read -r value
    echo "${value:-$default}"
}

ask_choice() {
    local prompt="$1"
    shift
    local options=("$@")
    echo
    printf "${BOLD}%s${NC}\n" "$prompt"
    for i in "${!options[@]}"; do
        printf "  ${CYAN}%d${NC}) %s\n" "$((i + 1))" "${options[$i]}"
    done
    local choice
    while true; do
        printf "${BOLD}Выбор [1-%d]${NC}: " "${#options[@]}"
        read -r choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
            echo "$choice"
            return
        fi
        echo "  Введите число от 1 до ${#options[@]}"
    done
}

# ── Globals ──────────────────────────────────────────────────────────────────

INSTALL_DIR="/opt/nft-gift-bot"
SERVICE_NAME="nft-gift-bot"
CONTAINER_NAME="nft-gift-bot"
IMAGE_NAME="nft-gift-bot"
VENV_DIR="$INSTALL_DIR/venv"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10
RELEASE_URL="${RELEASE_URL:-}"
DISTRO=""
INSTALL_MODE=""  # "docker" or "bare"

# config values
CFG_BOT_TOKEN=""
CFG_ADMIN_ID=""
CFG_LICENSE_KEY=""
CFG_API_ID=""
CFG_API_HASH=""
CFG_SESSION_STRING=""
CFG_UDP_PORT=""

# ── Detect distribution ──────────────────────────────────────────────────────

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        case "${ID:-}" in
            ubuntu|debian|linuxmint|pop)       DISTRO="debian"  ;;
            centos|rhel|rocky|almalinux)       DISTRO="rhel"    ;;
            fedora)                            DISTRO="fedora"  ;;
            arch|manjaro|endeavouros)          DISTRO="arch"    ;;
            alpine)                            DISTRO="alpine"  ;;
            opensuse*|sles)                    DISTRO="suse"    ;;
            *)
                warn "Неизвестный дистрибутив: ${ID:-unknown}"
                detect_distro_by_pm
                ;;
        esac
    else
        detect_distro_by_pm
    fi

    if [[ -z "$DISTRO" ]]; then
        die "Не удалось определить дистрибутив. Установите зависимости вручную."
    fi

    info "Дистрибутив: $DISTRO"
}

detect_distro_by_pm() {
    if command -v apt-get &>/dev/null; then
        DISTRO="debian"
    elif command -v dnf &>/dev/null; then
        DISTRO="fedora"
    elif command -v yum &>/dev/null; then
        DISTRO="rhel"
    elif command -v pacman &>/dev/null; then
        DISTRO="arch"
    elif command -v apk &>/dev/null; then
        DISTRO="alpine"
    elif command -v zypper &>/dev/null; then
        DISTRO="suse"
    fi
}

# ── Install curl (minimal prereq) ───────────────────────────────────────────

ensure_curl() {
    if command -v curl &>/dev/null; then
        return
    fi
    info "Устанавливаю curl..."
    case "$DISTRO" in
        debian)  apt-get update -qq && apt-get install -y -qq curl >/dev/null 2>&1 ;;
        fedora)  dnf install -y -q curl >/dev/null 2>&1 ;;
        rhel)    yum install -y -q curl >/dev/null 2>&1 ;;
        arch)    pacman -Sy --noconfirm curl >/dev/null 2>&1 ;;
        alpine)  apk add -q curl >/dev/null 2>&1 ;;
        suse)    zypper -q install -y curl >/dev/null 2>&1 ;;
    esac
}

# ══════════════════════════════════════════════════════════════════════════════
#                          DOCKER INSTALLATION
# ══════════════════════════════════════════════════════════════════════════════

install_docker() {
    if command -v docker &>/dev/null; then
        ok "Docker уже установлен: $(docker --version)"
        return
    fi

    info "Устанавливаю Docker..."

    case "$DISTRO" in
        debian|fedora)
            # Official Docker install script (supports Debian, Ubuntu, Fedora)
            curl -fsSL https://get.docker.com | sh
            ;;
        rhel)
            if command -v dnf &>/dev/null; then
                dnf install -y -q dnf-plugins-core >/dev/null 2>&1
                dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null
                dnf install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null 2>&1
            else
                yum install -y -q yum-utils >/dev/null 2>&1
                yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null
                yum install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin >/dev/null 2>&1
            fi
            ;;
        arch)
            pacman -Sy --noconfirm docker docker-compose >/dev/null 2>&1
            ;;
        alpine)
            apk add -q docker docker-compose >/dev/null 2>&1
            ;;
        suse)
            zypper -q install -y docker docker-compose >/dev/null 2>&1
            ;;
    esac

    # Start & enable Docker
    if command -v systemctl &>/dev/null; then
        systemctl start docker 2>/dev/null || true
        systemctl enable docker 2>/dev/null || true
    elif command -v rc-service &>/dev/null; then
        rc-service docker start 2>/dev/null || true
        rc-update add docker default 2>/dev/null || true
    fi

    # Verify
    if ! command -v docker &>/dev/null; then
        die "Docker не удалось установить. Установите Docker вручную: https://docs.docker.com/engine/install/"
    fi

    ok "Docker установлен: $(docker --version)"
}

install_docker_compose() {
    # Check for docker compose (v2 plugin) or docker-compose (v1 standalone)
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        ok "Docker Compose (plugin): $(docker compose version --short 2>/dev/null)"
        return
    fi

    if command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
        ok "docker-compose: $(docker-compose --version 2>/dev/null)"
        return
    fi

    info "Устанавливаю Docker Compose plugin..."

    case "$DISTRO" in
        debian|fedora|rhel)
            # Try installing plugin package
            if command -v apt-get &>/dev/null; then
                apt-get install -y -qq docker-compose-plugin >/dev/null 2>&1 || true
            elif command -v dnf &>/dev/null; then
                dnf install -y -q docker-compose-plugin >/dev/null 2>&1 || true
            elif command -v yum &>/dev/null; then
                yum install -y -q docker-compose-plugin >/dev/null 2>&1 || true
            fi
            ;;
    esac

    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        ok "Docker Compose plugin установлен"
        return
    fi

    # Fallback: standalone binary
    info "Скачиваю docker-compose standalone..."
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="x86_64" ;;
        aarch64) arch="aarch64" ;;
        armv7l)  arch="armv7" ;;
        *)       die "Архитектура $arch не поддерживается для docker-compose" ;;
    esac
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${arch}" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    COMPOSE_CMD="docker-compose"
    ok "docker-compose установлен"
}

setup_project_docker() {
    info "Подготавливаю проект для Docker..."

    mkdir -p "$INSTALL_DIR"

    if [[ -n "$RELEASE_URL" ]]; then
        info "Скачиваю из $RELEASE_URL ..."
        local tmpfile="/tmp/nft-gift-bot-release.tar.gz"
        curl -fsSL "$RELEASE_URL" -o "$tmpfile"
        tar -xzf "$tmpfile" -C "$INSTALL_DIR" --strip-components=1
        rm -f "$tmpfile"
    elif [[ -f "$(dirname "${BASH_SOURCE[0]}")/config.py" ]]; then
        info "Копирую из каталога проекта..."
        local src
        src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        cp "$src/config.py" "$INSTALL_DIR/"
        cp "$src/requirements.txt" "$INSTALL_DIR/"
        mkdir -p "$INSTALL_DIR/Message_Bot"
        cp "$src"/Message_Bot/*.py "$INSTALL_DIR/Message_Bot/"
        if [[ -d "$src/docker" ]]; then
            cp -r "$src/docker" "$INSTALL_DIR/"
        fi
    else
        die "Не найден исходный код. Укажите RELEASE_URL или запустите из каталога проекта."
    fi

    # Ensure Dockerfile exists
    if [[ ! -f "$INSTALL_DIR/docker/Dockerfile" ]]; then
        mkdir -p "$INSTALL_DIR/docker"
        cat > "$INSTALL_DIR/docker/Dockerfile" <<'DOCKEOF'
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY Message_Bot ./Message_Bot
COPY config.py ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "Message_Bot/talkbot.py"]
DOCKEOF
    fi

    ok "Файлы проекта готовы"
}

write_docker_compose() {
    cat > "$INSTALL_DIR/docker-compose.yml" <<COMPEOF
version: "3.8"

services:
  nft-gift-bot:
    build:
      context: .
      dockerfile: docker/Dockerfile
    image: ${IMAGE_NAME}:latest
    container_name: ${CONTAINER_NAME}
    restart: unless-stopped
    env_file: .env
    ports:
      - "${CFG_UDP_PORT}:${CFG_UDP_PORT}/udp"
    volumes:
      - ./data:/app/data
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
COMPEOF

    ok "docker-compose.yml создан"
}

build_and_start_docker() {
    info "Собираю Docker-образ..."
    cd "$INSTALL_DIR"
    $COMPOSE_CMD build --quiet

    info "Запускаю контейнер..."
    $COMPOSE_CMD up -d

    # Verify running
    sleep 2
    if $COMPOSE_CMD ps | grep -q "Up\|running"; then
        ok "Контейнер запущен"
    else
        warn "Контейнер может быть не запущен. Проверьте: cd $INSTALL_DIR && $COMPOSE_CMD logs"
    fi
}

docker_install_flow() {
    install_docker
    install_docker_compose
    setup_project_docker
    collect_config
    write_env
    write_docker_compose
    mkdir -p "$INSTALL_DIR/data"
    open_firewall
    build_and_start_docker
    create_docker_uninstall
    print_docker_summary
}

create_docker_uninstall() {
    cat > "$INSTALL_DIR/uninstall.sh" <<UNEOF
#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$INSTALL_DIR"
COMPOSE_CMD="$COMPOSE_CMD"

echo "Останавливаю контейнер..."
cd "\$INSTALL_DIR"
\$COMPOSE_CMD down --rmi local 2>/dev/null || true

echo "Удаляю файлы..."
rm -rf "\$INSTALL_DIR"

echo "Docker Gift Bot удалён."
echo "Docker остаётся установленным в системе."
UNEOF

    chmod +x "$INSTALL_DIR/uninstall.sh"
}

print_docker_summary() {
    local ext_ip
    ext_ip=$(curl -fsSL --max-time 5 https://api.ipify.org 2>/dev/null || echo "не определён")

    echo
    printf "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}\n"
    printf "${BOLD}${GREEN}     Установка завершена! (Docker)                ${NC}\n"
    printf "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}\n"
    echo
    echo "  Каталог:        $INSTALL_DIR"
    echo "  Конфиг:         $INSTALL_DIR/.env"
    echo "  Docker Compose: $INSTALL_DIR/docker-compose.yml"
    echo "  Удаление:       sudo bash $INSTALL_DIR/uninstall.sh"
    echo
    printf "${BOLD}${YELLOW}  !  Важно: сообщите в Service-Bot ваш адрес:${NC}\n"
    echo
    printf "     ${BOLD}IP:   ${ext_ip}${NC}\n"
    printf "     ${BOLD}Порт: ${CFG_UDP_PORT}${NC}\n"
    echo
    echo "  Отправьте эти данные в Service-Bot, чтобы"
    echo "  сервер мог отправлять вам информацию о подарках."
    echo
    printf "${CYAN}  Управление:${NC}\n"
    echo "    cd $INSTALL_DIR"
    echo "    $COMPOSE_CMD logs -f          # логи"
    echo "    $COMPOSE_CMD restart           # перезапуск"
    echo "    $COMPOSE_CMD down              # остановка"
    echo "    $COMPOSE_CMD up -d             # запуск"
    echo "    $COMPOSE_CMD up -d --build     # пересборка и запуск"
    echo
    printf "${CYAN}  Изменение настроек:${NC}\n"
    echo "    1. Отредактируйте $INSTALL_DIR/.env"
    echo "    2. $COMPOSE_CMD up -d --force-recreate"
    echo
}

# ══════════════════════════════════════════════════════════════════════════════
#                        BARE METAL INSTALLATION
# ══════════════════════════════════════════════════════════════════════════════

install_system_packages() {
    info "Устанавливаю системные зависимости..."

    case "$DISTRO" in
        debian)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -qq
            apt-get install -y -qq python3 python3-venv python3-pip curl >/dev/null 2>&1
            ;;
        fedora)
            dnf install -y -q python3 python3-pip curl >/dev/null 2>&1
            ;;
        rhel)
            if command -v dnf &>/dev/null; then
                dnf install -y -q python3 python3-pip curl >/dev/null 2>&1
            else
                yum install -y -q python3 python3-pip curl >/dev/null 2>&1
            fi
            ;;
        arch)
            pacman -Sy --noconfirm --needed python python-pip curl >/dev/null 2>&1
            ;;
        alpine)
            apk update -q
            apk add -q python3 py3-pip curl bash >/dev/null 2>&1
            ;;
        suse)
            zypper -q install -y python3 python3-pip curl >/dev/null 2>&1
            ;;
    esac

    ok "Системные зависимости установлены"
}

check_python() {
    local py=""
    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" &>/dev/null; then
            py="$candidate"
            break
        fi
    done

    if [[ -z "$py" ]]; then
        die "Python 3 не найден. Установите Python >= ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}"
    fi

    local version major minor
    version=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)

    if (( major < PYTHON_MIN_MAJOR || (major == PYTHON_MIN_MAJOR && minor < PYTHON_MIN_MINOR) )); then
        die "Python $version слишком старый. Требуется >= ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}"
    fi

    PYTHON="$py"
    ok "Python: $($PYTHON --version)"
}

setup_project_bare() {
    info "Устанавливаю проект в $INSTALL_DIR ..."

    mkdir -p "$INSTALL_DIR"

    if [[ -n "$RELEASE_URL" ]]; then
        info "Скачиваю из $RELEASE_URL ..."
        local tmpfile="/tmp/nft-gift-bot-release.tar.gz"
        curl -fsSL "$RELEASE_URL" -o "$tmpfile"
        tar -xzf "$tmpfile" -C "$INSTALL_DIR" --strip-components=1
        rm -f "$tmpfile"
    elif [[ -f "$(dirname "${BASH_SOURCE[0]}")/config.py" ]]; then
        info "Копирую из каталога проекта..."
        local src
        src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        cp "$src/config.py" "$INSTALL_DIR/"
        cp "$src/requirements.txt" "$INSTALL_DIR/"
        mkdir -p "$INSTALL_DIR/Message_Bot"
        cp "$src"/Message_Bot/*.py "$INSTALL_DIR/Message_Bot/"
    else
        die "Не найден исходный код. Укажите RELEASE_URL или запустите из каталога проекта."
    fi

    ok "Файлы проекта установлены"
}

setup_venv() {
    info "Создаю виртуальное окружение..."

    $PYTHON -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q

    ok "Python-зависимости установлены"
}

create_systemd_service() {
    if ! command -v systemctl &>/dev/null; then
        warn "systemd не найден — пропускаю создание сервиса."
        warn "Запускайте вручную: $VENV_DIR/bin/python $INSTALL_DIR/Message_Bot/talkbot.py"
        return
    fi

    info "Создаю systemd-сервис..."

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SVCEOF
[Unit]
Description=NFT Gift Bot (Self-Host)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/Message_Bot/talkbot.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
    systemctl restart "$SERVICE_NAME"

    ok "Сервис '$SERVICE_NAME' создан и запущен"
}

create_openrc_service() {
    if ! command -v rc-service &>/dev/null; then
        return
    fi

    info "Создаю OpenRC-сервис..."

    cat > "/etc/init.d/${SERVICE_NAME}" <<RCEOF
#!/sbin/openrc-run

name="NFT Gift Bot"
description="NFT Gift Bot (Self-Host)"
command="$VENV_DIR/bin/python"
command_args="$INSTALL_DIR/Message_Bot/talkbot.py"
command_background=true
pidfile="/run/\${RC_SVCNAME}.pid"
directory="$INSTALL_DIR"
output_log="/var/log/\${RC_SVCNAME}.log"
error_log="/var/log/\${RC_SVCNAME}.err"

depend() {
    need net
}

start_pre() {
    export \$(grep -v '^#' $INSTALL_DIR/.env | xargs)
}
RCEOF

    chmod +x "/etc/init.d/${SERVICE_NAME}"
    rc-update add "$SERVICE_NAME" default 2>/dev/null
    rc-service "$SERVICE_NAME" restart 2>/dev/null

    ok "OpenRC-сервис '$SERVICE_NAME' создан и запущен"
}

create_bare_service() {
    if command -v systemctl &>/dev/null; then
        create_systemd_service
    elif command -v rc-service &>/dev/null; then
        create_openrc_service
    else
        warn "Ни systemd, ни OpenRC не обнаружены."
        warn "Запускайте вручную:"
        warn "  cd $INSTALL_DIR && source .env && $VENV_DIR/bin/python Message_Bot/talkbot.py"
    fi
}

create_bare_uninstall() {
    cat > "$INSTALL_DIR/uninstall.sh" <<'UNEOF'
#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="nft-gift-bot"
INSTALL_DIR="/opt/nft-gift-bot"

echo "Удаляю NFT Gift Bot..."

if command -v systemctl &>/dev/null; then
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload 2>/dev/null || true
fi

if command -v rc-service &>/dev/null; then
    rc-service "$SERVICE_NAME" stop 2>/dev/null || true
    rc-update del "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/init.d/${SERVICE_NAME}"
fi

rm -rf "$INSTALL_DIR"
echo "NFT Gift Bot удалён."
UNEOF

    chmod +x "$INSTALL_DIR/uninstall.sh"
}

print_bare_summary() {
    local ext_ip
    ext_ip=$(curl -fsSL --max-time 5 https://api.ipify.org 2>/dev/null || echo "не определён")

    echo
    printf "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}\n"
    printf "${BOLD}${GREEN}     Установка завершена! (Bare Metal)            ${NC}\n"
    printf "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}\n"
    echo
    echo "  Каталог:   $INSTALL_DIR"
    echo "  Конфиг:    $INSTALL_DIR/.env"
    echo "  Сервис:    $SERVICE_NAME"
    echo "  Удаление:  sudo bash $INSTALL_DIR/uninstall.sh"
    echo
    printf "${BOLD}${YELLOW}  !  Важно: сообщите в Service-Bot ваш адрес:${NC}\n"
    echo
    printf "     ${BOLD}IP:   ${ext_ip}${NC}\n"
    printf "     ${BOLD}Порт: ${CFG_UDP_PORT}${NC}\n"
    echo
    echo "  Отправьте эти данные в Service-Bot, чтобы"
    echo "  сервер мог отправлять вам информацию о подарках."
    echo
    printf "${CYAN}  Управление:${NC}\n"
    echo "    sudo systemctl status  $SERVICE_NAME    # статус"
    echo "    sudo systemctl restart $SERVICE_NAME    # перезапуск"
    echo "    sudo systemctl stop    $SERVICE_NAME    # остановка"
    echo "    sudo journalctl -u $SERVICE_NAME -f     # логи"
    echo
    printf "${CYAN}  Изменение настроек:${NC}\n"
    echo "    1. Отредактируйте $INSTALL_DIR/.env"
    echo "    2. sudo systemctl restart $SERVICE_NAME"
    echo
}

bare_install_flow() {
    install_system_packages
    check_python
    setup_project_bare
    setup_venv
    collect_config
    write_env
    mkdir -p "$INSTALL_DIR/data"
    open_firewall
    create_bare_service
    create_bare_uninstall
    print_bare_summary
}

# ══════════════════════════════════════════════════════════════════════════════
#                          SHARED FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

collect_config() {
    echo
    printf "${BOLD}${CYAN}══════════════════════════════════════════════════${NC}\n"
    printf "${BOLD}${CYAN}          Настройка NFT Gift Bot                  ${NC}\n"
    printf "${BOLD}${CYAN}══════════════════════════════════════════════════${NC}\n"
    echo

    # Load existing config if present
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        warn "Найден существующий .env — значения будут использованы как умолчания"
        set +u
        source "$INSTALL_DIR/.env" 2>/dev/null || true
        set -u
    fi

    echo "  1/6. Telegram Bot"
    echo "       Создайте бота через @BotFather и скопируйте токен."
    CFG_BOT_TOKEN=$(ask "       BOT_TOKEN" "${BOT_TOKEN:-}")
    [[ -z "$CFG_BOT_TOKEN" ]] && die "BOT_TOKEN обязателен"
    echo

    echo "  2/6. Telegram ID владельца"
    echo "       Узнайте свой ID через @userinfobot или @getmyid_bot."
    CFG_ADMIN_ID=$(ask "       ADMIN_ID" "${ADMIN_ID:-}")
    [[ -z "$CFG_ADMIN_ID" ]] && die "ADMIN_ID обязателен"
    echo

    echo "  3/6. Лицензионный ключ"
    echo "       Получен после оплаты SELF-HOST подписки в Service-Bot."
    CFG_LICENSE_KEY=$(ask "       LICENSE_KEY" "${LICENSE_KEY:-}")
    [[ -z "$CFG_LICENSE_KEY" ]] && die "LICENSE_KEY обязателен"
    echo

    echo "  4/6. Telegram API (https://my.telegram.org → API development tools)"
    CFG_API_ID=$(ask "       API_ID" "${API_ID:-}")
    CFG_API_HASH=$(ask "       API_HASH" "${API_HASH:-}")
    [[ -z "$CFG_API_ID" || -z "$CFG_API_HASH" ]] && die "API_ID и API_HASH обязательны"
    echo

    echo "  5/6. Session String"
    echo "       Получена при авторизации через веб-страницу Service-Bot."
    CFG_SESSION_STRING=$(ask "       SESSION_STRING" "${SESSION_STRING:-}")
    [[ -z "$CFG_SESSION_STRING" ]] && die "SESSION_STRING обязателен"
    echo

    echo "  6/6. UDP порт для приёма данных от сервера"
    echo "       Убедитесь, что порт открыт в файрволе (UDP)."
    CFG_UDP_PORT=$(ask "       UDP_LISTEN_PORT" "${UDP_LISTEN_PORT:-9200}")
    echo
}

write_env() {
    cat > "$INSTALL_DIR/.env" <<ENVEOF
# NFT Gift Bot — Self-Host Configuration
# Generated by install.sh at $(date -Iseconds 2>/dev/null || date)

BOT_TOKEN=${CFG_BOT_TOKEN}
ADMIN_ID=${CFG_ADMIN_ID}
LICENSE_KEY=${CFG_LICENSE_KEY}
API_ID=${CFG_API_ID}
API_HASH=${CFG_API_HASH}
SESSION_STRING=${CFG_SESSION_STRING}
UDP_LISTEN_HOST=0.0.0.0
UDP_LISTEN_PORT=${CFG_UDP_PORT}
ENVEOF

    chmod 600 "$INSTALL_DIR/.env"
    ok "Конфигурация сохранена в $INSTALL_DIR/.env"
}

open_firewall() {
    info "Открываю UDP-порт $CFG_UDP_PORT ..."

    local opened=false

    if command -v ufw &>/dev/null && ufw status 2>/dev/null | grep -q "active"; then
        ufw allow "${CFG_UDP_PORT}/udp" >/dev/null 2>&1 && opened=true
    fi

    if ! $opened && command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
        firewall-cmd --permanent --add-port="${CFG_UDP_PORT}/udp" >/dev/null 2>&1
        firewall-cmd --reload >/dev/null 2>&1
        opened=true
    fi

    if ! $opened && command -v iptables &>/dev/null; then
        if ! iptables -C INPUT -p udp --dport "$CFG_UDP_PORT" -j ACCEPT 2>/dev/null; then
            iptables -A INPUT -p udp --dport "$CFG_UDP_PORT" -j ACCEPT 2>/dev/null && opened=true
        else
            opened=true  # already open
        fi
    fi

    if $opened; then
        ok "UDP-порт $CFG_UDP_PORT открыт"
    else
        warn "Не удалось автоматически открыть порт. Откройте UDP $CFG_UDP_PORT вручную."
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
#                              MAIN
# ══════════════════════════════════════════════════════════════════════════════

main() {
    echo
    printf "${BOLD}${CYAN}══════════════════════════════════════════════════${NC}\n"
    printf "${BOLD}${CYAN}    NFT Gift Bot — Self-Host Installer            ${NC}\n"
    printf "${BOLD}${CYAN}══════════════════════════════════════════════════${NC}\n"
    echo

    # Check root
    if [[ $EUID -ne 0 ]]; then
        die "Запустите скрипт от root:\n  sudo bash install.sh"
    fi

    detect_distro
    ensure_curl

    # Choose install mode
    local choice
    choice=$(ask_choice \
        "Выберите способ установки:" \
        "Docker (рекомендуется) — изолированный контейнер, простое управление" \
        "Bare Metal — Python + venv + systemd, без Docker"
    )

    case "$choice" in
        1) INSTALL_MODE="docker" ;;
        2) INSTALL_MODE="bare"   ;;
    esac

    info "Режим установки: $INSTALL_MODE"
    echo

    case "$INSTALL_MODE" in
        docker) docker_install_flow ;;
        bare)   bare_install_flow   ;;
    esac
}

main "$@"
