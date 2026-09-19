#!/bin/bash
# 批量对比所有子页面的标题结构

LOCAL_BASE="http://localhost:8082"
OFFICIAL_BASE="https://perfetto.dev"
SNAPSHOT_DIR="$HOME/CodeBuddy/Claw/perfetto-docs-zh-cn/.playwright-cli"

# Sidebar URLs (excluding the index page)
URLS=$(cat /tmp/local_urls.txt | grep -v '^/docs/$')

total=0
passed=0
failed=0
errors=""

echo "=== 开始批量检查 $(echo "$URLS" | wc -l | tr -d ' ') 个子页面 ==="
echo ""

for url in $URLS; do
    total=$((total + 1))
    local_url="${LOCAL_BASE}${url}"
    official_url="${OFFICIAL_BASE}${url}"
    
    # Visit local page
    playwright-cli -s=local goto "$local_url" 2>&1 > /dev/null
    if [ $? -ne 0 ]; then
        failed=$((failed + 1))
        errors="$errors\n❌ [$total] $url - 本地页面加载失败"
        echo -ne "\r[$total] $url ... 本地加载失败"
        continue
    fi
    
    # Get local headings
    local_snap=$(ls -t "$SNAPSHOT_DIR"/page-*.yml 2>/dev/null | head -1)
    local_headings=$(grep -oE 'heading "[^"]*"' "$local_snap" | sed 's/heading "//;s/"$//')
    local_count=$(echo "$local_headings" | grep -c . 2>/dev/null || echo 0)
    
    # Visit official page
    playwright-cli -s=official goto "$official_url" 2>&1 > /dev/null
    if [ $? -ne 0 ]; then
        failed=$((failed + 1))
        errors="$errors\n❌ [$total] $url - 官方页面加载失败"
        echo -ne "\r[$total] $url ... 官方加载失败"
        continue
    fi
    
    # Get official headings
    official_snap=$(ls -t "$SNAPSHOT_DIR"/page-*.yml 2>/dev/null | head -1)
    official_headings=$(grep -oE 'heading "[^"]*"' "$official_snap" | sed 's/heading "//;s/"$//')
    official_count=$(echo "$official_headings" | grep -c . 2>/dev/null || echo 0)
    
    # Compare
    if [ "$local_count" -eq "$official_count" ]; then
        passed=$((passed + 1))
        status="✅"
    else
        failed=$((failed + 1))
        status="❌"
        errors="$errors\n$status [$total] $url: 本地 $local_count 个标题 vs 官方 $official_count 个标题"
    fi
    
    echo -ne "\r[$total/88] $url ... $local_count/$official_count $status"
done

echo ""
echo ""
echo "=== 检查完成 ==="
echo "总计: $total | 通过: $passed | 失败: $failed"
if [ -n "$errors" ]; then
    echo ""
    echo "=== 失败详情 ==="
    echo -e "$errors"
fi
