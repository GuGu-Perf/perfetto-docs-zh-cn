#!/bin/bash
# audit.sh — 全量结构审计：本地 docs/ vs 上游 perfetto@HEAD（git 对象，非工作树）
#
# 用法:
#   bash .project/audit.sh                     # 全量审计
#   bash .project/audit.sh --files docs/a.md   # 只审计指定文件
#   PERFETTO_DIR=/path bash .project/audit.sh  # 覆盖上游仓库位置
#
# 检查项（均剥离代码块后统计，避免代码内注释造成误报）:
#   A1 文件清单: 上游有而本地缺（漏翻/漏新建）、本地有而上游无（上游已删未同步）
#   A2 标题数 (^#{1,6} )
#   A3 代码围栏数 (^```)
#   A4 表格行数 (^|)               —— 近似对比，差异仅提示
#   A5 图片数 (^![...)
#   A6 链接 URL 集合               —— URL 必须与上游一致（指南规定 URL 不变）
#   A7 幽灵引用: 工程文档引用的 .project/* 脚本/文件必须存在
#
# 退出码: 0=干净, 1=存在差异（欠账清单见输出）
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PERFETTO_DIR="${PERFETTO_DIR:-$(cd "$REPO_DIR/.." && pwd)/perfetto}"

if [ ! -d "$PERFETTO_DIR/.git" ]; then
    echo "错误: 上游仓库不存在: $PERFETTO_DIR（可用 PERFETTO_DIR 覆盖）" >&2
    exit 2
fi

upstream_file() {  # 输出上游某 md 文件的英文原文（git 对象）
    git -C "$PERFETTO_DIR" show "HEAD:$1" 2>/dev/null
}

strip_fences() {   # 剥离 ``` 围栏内容（围栏行本身也去掉）
    awk '/^```/{f=!f; next} !f{print}'
}

count_in() {  # count_in <ere-pattern>  （读 stdin，输出计数）
    grep -cE "$1" - 2>/dev/null | cat
    return 0
}

# ---- 参数 ----
UP_LIST=$(mktemp); CHECK_LIST=$(mktemp); LOC_LIST=$(mktemp)
TMP_UP=$(mktemp); TMP_LOC=$(mktemp)
trap 'rm -f "$UP_LIST" "$CHECK_LIST" "$LOC_LIST" "$TMP_UP" "$TMP_LOC"' EXIT

git -C "$PERFETTO_DIR" ls-tree -r --name-only HEAD docs/ | grep '\.md$' | sed 's|^docs/||' > "$UP_LIST"

if [ "${1:-}" = "--files" ]; then
    shift
    for a in "$@"; do echo "${a#docs/}"; done > "$CHECK_LIST"
else
    cp "$UP_LIST" "$CHECK_LIST"
fi

ISSUES=0
report() { echo "$1"; ISSUES=$((ISSUES+1)); }

echo "=== audit.sh 结构审计 (上游: $(git -C "$PERFETTO_DIR" rev-parse --short HEAD)) ==="
echo "审计范围: $(wc -l < "$CHECK_LIST" | tr -d ' ') 个文件（上游共 $(wc -l < "$UP_LIST" | tr -d ' ') 个 md）"
echo ""

# ---- A1 文件清单（仅全量模式） ----
if [ "${1:-}" != "--files" ] && [ -z "${AUDIT_SKIP_A1:-}" ]; then
    while IFS= read -r f; do
        [ -f "docs/$f" ] || report "A1 漏翻/缺失: docs/$f"
    done < "$UP_LIST"
    find docs -name '*.md' | sed 's|^docs/||' | sort > "$LOC_LIST"
    comm -23 "$LOC_LIST" <(sort "$UP_LIST") | while IFS= read -r f; do
        echo "A1 上游已删除未同步: docs/$f"
    done
fi

# ---- A2-A6 逐文件结构 ----
cd "$REPO_DIR"
while IFS= read -r f; do
    [ -f "docs/$f" ] || continue
    upstream_file "docs/$f" > "$TMP_UP"
    [ -s "$TMP_UP" ] || continue   # 上游无此文件（A1 已报）

    strip_fences < "$TMP_UP"  > "${TMP_UP}.s" && mv "${TMP_UP}.s" "$TMP_UP"
    strip_fences < "docs/$f" > "${TMP_LOC}.s" && mv "${TMP_LOC}.s" "$TMP_LOC"

    uh=$(count_in '^#{1,6} ' < "$TMP_UP" || true); uh=${uh:-0}
    lh=$(count_in '^#{1,6} ' < "$TMP_LOC" || true); lh=${lh:-0}
    [ "$uh" != "$lh" ] && report "A2 标题数 docs/$f: 上游=$uh 本地=$lh"

    uf=$(git -C "$PERFETTO_DIR" show "HEAD:docs/$f" | grep -c '^```' | cat || true); uf=${uf:-0}
    lf=$(grep -c '^```' "docs/$f" | cat || true); lf=${lf:-0}
    [ "$uf" != "$lf" ] && report "A3 代码围栏 docs/$f: 上游=$uf 本地=$lf"

    ut=$(count_in '^\|' < "$TMP_UP" || true); ut=${ut:-0}
    lt=$(count_in '^\|' < "$TMP_LOC" || true); lt=${lt:-0}
    [ "$ut" != "$lt" ] && report "A4 表格行 docs/$f: 上游=${ut} 本地=${lt}（近似，请人工复核）"

    ui=$(count_in '^!\[' < "$TMP_UP" || true); ui=${ui:-0}
    li=$(count_in '^!\[' < "$TMP_LOC" || true); li=${li:-0}
    [ "$ui" != "$li" ] && report "A5 图片数 docs/$f: 上游=$ui 本地=$li"

    # A6 链接 URL 集合（取 ")" 前的 URL 主体，去掉可翻译的 "title" 部分；
    #    相对链接按文件目录归一化为 /docs/... 绝对路径，**先归一化再排序**，
    #    否则 ../ 与 /docs 写法的排序位置不同会造成行序 diff 假阳性）
    norm_urls() {
        python3 -c '
import sys, posixpath
base = sys.argv[1]
for u in sys.stdin:
    u = u.rstrip("\n")
    if u.startswith(("http", "#", "mailto:")) or not u:
        print(u)
    else:
        print("/" + posixpath.normpath(posixpath.join(base, u)).lstrip("/"))
' "$(dirname "$f")"
    }
    diff <(grep -oE '\]\([^)]+\)' "$TMP_UP"  | sed 's/^](//;s/)$//;s/ .*//' | grep -v '^#' | norm_urls | sort -u) \
         <(grep -oE '\]\([^)]+\)' "$TMP_LOC" | sed 's/^](//;s/)$//;s/ .*//' | grep -v '^#' | norm_urls | sort -u) \
         > /dev/null 2>&1 || report "A6 链接URL集合 docs/$f 与上游不一致"

    # A7 提示框（callout）数量一致性：段首大写 NOTE:/TIP:/WARNING:/TODO:/FIXME:/Summary:
    #    会被渲染成提示框（render.mjs renderParagraph，大小写敏感；列表内段落
    #    缩进被解析器剥离，同样生效）。数量不对说明 callout 被译走或纯文本被误标。
    callout_count() {
        grep -cE '^[[:space:]]*(NOTE|TIP|WARNING|TODO|FIXME|Summary):' - 2>/dev/null | cat
        return 0
    }
    uc=$(git -C "$PERFETTO_DIR" show "HEAD:docs/$f" | strip_fences | callout_count || true); uc=${uc:-0}
    lc=$(strip_fences < "docs/$f" | callout_count || true); lc=${lc:-0}
    [ "$uc" != "$lc" ] && report "A7 提示框数 docs/$f: 上游=${uc} 本地=${lc}"
done < "$CHECK_LIST"

# ---- A7 幽灵引用 ----
while IFS= read -r ref; do
    [ -e "$REPO_DIR/$ref" ] || report "A7 幽灵引用: $ref（文档引用但文件不存在）"
done < <(grep -rohE '\.project/[A-Za-z0-9_./-]+\.(sh|py|md|json)' \
            .project/*.md README.md CONTRIBUTING.md 2>/dev/null | sort -u)

echo ""
echo "==== 审计结果: $ISSUES 项差异 ===="
if [ "$ISSUES" -eq 0 ]; then
    echo "全部通过 ✅"
    exit 0
else
    echo "存在欠账，请按清单修复 ❌"
    exit 1
fi
