#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_ZH_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DOCS_ZH_DIR")"
PERFETTO_DIR="${PERFETTO_DIR:-$PROJECT_ROOT/perfetto}"
LAST_SYNC_FILE="$SCRIPT_DIR/LAST_SYNC"
TOOL_NAME="$(basename "${BASH_SOURCE[0]}")"
TOOL_PATH=".project/$TOOL_NAME"

COMMAND=""
AUTO_MODE=""
ENABLE_LOG=false

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 调试模式（可通过环境变量开启）
DEBUG="${DEBUG:-false}"

# 超时设置（秒）
TIMEOUT_CLONE=300
TIMEOUT_BUILD=600

# 日志文件
LOG_FILE="/tmp/perfetto-workwork-$(date +%Y%m%d-%H%M%S).log"

show_help() {
    echo ""
    echo "Perfetto 中文文档工具"
    echo ""
    echo "使用方法: bash $TOOL_PATH <命令>"
    echo ""
    echo "命令:"
    echo "  deploy-local     本地部署并启动服务器"
    echo "  deploy-gh-pages  部署到 GitHub Pages"
    echo "  sync-check       检查上游 docs/ 更新"
    echo "  sync-update      更新 LAST_SYNC"
    echo ""
    echo "选项:"
    echo "  --help, -h       显示帮助信息"
    echo ""
}

parse_args() {
    case "${1:-}" in
        deploy-local)
            COMMAND="deploy-local"
            shift
            ;;
        deploy-gh-pages)
            COMMAND="deploy-gh-pages"
            shift
            ;;
        sync-check)
            COMMAND="sync-check"
            shift
            ;;
        sync-update)
            COMMAND="sync-update"
            shift
            ;;
        help|--help|-h)
            COMMAND="help"
            shift
            ;;
        "")
            show_help
            exit 1
            ;;
        *)
            echo "错误: 未知命令 '$1'"
            show_help
            exit 1
            ;;
    esac

    while [ $# -gt 0 ]; do
        case "$1" in
            --auto)
                AUTO_MODE="--auto"
                shift
                ;;
            --help|-h)
                COMMAND="help"
                shift
                ;;
            *)
                echo "错误: 未知参数 '$1'"
                show_help
                exit 1
                ;;
        esac
    done
}

log() {
    if [ "$ENABLE_LOG" = "true" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    fi
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    log "INFO: $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    log "SUCCESS: $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
    log "ERROR: $1"
}

print_step() {
    echo ""
    echo -e "${YELLOW}=== 步骤 $1/4: $2 ===${NC}"
    log "STEP $1: $2"
}

print_debug() {
    if [ "$DEBUG" = "true" ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
    log "DEBUG: $1"
}

detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="Linux";;
        Darwin*)    OS="macOS";;
        CYGWIN*)    OS="Windows";;
        MINGW*)     OS="Windows";;
        MSYS*)      OS="Windows";;
        *)          OS="Unknown";;
    esac
    echo "$OS"
}

OS=$(detect_os)

get_timeout_cmd() {
    if [ "$OS" = "Linux" ]; then
        if command -v timeout &> /dev/null; then
            echo "timeout"
        elif command -v gtimeout &> /dev/null; then
            echo "gtimeout"
        else
            echo ""
        fi
    elif [ "$OS" = "macOS" ]; then
        if command -v gtimeout &> /dev/null; then
            echo "gtimeout"
        else
            echo ""
        fi
    else
        echo ""
    fi
}

timeout_compat() {
    local duration=$1
    shift

    local timeout_cmd=$(get_timeout_cmd)

    if [ -n "$timeout_cmd" ]; then
        $timeout_cmd $duration "$@"
    else
        perl -e 'alarm shift; exec @ARGV' "$duration" "$@"
    fi
}

check_disk_space() {
    local dir=$1
    local required_mb=${2:-100}

    local available_mb=0

    case "$OS" in
        "Linux")
            available_mb=$(df -m "$dir" | tail -1 | awk '{print $4}')
            ;;
        "macOS")
            available_mb=$(df -m "$dir" | tail -1 | awk '{print $4}')
            ;;
        "Windows")
            if command -v df &> /dev/null; then
                available_mb=$(df -m "$dir" 2>/dev/null | tail -1 | awk '{print $4}')
            else
                available_mb=10000
            fi
            ;;
        *)
            available_mb=10000
            ;;
    esac

    if [ "$available_mb" -lt "$required_mb" ]; then
        print_error "磁盘空间不足（剩余 ${available_mb}MB，需要 ${required_mb}MB）"
        return 1
    fi

    print_debug "磁盘空间充足: ${available_mb}MB"
    return 0
}

check_port() {
    local port=$1

    case "$OS" in
        "Linux"|"macOS")
            if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
                return 1
            fi
            ;;
        "Windows")
            if command -v netstat &> /dev/null; then
                if netstat -an | grep -q ":$port "; then
                    return 1
                fi
            fi
            ;;
    esac
    return 0
}

cleanup_port() {
    local port=$1
    print_info "尝试清理端口 $port 占用..."

    local pids=""
    case "$OS" in
        "Linux"|"macOS")
            pids=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
            ;;
        "Windows")
            if command -v netstat &> /dev/null && command -v taskkill &> /dev/null; then
                pids=$(netstat -ano | grep ":$port " | awk '{print $5}' | head -1)
            fi
            ;;
    esac

    if [ -n "$pids" ]; then
        case "$OS" in
            "Linux"|"macOS")
                echo "$pids" | xargs kill -9 2>/dev/null || true
                ;;
            "Windows")
                taskkill /F /PID $pids 2>/dev/null || true
                ;;
        esac
        sleep 2
        print_success "端口 $port 已清理"
    fi
}

monitor_build_progress() {
    local log_file=$1
    local last_line_count=0
    local no_change_count=0
    local max_no_change=60

    print_info "启动编译进度监控..."

    while true; do
        sleep 2

        if [ ! -f "$log_file" ]; then
            continue
        fi

        local current_line_count=0
        if [ "$OS" = "Windows" ]; then
            current_line_count=$(wc -l < "$log_file" 2>/dev/null | tr -d ' ' || echo 0)
        else
            current_line_count=$(wc -l < "$log_file" 2>/dev/null || echo 0)
        fi

        if [ "$current_line_count" -eq "$last_line_count" ]; then
            no_change_count=$((no_change_count + 1))

            if [ $no_change_count -eq 10 ]; then
                print_warning "编译似乎没有进展（20秒无输出）..."
            elif [ $no_change_count -eq 30 ]; then
                print_warning "编译进展缓慢（60秒无输出）..."
            elif [ $no_change_count -ge $max_no_change ]; then
                print_error "编译似乎卡住了（120秒无输出）"
                return 1
            fi
        else
            if [ $no_change_count -ge 10 ]; then
                print_success "编译恢复进行中..."
            fi
            no_change_count=0
            last_line_count=$current_line_count

            local last_lines=$(tail -3 "$log_file" 2>/dev/null)
            if [ -n "$last_lines" ]; then
                print_debug "最新输出: $last_lines"
            fi
        fi

        if grep -qE '\[379/379\].*stamp obj/site\.stamp' "$log_file" 2>/dev/null; then
            print_success "编译成功完成！"
            return 0
        fi

        if grep -qE '(Done!|Build completed successfully)' "$log_file" 2>/dev/null; then
            print_success "编译完成！"
            return 0
        fi

        if grep -qE "(Error:|FAILED|FATAL)" "$log_file" 2>/dev/null; then
            print_error "编译过程中出现错误"
            return 1
        fi

        if [ -n "$BUILD_PID" ] && ! kill -0 $BUILD_PID 2>/dev/null; then
            if grep -qE '\[[0-9]+/[0-9]+\].*stamp obj/site\.stamp' "$log_file" 2>/dev/null; then
                print_success "编译进程已完成！"
                return 0
            fi
        fi
    done
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "命令 '$1' 未找到，请先安装"
        return 1
    fi
    print_debug "命令 '$1' 已安装"
    return 0
}

check_directory() {
    local dir=$1
    if [ ! -d "$dir" ]; then
        print_debug "目录不存在，创建: $dir"
        mkdir -p "$dir" || {
            print_error "无法创建目录: $dir"
            return 1
        }
    fi

    if [ "$OS" != "Windows" ]; then
        if [ ! -w "$dir" ]; then
            print_error "目录没有写权限: $dir"
            return 1
        fi
    fi

    print_debug "目录检查通过: $dir"
    return 0
}

self_heal() {
    print_info "尝试自动修复常见问题..."
    print_info "当前操作系统: $OS"

    cleanup_port 8082

    if ! check_disk_space "$PROJECT_ROOT" 100; then
        return 1
    fi

    if ! check_command node; then
        print_error "Node.js 未安装"
        print_info "请访问 https://nodejs.org/ 安装 Node.js"
        return 1
    fi

    if ! check_command git; then
        print_error "Git 未安装"
        if [ "$OS" = "Windows" ]; then
            print_info "请安装 Git for Windows: https://git-scm.com/download/win"
        else
            print_info "请使用包管理器安装 Git"
        fi
        return 1
    fi

    if [ "$OS" = "Windows" ]; then
        print_info "检测到 Windows 系统"
        print_info "确保在 Git Bash 或 WSL 环境中运行此脚本"
    fi

    print_success "自愈检查完成"
    return 0
}

run_with_timeout() {
    local timeout_sec=$1
    local retries=${2:-0}
    local cmd="${@:3}"
    local attempt=0

    while [ $attempt -le $retries ]; do
        if [ $attempt -gt 0 ]; then
            print_warning "第 $attempt 次重试..."
            sleep 2
        fi

        print_debug "执行命令: $cmd"
        print_debug "超时设置: ${timeout_sec}秒"

        local output_file=$(mktemp)
        if timeout_compat $timeout_sec bash -c "$cmd" > "$output_file" 2>&1; then
            cat "$output_file" | tee -a "$LOG_FILE"
            rm -f "$output_file"
            return 0
        else
            local exit_code=$?
            cat "$output_file" | tee -a "$LOG_FILE"
            rm -f "$output_file"

            if [ $exit_code -eq 124 ] || [ $exit_code -eq 142 ]; then
                print_error "命令执行超时（${timeout_sec}秒）"
                log "TIMEOUT: 命令执行超过 ${timeout_sec} 秒"
            else
                print_error "命令失败，退出码: $exit_code"
                log "FAILED: 命令失败，退出码: $exit_code"
            fi

            attempt=$((attempt + 1))
            if [ $attempt -le $retries ]; then
                print_info "等待后重试..."
                sleep 5
            fi
        fi
    done

    return 1
}

ensure_perfetto_repo_for_deploy() {
    print_step "1" "检查 Perfetto 仓库"

    if [ ! -d "$PERFETTO_DIR/.git" ]; then
        print_warning "Perfetto 仓库不存在"
        print_info "正在从 GitHub 克隆 Perfetto 仓库..."

        if check_directory "$PROJECT_ROOT"; then
            cd "$PROJECT_ROOT"

            if run_with_timeout $TIMEOUT_CLONE 2 "git clone https://github.com/google/perfetto.git perfetto"; then
                print_success "Perfetto 仓库克隆完成"
            else
                print_error "克隆失败，请检查网络连接"
                exit 1
            fi
        else
            exit 1
        fi
    else
        print_success "Perfetto 仓库已存在 ($PERFETTO_DIR)"
        print_debug "Git 远程仓库: $(cd "$PERFETTO_DIR" && git remote -v 2>/dev/null | head -1)"
    fi
}

run_deploy() {
    local deploy_mode="$1"
    ENABLE_LOG=true

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      Perfetto 中文文档部署脚本                           ║${NC}"
    echo -e "${GREEN}║      支持: macOS / Linux / Windows (Git Bash/WSL)        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_info "操作系统: $OS"
    print_info "日志文件: $LOG_FILE"
    print_info "调试模式: $DEBUG"
    echo ""

    log "========================================="
    log "开始部署"
    log "操作系统: $OS"
    log "当前目录: $(pwd)"
    log "用户: $(whoami)"
    log "系统: $(uname -a)"
    log "========================================="

    print_debug "SCRIPT_DIR: $SCRIPT_DIR"
    print_debug "DOCS_ZH_DIR: $DOCS_ZH_DIR"
    print_debug "PROJECT_ROOT: $PROJECT_ROOT"
    print_debug "PERFETTO_DIR: $PERFETTO_DIR"

    if ! self_heal; then
        print_error "自愈检查失败，请手动修复问题"
        exit 1
    fi

    ensure_perfetto_repo_for_deploy

    cd "$PERFETTO_DIR"

    print_step "2" "替换为中文文档"

    if [ ! -d "$DOCS_ZH_DIR/docs" ]; then
        print_error "中文文档目录不存在: $DOCS_ZH_DIR/docs"
        exit 1
    fi

    print_info "删除英文 docs 目录..."
    rm -rf docs
    print_success "英文 docs 目录已删除"

    print_info "复制中文 docs 目录..."
    cp -r "$DOCS_ZH_DIR/docs" .
    print_success "中文 docs 目录已复制"

    if [ -f "docs/README.md" ]; then
        print_debug "README.md 验证通过"
        print_info "共复制 $(find docs -name '*.md' 2>/dev/null | wc -l) 个 Markdown 文件"
    else
        print_error "复制失败，README.md 不存在"
        exit 1
    fi

    print_step "2b" "修改首页配置"
    BUILD_GN_FILE="infra/perfetto.dev/BUILD.gn"

    print_info "备份原始 BUILD.gn..."
    cp "$BUILD_GN_FILE" "$BUILD_GN_FILE.bak"

    print_info "修改首页配置，使用 README.md 作为首页内容..."
    sed -i '' 's/md_to_html("gen_index") {/md_to_html("gen_index") {\n  markdown = "${src_doc_dir}\/README.md"/' "$BUILD_GN_FILE"
    sed -i '' 's|html_template = "src/template_index.html"|html_template = "src/template_markdown.html"|' "$BUILD_GN_FILE"

    print_success "首页配置已修改"

    print_step "3" "验证文档"

    print_info "验证中文文档..."
    if [ -f "docs/README.md" ]; then
        print_success "README.md 验证通过"
        print_info "共复制 $(find docs -name '*.md' 2>/dev/null | wc -l) 个 Markdown 文件"
    else
        print_error "复制失败，docs/README.md 不存在"
        exit 1
    fi

    echo ""
    print_step "4" "构建并启动服务器（官方方式）"

    print_info "检查 Node.js..."
    if ! check_command node; then
        exit 1
    fi

    print_info "Node.js 版本: $(node --version 2>/dev/null || echo '未知')"

    cd "$PERFETTO_DIR"
    BUILD_JS="$PERFETTO_DIR/infra/perfetto.dev/build.js"
    if grep -q "exec(installBuildDeps, depsArgs)" "$BUILD_JS" 2>/dev/null; then
        sed -i '' 's/exec(installBuildDeps, depsArgs);/\/\/ exec(installBuildDeps, depsArgs); \/\/ 跳过 test_data 检查/' "$BUILD_JS"
        print_success "已跳过 build.js 中的 test_data 依赖检查"
    else
        print_info "build.js 无需 patch"
    fi

    print_info "检查 npm 依赖..."
    cd "$PERFETTO_DIR/infra/perfetto.dev"
    if [ ! -d "node_modules" ] || [ ! -d "node_modules/argparse" ]; then
        print_warning "npm 依赖不完整，正在安装..."
        if npm install 2>&1 | tee -a "$LOG_FILE"; then
            print_success "npm 依赖安装完成"
        else
            print_error "npm 依赖安装失败"
            print_info "请手动运行: cd perfetto/infra/perfetto.dev && npm install"
            exit 1
        fi
    else
        print_success "npm 依赖已满足"
    fi

    cd "$PERFETTO_DIR"

    if ! check_port 8082; then
        print_info "端口 8082 被占用，尝试清理..."
        cleanup_port 8082
    fi

    print_info "清理旧构建输出..."
    rm -rf out/perfetto.dev
    print_success "旧构建输出已清理"

    print_info "执行构建（不启动服务器）..."
    print_info "使用命令: node infra/perfetto.dev/build.js"
    print_info "首次构建需要 2-5 分钟，请耐心等待..."
    echo ""

    BUILD_LOG=$(mktemp)
    export BUILD_LOG
    print_debug "构建日志: $BUILD_LOG"

    node infra/perfetto.dev/build.js > "$BUILD_LOG" 2>&1 &
    BUILD_PID=$!

    print_info "构建进程 PID: $BUILD_PID"
    print_info "正在监控编译进度..."

    if monitor_build_progress "$BUILD_LOG"; then
        print_success "构建完成！"

        if [ -d "out/perfetto.dev" ]; then
            print_success "构建输出目录验证通过"
        else
            print_warning "未找到标准构建输出目录，但构建可能已成功"
        fi

        rm -f "$BUILD_LOG"

        if [[ "$deploy_mode" == "deploy-gh-pages" ]]; then
            echo ""
            print_success "========================================"
            print_success "构建完成！准备部署到 GitHub Pages"
            print_success "========================================"
            echo ""

            cd "$DOCS_ZH_DIR"

            REPO_NAME=$(basename "$DOCS_ZH_DIR")
            print_info "仓库名: $REPO_NAME"

            DEPLOY_TEMP=$(mktemp -d)
            print_info "创建临时部署目录: $DEPLOY_TEMP"

            cp -r "$PERFETTO_DIR/out/perfetto.dev/site"/* "$DEPLOY_TEMP/"

            print_info "修复 GitHub Pages 路径..."

            print_info "为无扩展名文件添加 .html 后缀..."
            for file in "$DEPLOY_TEMP/docs"/*; do
                if [ -f "$file" ] && [[ ! "$file" =~ \. ]]; then
                    mv "$file" "$file.html"
                fi
            done
            find "$DEPLOY_TEMP/docs" -type f ! -name "*.png" ! -name "*.jpg" ! -name "*.gif" ! -name "*.svg" ! -name "*.ico" ! -name "*.html" -exec sh -c 'mv "$1" "$1.html"' _ {} \; 2>/dev/null || true

            find "$DEPLOY_TEMP" -name "*.html" -type f -exec sed -i '' \
                -e "s|href=\"/assets/|href=\"/$REPO_NAME/assets/|g" \
                -e "s|src=\"/assets/|src=\"/$REPO_NAME/assets/|g" \
                -e "s|href=\"/docs/|href=\"/$REPO_NAME/docs/|g" \
                -e "s|src=\"/docs/|src=\"/$REPO_NAME/docs/|g" \
                -e "s|data=\"/docs/|data=\"/$REPO_NAME/docs/|g" \
                -e "s|href=\"/\"|href=\"/$REPO_NAME/\"|g" \
                {} \;

            sed -i '' "s|\"\/assets\/mermaid.min.js\"|\"\/$REPO_NAME\/assets\/mermaid.min.js\"|g" "$DEPLOY_TEMP/assets/script.js" 2>/dev/null || true
            sed -i '' "s|\"\/assets\/sprite.png\"|\"\/$REPO_NAME\/assets\/sprite.png\"|g" "$DEPLOY_TEMP/assets/style.css" 2>/dev/null || true

            find "$DEPLOY_TEMP" -name "*.html" -type f -exec sed -i '' \
                -e "s|href=\"/$REPO_NAME/docs/\([^\"]*\)\"|href=\"/$REPO_NAME/docs/\1.html\"|g" \
                {} \;

            find "$DEPLOY_TEMP" -name "*.html" -type f -exec sed -i '' \
                -e "s|href=\"/$REPO_NAME/docs/\.html\"|href=\"/$REPO_NAME/docs/\"|g" \
                {} \;

            print_success "路径修复完成"

            touch "$DEPLOY_TEMP/.nojekyll"

            print_info "部署到 gh-pages 分支..."
            cd "$DEPLOY_TEMP"
            git init
            git config user.email "deploy@perfetto-docs.local"
            git config user.name "Deploy Bot"
            git add -A
            git commit -m "Deploy to GitHub Pages"
            git push --force "$DOCS_ZH_DIR" main:gh-pages
            cd "$DOCS_ZH_DIR"
            git push origin gh-pages --force

            rm -rf "$DEPLOY_TEMP"

            print_success "========================================"
            print_success "GitHub Pages 部署成功！"
            print_success "========================================"
            print_info ""
            print_info "访问地址: https://gugu-perf.github.io/$REPO_NAME/"
            print_info ""

            exit 0
        fi

        echo ""
        print_info "启动 HTTP 服务器..."
        print_info "使用命令: node infra/perfetto.dev/build.js --serve"
        print_info "服务器将在后台运行"
        echo ""

        SERVER_LOG="/tmp/perfetto-server-$(date +%Y%m%d-%H%M%S).log"

        node infra/perfetto.dev/build.js --serve > "$SERVER_LOG" 2>&1 &
        SERVER_PID=$!

        print_info "服务器进程 PID: $SERVER_PID"
        print_info "服务器日志: $SERVER_LOG"

        print_info "等待服务器启动..."
        sleep 5

        retry_count=0
        max_retries=6

        while [ $retry_count -lt $max_retries ]; do
            if ! check_port 8082; then
                print_success "服务器已正常启动（端口 8082 已被占用）"
                break
            fi

            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                print_info "服务器启动中... (${retry_count}/${max_retries})"
                sleep 2
            fi
        done

        if [ $retry_count -eq $max_retries ]; then
            print_error "服务器未能正常启动（端口 8082 未被占用）"
            print_info "检查服务器日志最后 30 行:"
            tail -30 "$SERVER_LOG"
            exit 1
        fi

        print_info ""
        print_success "========================================"
        print_success "本地部署成功！"
        print_success "========================================"
        print_info ""
        print_info "访问地址: http://localhost:8082/docs/"
        print_info ""
        print_info "服务器在后台运行，PID: $SERVER_PID"
        print_info "查看服务器日志: tail -f $SERVER_LOG"
        print_info ""
        print_info "停止服务器命令: kill $SERVER_PID"
        print_info ""
        print_info "日志文件保留在: $LOG_FILE"
        print_info ""
        print_info "========================================"
        print_info "GitHub Pages 部署"
        print_info "========================================"
        print_info ""
        print_info "如需部署到 GitHub Pages，请运行:"
        print_info ""
        print_info "  bash $TOOL_PATH deploy-gh-pages"
        print_info ""
    else
        print_error "构建过程出现问题"
        print_info "杀死构建进程..."
        kill $BUILD_PID 2>/dev/null || true

        print_info "最后 50 行日志:"
        tail -50 "$BUILD_LOG"

        rm -f "$BUILD_LOG"
        exit 1
    fi
}

ensure_perfetto_repo_for_sync() {
    if [ ! -d "$PERFETTO_DIR/.git" ]; then
        print_warning "Perfetto 仓库不存在，正在克隆到平级目录..."
        cd "$PROJECT_ROOT"
        git clone https://github.com/google/perfetto.git perfetto
        print_success "Perfetto 仓库克隆完成: $PERFETTO_DIR"
    fi
}

run_sync() {
    local sync_mode="$1"
    ENABLE_LOG=false

    echo ""
    echo "========================================"
    echo "Perfetto 上游同步检测"
    echo "========================================"
    echo ""

    ensure_perfetto_repo_for_sync

    if [ -f "$LAST_SYNC_FILE" ]; then
        LAST_SYNC_LINE=$(grep -v "^#" "$LAST_SYNC_FILE" | grep -v "^$" | head -1)
        LAST_SYNC_COMMIT=$(echo "$LAST_SYNC_LINE" | awk '{print $1}')
    else
        print_warning "未找到 LAST_SYNC 文件"
        print_info "请创建 .project/LAST_SYNC 文件记录上次同步点"
        LAST_SYNC_COMMIT="unknown"
    fi

    cd "$PERFETTO_DIR"

    print_info "正在强制同步本地仓库与远程一致..."
    git clean -fd 2>/dev/null || true
    git reset --hard HEAD 2>/dev/null || true
    git checkout main 2>/dev/null || git checkout -b main origin/main
    git pull origin main --ff-only
    print_success "本地仓库已同步到最新"

    REMOTE_SHORT=$(git log -1 --format="%h" HEAD -- docs/)
    REMOTE_DATE=$(git log -1 --format=%cd --date=short HEAD -- docs/)
    REMOTE_MSG=$(git log -1 --format=%s HEAD -- docs/)

    echo ""
    if [ "$sync_mode" = "sync-check" ]; then
        print_info "上次同步点（LAST_SYNC 记录）:"
        if [ "$LAST_SYNC_COMMIT" != "unknown" ]; then
            echo "  $LAST_SYNC_LINE"
        else
            echo "  unknown"
        fi
        echo ""

        print_info "上游最新:"
        echo "  Commit: $REMOTE_SHORT"
        echo "  日期: $REMOTE_DATE"
        echo "  描述: $REMOTE_MSG"
        echo ""

        if git cat-file -e "$LAST_SYNC_COMMIT" 2>/dev/null; then
            DOCS_CHANGES=$(git diff --name-only "$LAST_SYNC_COMMIT" HEAD -- docs/ 2>/dev/null || echo "")
        else
            print_warning "LAST_SYNC 中的 commit 在本地不存在，可能已重新 clone 或历史被修改"
            print_info "建议手动检查: cd perfetto && git log --oneline -10 -- docs/"
            DOCS_CHANGES=""
        fi

        if [ -z "$DOCS_CHANGES" ]; then
            print_success "docs/ 目录已是最新，无需同步"
            echo ""
            exit 0
        else
            print_warning "发现 docs/ 目录有更新！"
            echo ""

            echo "变更的文件列表:"
            echo "----------------------------------------"
            echo "$DOCS_CHANGES" | head -20

            CHANGED_COUNT=$(echo "$DOCS_CHANGES" | wc -l)
            echo ""
            echo "共 $CHANGED_COUNT 个文件有变更"
            echo ""

            echo "========================================"
            echo "建议操作步骤:"
            echo "========================================"
            echo ""
            echo "1. 查看详细变更:"
            echo "   cd perfetto && git log --oneline $LAST_SYNC_COMMIT..HEAD -- docs/"
            echo ""
            echo "2. 对比变更并翻译:"
            echo "   git diff $LAST_SYNC_COMMIT -- docs/"
            echo ""
            echo "4. 翻译完成后更新 LAST_SYNC:"
            echo "   bash $TOOL_PATH sync-update"
            echo ""

            exit 1
        fi
    fi

    echo ""
    print_info "正在更新 LAST_SYNC 文件..."

    REMOTE_HASH=$(git log -1 --format="%h" origin/main -- docs/)
    REMOTE_DATE=$(git log -1 --format="%ci" origin/main -- docs/ | awk '{print $1}')
    REMOTE_TIME=$(git log -1 --format="%ci" origin/main -- docs/ | awk '{print $2, $3}')
    REMOTE_MSG=$(git log -1 --format="%s" origin/main -- docs/)
    REMOTE_LINE="$REMOTE_HASH $REMOTE_DATE $REMOTE_TIME $REMOTE_MSG"

    cat > "$LAST_SYNC_FILE" << EOF
# LAST_SYNC - 上游同步记录文件
#
# 格式: git log --oneline 单行格式
#   <short-hash> <date> <time> <tz> <message>
#
# 更新方式:
#   bash $TOOL_PATH sync-update

$REMOTE_LINE
EOF

    print_success "LAST_SYNC 已更新"
    echo ""
    echo "更新内容:"
    echo "  $REMOTE_LINE"
    echo ""
}

parse_args "$@"

case "$COMMAND" in
    deploy-local)
        run_deploy "$COMMAND"
        ;;
    deploy-gh-pages)
        run_deploy "$COMMAND"
        ;;
    sync-check)
        run_sync "$COMMAND"
        ;;
    sync-update)
        run_sync "$COMMAND"
        ;;
    help)
        show_help
        ;;
esac
