#!/bin/bash
# 逐页对比标题结构（本地 vs perfetto.dev 官网），只报告不匹配的页面
#
# 修复记录（2026-09-19）：
#   - 快照竞态：改为从 playwright-cli goto 的 stdout 捕获本次快照路径
#     （输出含 `[Snapshot](.playwright-cli/page-*.yml)`），不再用全局 ls -t 猜测
#   - 会话未打开时自动 open（--browser=chromium）
#   - 对比标题级别序列，而非仅数量
#   - 空页面的计数修正
set -u

SNAPSHOT_DIR="$HOME/CodeBuddy/Claw/perfetto-docs-zh-cn/.playwright-cli"
LOCAL_BASE="http://localhost:8082"
OFFICIAL_BASE="https://perfetto.dev"

# 从 toc.md 提取所有页面路径（排除 # 锚点和外部链接）
URLS=$(perl -nle 'while(/\]\(([^)]+)\)/g){print $1}' docs/toc.md | grep -v '^#' | grep -v '^http' | grep '\.md$' | sed 's/\.md$//' | sort -u)

ensure_session() {  # ensure_session <name> <url>
    out=$(playwright-cli -s="$1" goto "$2" 2>/dev/null || true)
    if ! echo "$out" | grep -q 'Page Title'; then
        echo "会话 '$1' 未打开，正在启动..." >&2
        playwright-cli -s="$1" open --browser=chromium "$2" >/dev/null 2>&1 || {
            echo "错误: 无法启动浏览器会话 '$1'（playwright-cli 是否可用？）" >&2; exit 2; }
        sleep 1
        out=$(playwright-cli -s="$1" goto "$2" 2>/dev/null || true)
    fi
    echo "$out"
}

goto_snap() {  # goto_snap <session> <url> → 输出快照文件路径（本次 goto 专属）
    local out snap
    out=$(ensure_session "$1" "$2")
    snap=$(echo "$out" | grep -oE '\.playwright-cli/page-[^) ]+\.yml' | head -1)
    [ -n "$snap" ] || return 1
    echo "${snap#\.playwright-cli/}"
    [ -s "$SNAPSHOT_DIR/${snap#\.playwright-cli/}" ]
}

headings_of() {  # headings_of <snap-relpath> → 级别序列（如 1,2,2,3,2）
    grep -oE 'heading "[^"]*" \[level=[0-9]+\]' "$SNAPSHOT_DIR/$1" 2>/dev/null \
        | grep -oE 'level=[0-9]+' | sed 's/level=//' | paste -sd, -
}

TOTAL=0; PASSED=0; FAILED=0; ISSUES=""

echo "=== 标题结构对比 ($(echo "$URLS" | wc -l | tr -d ' ') 个页面) ==="
echo ""

for url in $URLS; do
    TOTAL=$((TOTAL + 1))
    local_url="${LOCAL_BASE}/docs/${url}"
    official_url="${OFFICIAL_BASE}/docs/${url}"

    ls_snap=$(goto_snap local "$local_url")
    os_snap=$(goto_snap official "$official_url")

    lh=$(headings_of "${ls_snap:-/dev/null}"); [ "${lh:-}" = "" ] && lh="-"
    oh=$(headings_of "${os_snap:-/dev/null}"); [ "${oh:-}" = "" ] && oh="-"
    lc=$(echo "$lh" | tr ',' '\n' | grep -c . || true)
    oc=$(echo "$oh" | tr ',' '\n' | grep -c . || true)

    if [ "$lh" = "-" ]; then
        FAILED=$((FAILED + 1))
        ISSUES="$ISSUES\n  ❌ $url: 本地页面加载失败 (官方: ${oc} 个标题)"
        printf "\r[%d] %-45s  ❌ 加载失败" "$TOTAL" "$url"
    elif [ "$lh" = "$oh" ]; then
        PASSED=$((PASSED + 1))
        printf "\r[%d] %-45s  ✅ %2d/%2d" "$TOTAL" "$url" "$lc" "$oc"
    else
        FAILED=$((FAILED + 1))
        ISSUES="$ISSUES\n  ⚠️  $url: 本地 ${lc} 个 vs 官方 ${oc} 个标题（级别序列: 本地[$lh] 官方[$oh]）"
        printf "\r[%d] %-45s  ⚠️  %d/%d" "$TOTAL" "$url" "$lc" "$oc"
    fi
done

echo ""
echo ""
echo "=== 完成: 总计 $TOTAL | 通过 $PASSED | 失败 $FAILED ==="
if [ -n "$ISSUES" ]; then
    echo -e "\n--- 问题详情 ---$ISSUES"
    exit 1
else
    echo "所有页面标题结构匹配！✅"
fi
