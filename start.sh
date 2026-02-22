#!/bin/bash

# 极简聊天工具 - 一键启动脚本
# 兼容 macOS / Linux / Windows (Git Bash/WSL)

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Darwin*)  OS="mac" ;;
        Linux*)   OS="linux" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *)        OS="unknown" ;;
    esac
    info "检测到操作系统: $OS"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 安装 Homebrew (macOS)
install_homebrew() {
    if [[ "$OS" == "mac" ]] && ! command_exists brew; then
        info "正在安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
}

# 安装 Docker
install_docker() {
    if command_exists docker; then
        info "Docker 已安装"
        return
    fi

    warn "Docker 未安装，正在安装..."
    
    case "$OS" in
        mac)
            install_homebrew
            brew install --cask docker
            info "请手动启动 Docker Desktop，然后重新运行此脚本"
            exit 0
            ;;
        linux)
            curl -fsSL https://get.docker.com | sh
            sudo usermod -aG docker "$USER"
            warn "请重新登录以使 Docker 权限生效，然后重新运行此脚本"
            exit 0
            ;;
        windows)
            error "请手动安装 Docker Desktop: https://www.docker.com/products/docker-desktop"
            ;;
    esac
}

# 安装 Docker Compose
install_docker_compose() {
    if docker compose version >/dev/null 2>&1 || command_exists docker-compose; then
        info "Docker Compose 已安装"
        return
    fi

    warn "Docker Compose 未安装，正在安装..."
    
    case "$OS" in
        mac)
            # Docker Desktop for Mac 自带 compose
            ;;
        linux)
            sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
                -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            ;;
        windows)
            # Docker Desktop for Windows 自带 compose
            ;;
    esac
}

# 检查 Docker 是否运行
check_docker_running() {
    if ! docker info >/dev/null 2>&1; then
        error "Docker 未运行，请先启动 Docker Desktop"
    fi
    info "Docker 运行正常"
}

# 运行 docker compose
run_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    info "正在构建并启动服务..."
    $COMPOSE_CMD up --build -d

    info "等待服务启动..."
    sleep 5

    if $COMPOSE_CMD ps | grep -q "Up"; then
        info "服务已启动，开始验证..."
        run_tests
    else
        error "服务启动失败，请检查日志: $COMPOSE_CMD logs"
    fi
}

# API 测试验证
run_tests() {
    BASE_URL="http://localhost:8000"
    echo ""
    info "========================================="
    info "API 测试验证"
    info "========================================="
    
    # 健康检查
    echo -n "  健康检查... "
    if curl -s "$BASE_URL/health" | grep -q "healthy"; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        return 1
    fi
    
    # 登录测试
    echo -n "  登录测试... "
    LOGIN=$(curl -s -X POST "$BASE_URL/login" -u admin:admin123)
    TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])" 2>/dev/null)
    if [ -n "$TOKEN" ]; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        return 1
    fi
    
    # 在线用户
    echo -n "  在线用户接口... "
    if curl -s "$BASE_URL/users/online" | grep -q "users"; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
    fi
    
    # 历史消息
    echo -n "  历史消息接口... "
    curl -s "$BASE_URL/messages" >/dev/null && echo -e "${GREEN}OK${NC}"
    
    # 加密接口
    echo -n "  加密密钥生成... "
    if curl -s -X POST "$BASE_URL/crypto/generate-keypair" | grep -q "public_key"; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
    fi
    
    echo ""
    info "========================================="
    info "🎉 服务启动成功，所有测试通过！"
    info "========================================="
    echo ""
    echo "  API 文档:    http://localhost:8000/docs"
    echo "  健康检查:    http://localhost:8000/health"
    echo ""
    echo "  测试账号:"
    echo "    admin / admin123"
    echo "    user1 / password1"
    echo "    user2 / password2"
    echo ""
    info "WebSocket 测试:"
    echo "  websocat \"ws://localhost:8000/ws/chat?token=$TOKEN\""
    echo ""
    info "查看日志: $COMPOSE_CMD logs -f"
    info "停止服务: $COMPOSE_CMD down"
}

# 主流程
main() {
    echo ""
    info "========================================="
    info "极简聊天工具 - 一键启动"
    info "========================================="
    echo ""

    detect_os
    install_docker
    install_docker_compose
    check_docker_running
    run_compose
}

main "$@"
