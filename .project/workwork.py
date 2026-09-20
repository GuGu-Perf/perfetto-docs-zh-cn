#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workwork.py — Perfetto 中文文档统一工具（单文件，全部命令）

用法: python3 .project/workwork.py <命令>

命令:
  deploy-local            本地部署并启动服务器
  deploy-gh-pages         部署到 GitHub Pages（含 fail-closed 断言 + pre-deploy tag）
  rollback-gh-pages [tag] 回退 gh-pages 到部署前状态
  sync-check              检查上游 docs/ 更新
  sync-update             更新 LAST_SYNC
  audit [--files ...]     全量结构审计（本地 docs/ vs 上游 git HEAD）
  proofread [--all] [...] 术语/标志/标点 lint
  compare-structure [...] 渲染层比对（官网 vs 自建页面，DOM 签名 + 英文残留）

设计纪律（见 .project/workwork.md）:
  - 单文件单入口：新增能力一律作为本文件的子命令，不新建脚本
  - 每个外部调用（git/curl/node）都带超时
  - 按目标选直连/代理：perfetto.dev 走代理，GitHub Pages/localhost 直连
"""
import argparse
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = REPO_DIR.parent
PERFETTO_DIR = Path(os.environ.get("PERFETTO_DIR", PROJECT_ROOT / "perfetto"))
LAST_SYNC_FILE = SCRIPT_DIR / "LAST_SYNC"
CACHE_DIR = REPO_DIR / ".cache" / "structure"

PROXY = os.environ.get("WORKWORK_PROXY", "http://127.0.0.1:7897")
OFFICIAL_BASE = "https://perfetto.dev"
LIVE_BASE = "https://gugu-perf.github.io/perfetto-docs-zh-cn"
TIMEOUT_GIT = 180
TIMEOUT_FETCH = 15
TIMEOUT_BUILD = 600

_IS_TTY = sys.stdout.isatty()
if os.name == "nt" and _IS_TTY:
    os.system("")  # 启用 Windows ANSI 支持


def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if _IS_TTY else str(s)


def info(msg):    print(_c("34", f"[INFO] {msg}"))
def ok(msg):      print(_c("32", f"[✓] {msg}"))
def warn(msg):    print(_c("33", f"[!] {msg}"))
def err(msg):     print(_c("31", f"[✗] {msg}"))
def step(n, msg): print(f"\n=== 步骤 {n}: {msg} ===")


def run(cmd, cwd=None, timeout=TIMEOUT_GIT, check=True, capture=False, env=None):
    """带超时的子进程执行。"""
    p = subprocess.run(cmd, cwd=cwd, timeout=timeout, check=False,
                       capture_output=capture, text=True, env=env)
    if check and p.returncode != 0:
        out = (p.stdout or "") + (p.stderr or "") if capture else ""
        raise RuntimeError(f"命令失败({p.returncode}): {' '.join(map(str, cmd))}\n{out[-2000:]}")
    return p


def git(args, cwd=None, timeout=TIMEOUT_GIT, check=True):
    return run(["git"] + args, cwd=cwd or PERFETTO_DIR, timeout=timeout, check=check)


def git_out(args, cwd=None, timeout=TIMEOUT_GIT):
    return run(["git"] + args, cwd=cwd or PERFETTO_DIR, timeout=timeout,
               capture=True).stdout.strip()


# ============================================================
# sync-check / sync-update
# ============================================================

def read_last_sync():
    if not LAST_SYNC_FILE.exists():
        return None, None
    for line in LAST_SYNC_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line, line.split()[0]
    return None, None


def ensure_perfetto_repo():
    if not (PERFETTO_DIR / ".git").exists():
        warn(f"Perfetto 仓库不存在，克隆到 {PERFETTO_DIR} ...")
        run(["git", "clone", "https://github.com/google/perfetto.git", str(PERFETTO_DIR)],
            cwd=PROJECT_ROOT, timeout=600)
        ok("克隆完成")


def cmd_sync(args):
    ensure_perfetto_repo()
    last_line, last_commit = read_last_sync()

    info("强制同步上游仓库与远程一致...")
    git(["clean", "-fd"], check=False)
    git(["reset", "--hard", "HEAD"], check=False)
    git(["checkout", "main"], check=False)
    git(["pull", "origin", "main", "--ff-only"])

    if args.command == "sync-check":
        print()
        info("上次同步点:")
        print(f"  {last_line or 'unknown'}")
        head_short = git_out(["log", "-1", "--format=%h", "HEAD", "--", "docs/"])
        head_date = git_out(["log", "-1", "--format=%cd", "--date=short", "HEAD", "--", "docs/"])
        head_msg = git_out(["log", "-1", "--format=%s", "HEAD", "--", "docs/"])
        print()
        info("上游最新:")
        print(f"  Commit: {head_short}\n  日期: {head_date}\n  描述: {head_msg}\n")

        if not last_commit or git(["cat-file", "-e", last_commit], check=False).returncode != 0:
            warn("LAST_SYNC 中的 commit 本地不存在（可能重新 clone）")
            sys.exit(1)
        changes = git_out(["diff", "--name-only", last_commit, "HEAD", "--", "docs/"])
        if not changes:
            ok("docs/ 目录已是最新，无需同步")
            return
        files = [l for l in changes.splitlines() if l.strip()]
        warn(f"发现 docs/ 更新，共 {len(files)} 个文件：")
        print("\n".join(files[:20]))
        print()
        print(f"建议: python3 .project/workwork.py audit 后按 diff 翻译，完成后 sync-update")
        sys.exit(1)

    # sync-update
    print()
    info("更新 LAST_SYNC ...")
    h = git_out(["log", "-1", "--format=%h", "origin/main", "--", "docs/"])
    ci = git_out(["log", "-1", "--format=%ci", "origin/main", "--", "docs/"]).split()
    date, tm, tz = ci[0], ci[1], ci[2]
    msg = git_out(["log", "-1", "--format=%s", "origin/main", "--", "docs/"])
    line = f"{h} {date} {tm} {tz} {msg}"
    LAST_SYNC_FILE.write_text(
        "# LAST_SYNC - 上游同步记录文件\n#\n"
        f"# 更新方式: python3 .project/workwork.py sync-update\n\n{line}\n",
        encoding="utf-8")
    ok(f"LAST_SYNC 已更新: {line}")


# ============================================================
# audit — 全量结构审计
# ============================================================

def strip_fences(text):
    out, in_fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


# A12 辅助：围栏块提取与代码注释行识别（注释行按政策 B 可翻译，比对时过滤）
_CODE_COMMENT = re.compile(r"^\s*(//|#|--|;|/\*|\*)")
# 行尾注释剥离（对称应用于两侧：行尾注释按政策 B 可翻译；
# 剥离过度也是对称的，只在"译了被剥离区域"时误报，届时人工复核）
_TRAILING_COMMENT = re.compile(r"\s+(//|#|--)[^\n]*$")


def _code_part(line):
    return _TRAILING_COMMENT.sub("", line.rstrip())


def _fenced_blocks(text):
    out, cur, in_fence = [], None, False
    for line in text.splitlines():
        if line.startswith("```"):
            if in_fence:
                out.append(cur)
            else:
                cur = []
            in_fence = not in_fence
            continue
        if in_fence:
            cur.append(line)
    return out


def upstream_md(rel):  # rel 相对 docs/，返回英文原文或 None
    p = subprocess.run(["git", "-C", str(PERFETTO_DIR), "show", f"HEAD:docs/{rel}"],
                       capture_output=True, text=True, timeout=TIMEOUT_GIT)
    return p.stdout if p.returncode == 0 and p.stdout.strip() else None


CALLOUT_RE = re.compile(r"^\s*(NOTE|TIP|WARNING|TODO|FIXME|Summary):")
HEAD_RE = re.compile(r"^#{1,6} ", re.M)


def url_set(text, base):
    urls = set()
    for m in re.finditer(r"\]\(([^)\n]+)\)", text):
        u = m.group(1).split(" ")[0]
        if not u or u.startswith("#"):
            continue
        if u.startswith(("http", "mailto:")):
            urls.add(u)
        else:
            urls.add("/" + posixpath.normpath(posixpath.join(base, u)).lstrip("/"))
    return urls


def cmd_audit(args):
    if not (PERFETTO_DIR / ".git").exists():
        err(f"上游仓库不存在: {PERFETTO_DIR}"); sys.exit(2)
    head = git_out(["rev-parse", "--short", "HEAD"])
    upstream_files = [l.removeprefix("docs/")
                      for l in git_out(["ls-tree", "-r", "--name-only", "HEAD", "docs/"]).splitlines()
                      if l.endswith(".md")]
    targets = ([f.removeprefix("docs/") for f in args.files]
               if args.files else upstream_files)
    print(f"=== audit 结构审计 (上游 {head}): {len(targets)} 个文件（上游共 {len(upstream_files)} 个 md）===\n")

    issues = []

    def report(msg):
        issues.append(msg)
        print(msg)

    if not args.files:  # A1 文件清单
        up_set = set(upstream_files)
        for f in upstream_files:
            if not (REPO_DIR / "docs" / f).exists():
                report(f"A1 漏翻/缺失: docs/{f}")
        for f in sorted((REPO_DIR / "docs").rglob("*.md")):
            rel = f.relative_to(REPO_DIR / "docs").as_posix()
            if rel not in up_set:
                report(f"A1 上游已删除未同步: docs/{rel}")

    for f in targets:
        local_path = REPO_DIR / "docs" / f
        if not local_path.exists():
            continue
        up_raw = upstream_md(f)
        if up_raw is None:
            continue
        loc_raw = local_path.read_text(encoding="utf-8")
        up, loc = strip_fences(up_raw), strip_fences(loc_raw)
        base = posixpath.join("docs", posixpath.dirname(f) or ".")

        uh, lh = len(HEAD_RE.findall(up)), len(HEAD_RE.findall(loc))
        if uh != lh:
            report(f"A2 标题数 docs/{f}: 上游={uh} 本地={lh}")
        uf, lf = up_raw.count("\n```") * 0 + sum(1 for l in up_raw.splitlines() if l.startswith("```")), \
                 sum(1 for l in loc_raw.splitlines() if l.startswith("```"))
        if uf != lf:
            report(f"A3 代码围栏 docs/{f}: 上游={uf} 本地={lf}")
        ut, lt = sum(1 for l in up.splitlines() if l.lstrip().startswith("|")), \
                 sum(1 for l in loc.splitlines() if l.lstrip().startswith("|"))
        if ut != lt:
            report(f"A4 表格行 docs/{f}: 上游={ut} 本地={lt}（近似）")
        ui, li = sum(1 for l in up.splitlines() if l.startswith("!\[")), \
                 sum(1 for l in loc.splitlines() if l.startswith("!\["))
        if ui != li:
            report(f"A5 图片数 docs/{f}: 上游={ui} 本地={li}")
        if url_set(up, base) != url_set(loc, base):
            report(f"A6 链接URL集合 docs/{f} 与上游不一致")
        uc, lc = len(CALLOUT_RE.findall(up, re.M)), len(CALLOUT_RE.findall(loc, re.M))
        if uc != lc:
            report(f"A7 提示框数 docs/{f}: 上游={uc} 本地={lc}")

        # A8 显式锚点：上游有而本地缺 = 真欠账（深链破坏）。
        # 本地多出的锚点是合法适配：中文标题自动 slug 与英文不同，为保链接
        # 目标需要显式声明，不算差异。
        anchor = re.compile(r"^#{1,6}[^{\n]*\{#([\w_.-]+)\}", re.M)
        ua, la = anchor.findall(up), set(anchor.findall(loc))
        missing = [a for a in ua if a not in la]
        if missing:
            report(f"A8 缺失锚点 docs/{f}: {missing}")

        # A9 代码块语言标签序列（语言标记不变）
        langtag = re.compile(r"^```(\S*)", re.M)
        ul, ll = langtag.findall(up_raw), langtag.findall(loc_raw)
        if ul != ll:
            report(f"A9 语言标签 docs/{f}: 上游={ul} 本地={ll}")

        # A10/A11 行内代码 span 数 / 加粗斜体数（段落感知：剥离列表符后按段落
        # 跨行合并再计数——上游英文 80 列硬换行会把 span 拆到多行，按行统计
        # 会产生系统性假阳性/假阴性）
        def para_join(text):
            lines = [re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", ln)
                     for ln in text.splitlines()]
            return re.sub(r"(?<!\n)\n(?!\n)", " ", "\n".join(lines))

        upj, locj = para_join(up), para_join(loc)
        uc2 = len(re.findall(r"`[^`]+`", upj))
        lc2 = len(re.findall(r"`[^`]+`", locj))
        if uc2 != lc2:
            report(f"A10 行内代码数 docs/{f}: 上游={uc2} 本地={lc2}")
        ub, lb = emph_count(up), emph_count(loc)
        if ub != lb:
            report(f"A11 加粗/斜体数 docs/{f}: 上游={ub} 本地={lb}")

        # A12 代码块非注释行必须与上游逐字节一致（代码本体不翻译的不变量——
        # 抓缩进塌缩/NBSP 丢失/标点混入等 DOM 签名不可见的缺陷；注释行按
        # 政策 B 可翻译，过滤后比对序列）
        zblocks = _fenced_blocks(loc_raw)
        eblocks = _fenced_blocks(up_raw)
        if len(zblocks) != len(eblocks):
            report(f"A12 代码块数 docs/{f}: 上游={len(eblocks)} 本地={len(zblocks)}")
        else:
            for bi_, (zl, el) in enumerate(zip(zblocks, eblocks)):
                zc = [_code_part(l) for l in zl if not _CODE_COMMENT.match(l)]
                ec = [_code_part(l) for l in el if not _CODE_COMMENT.match(l)]
                if zc != ec:
                    report(f"A12 代码行不一致 docs/{f} 第{bi_+1}块"
                           f"（如: 上游 {next((repr(x) for x, y in zip(ec, zc) if x != y), ec[:1])!r}"
                           f" vs 本地 {next((repr(y) for x, y in zip(ec, zc) if x != y), zc[:1])!r}）")

    # A7b 幽灵引用（含 .json 数据文件——它们会注入翻译 prompt，引用错误会误导子代理）
    for doc in list(SCRIPT_DIR.glob("*.md")) + list(SCRIPT_DIR.glob("*.json")) \
            + [REPO_DIR / "README.md", REPO_DIR / "CONTRIBUTING.md"]:
        if not doc.exists():
            continue
        for ref in set(re.findall(r"\.project/[A-Za-z0-9_./-]+\.(?:sh|py|md|json)",
                                  doc.read_text(encoding="utf-8"))):
            if not (REPO_DIR / ref).exists():
                report(f"A7b 幽灵引用: {ref}（{doc.name} 引用但不存在）")

    print(f"\n==== 审计结果: {len(issues)} 项差异 ====")
    if issues:
        print("存在欠账，请按清单修复 ❌"); sys.exit(1)
    print("全部通过 ✅")


# ============================================================
# proofread — 术语/标志/标点 lint
# ============================================================

CJK = r"\u4e00-\u9fff\u3400-\u4dbf"


def iter_prose(text):
    in_fence = False
    for i, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield i, re.sub(r"`[^`]*`", "", raw)


def cmd_proofread(args):
    glossary = json.loads((SCRIPT_DIR / "glossary.json").read_text(encoding="utf-8"))
    forbidden = [(t["en"], z) for t in glossary["terms"] for z in t.get("forbidden", []) if z]
    zh_markers = glossary.get("markers", {}).get("forbidden_zh_markers", [])
    fw_markers = glossary.get("markers", {}).get("forbidden_fullwidth_colon", [])

    files = (sorted((REPO_DIR / "docs").rglob("*.md")) if args.all
             else [Path(f).resolve() for f in args.files])
    if not files:
        err("用法: proofread --all 或 proofread <文件...>"); sys.exit(2)

    total_e = total_w = 0
    for f in files:
        errors, warnings = [], []
        for lineno, line in iter_prose(f.read_text(encoding="utf-8")):
            if not line.strip():
                continue
            for en, zh in forbidden:
                if zh in line:
                    errors.append((lineno, "E1", f"术语 [{en}] 应保持英文，出现「{zh}」"))
            for m in fw_markers:
                if line.lstrip().startswith(m):
                    errors.append((lineno, "E2", f"标志误用全角冒号: {m} → {m[:-1]}:"))
            for m in zh_markers:
                if line.lstrip().startswith(m):
                    warnings.append((lineno, "W2", f"段首中文标志词「{m}」需对照上游确认为纯文本"))
            if re.match(rf"^\s*(Note|note|Tip|tip|Caution|Warning)\s*:\s*[^\x00-\x7f]", line):
                warnings.append((lineno, "W3", "英文引导词+中文内容（非 callout，应翻译）"))
            if re.search(f"[{CJK}]\\s*\\.\\s*$", line):
                errors.append((lineno, "E3", "中文语句以半角句号结尾"))
            if re.search(f"[{CJK}],[{CJK}]", line):
                errors.append((lineno, "E3", "中文之间使用半角逗号"))
            # 注：强调闭合符与全角标点的兼容性以 compare-structure（真实渲染）为
            # 权威判定——曾试加 E4 启发式规则但在已验证正常的语料上误报，已移除。
            # 已知坑（详见 workwork.md 4.5）：_中文_ 斜体不可靠、闭合符紧邻
            # 全角标点在特定前驱字符下可能失效，出现字面星号时用
            # compare-structure --page 定位。
            for m in re.finditer(f"([{CJK}])([A-Za-z0-9])|([A-Za-z0-9])([{CJK}])", line):
                frag = line[max(0, m.start() - 8):m.end() + 8]
                warnings.append((lineno, "W1", f"中英文之间建议加空格: ...{frag}..."))
        if errors or warnings:
            print(f"\n== {f.relative_to(REPO_DIR)} ==")
            for ln, code, msg in errors + warnings:
                print(f"  L{ln} [{code}] {msg}")
        total_e += len(errors)
        total_w += len(warnings)

    print(f"\n==== proofread: {len(files)} 文件 | 错误 {total_e} | 警告 {total_w} ====")
    failed = total_e > 0 or (args.strict and total_w > 0)
    print("结果: 未通过" if failed else "结果: 通过")
    sys.exit(1 if failed else 0)


# A11 加粗/斜体计数：先归一化再数 `*`——把"可渲染的" `_x_`（两侧非词字符边界，
# 含 `__x__` 粗体）统一替换为 `*x*` 后用原正则计数。只数 `*` 会把中文的正确
# 改写（CJK 内嵌 `_x_` 无法闭合，须改成 `*x*` 才渲染为 <em>）误报为多出；
# 而无法渲染的 `_中文_内嵌` 形式不会被归一化，漏写/多写仍会被发现。
# 同时剥离代码围栏：块内注释已译，`_`/`*` 计数天然不对称。
# 另需剥离（两侧对称，不影响真差异检出）：
#   - 行内代码 `...`（`tail_` 的 `_` 会被归一化成 `*` 造成幻影配对）
#   - 链接引用定义行 [label]: url（URL 中的 `_` 同理）
#   - 列表标记 `* ` / `- ` / `1. `（上游 `*` 弹列表符会与下一个列表符配对
#     成幻影强调，且中文译文惯用 `-`，导致上游计数虚高）
_EMPH_FENCE = re.compile(r"```.*?```", re.S)
_EMPH_CODE = re.compile(r"`[^`\n]*`")
_EMPH_REFDEF = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*\S+", re.M)
_EMPH_LISTMARK = re.compile(r"^\s{0,3}(?:[-*+]|\d+\.)\s+", re.M)
_EMPH_ASTER = re.compile(r"\*\*[^*]+\*\*|(?<!\*)\*[^*\s][^*]*\*(?!\*)")


def emph_count(text):
    t = _EMPH_FENCE.sub(" ", text)
    t = _EMPH_REFDEF.sub(" ", t)
    t = _EMPH_CODE.sub(" ", t)
    t = _EMPH_LISTMARK.sub(" ", t)
    # 转义下划线 \_（如 trace\_processor）不是强调定界符，排除
    t = re.sub(r"(?<![\\\w_])_(?=\S)", "*", t)
    t = re.sub(r"(?<=\S)_(?![\w_\\])", "*", t)
    return len(_EMPH_ASTER.findall(t))


# ============================================================
# compare-structure — 渲染层比对
# ============================================================

SKIP_TAGS = {"script", "style", "nav", "head"}
STRUCTURAL_CLASS = re.compile(
    r"^(callout|note|tip|warning|todo|summary|tabs|tab-content|mermaid|"
    r"hljs|language-\S+|md-tabs|md-tab|datagrid|table|codehilite)")
ENGLISH_FN_WORDS = re.compile(
    r"\b(the|and|with|for|you|your|this|that|from|will|can|not|are|was|when|"
    r"which|into|onto|over|under|here|there|see|use|using)\b", re.I)


class SigParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_main = self._skip = False
        self.depth = 0
        self.sig, self.prose = [], []
        self._buf = self._buf_tag = None

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip = True
            return
        if self._skip or (not self.in_main and tag != "main"):
            return
        cls = dict(attrs).get("class", "") or ""
        if tag == "main" and "md-content" in cls:
            self.in_main, self.depth = True, 0
            return
        if not self.in_main:
            return
        keep = ".".join(sorted(c for c in cls.split() if STRUCTURAL_CLASS.match(c)))
        self.sig.append((self.depth, tag, keep))
        if tag in ("p", "li"):
            self._buf, self._buf_tag = [], tag
        self.depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip = False
            return
        if self._skip or not self.in_main:
            return
        self.depth -= 1
        if tag == self._buf_tag and self._buf is not None:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if text and not re.search(f"[{CJK}]", text):
                self.prose.append((tag, text))
            self._buf = self._buf_tag = None
        if tag == "main":
            self.in_main = False

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)


def prose_whitelisted(text):
    if re.match(r"^[\d\s.,:;/()%\-+*=<>#_|~\[\]{}\"'`!?·—-]+$", text):
        return True
    if re.match(r"^(TODO|FIXME|NOTE|TIP|WARNING|Summary)[:：]", text):
        return True
    if len(text) <= 4:
        return True
    tokens = text.split()
    if all(re.search(r"[_.\-/>=]", t) for t in tokens):
        return True
    if not ENGLISH_FN_WORDS.search(text) and len(tokens) <= 6:
        return True
    return False


def parse_html_file(path):
    p = SigParser()
    p.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    return p.sig, p.prose


def normalize_sig(sig, tolerate_hljs=True):
    """按政策 B 归一化签名：hljs-* 高亮类差异源于代码注释翻译（已接受的惯例）。

    - hljs 变体类统一为 'hljs'（注释译文的分词变化只改类名，不改结构）
    - 连续的 (depth, tag, 'hljs') 条目折叠为一条（注释行合并/拆行不改变结构）
    --strict-hljs 时跳过归一化，严格逐元素比对。
    """
    if not tolerate_hljs:
        return sig
    out = []
    for d, t, c in sig:
        if "hljs" in c:
            entry = (d, t, "hljs")
            if out and out[-1] == entry:
                continue
            out.append(entry)
        else:
            out.append((d, t, c))
    return out


def fetch(url, dest, use_proxy):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    handlers = []
    if use_proxy:
        handlers.append(urllib.request.ProxyHandler(
            {"http": PROXY, "https": PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [("User-Agent", "workwork-py")]
    try:
        with opener.open(url, timeout=TIMEOUT_FETCH) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        return False


def toc_pages():
    pages = set()
    for m in re.finditer(r"\]\(([^)\n]+)\)", (REPO_DIR / "docs" / "toc.md").read_text(encoding="utf-8")):
        u = m.group(1)
        if u.endswith(".md") and not u.startswith("#") and not u.startswith("http"):
            pages.add(u.removesuffix(".md").removeprefix("docs/"))
    return sorted(pages)


def build_site(out_name, docs_zh: bool):
    """构建一份站点到 out/<out_name>/site。docs_zh=True 用中文 docs，否则从 git HEAD 恢复英文。

    双构建对比的基础：同一上游 commit、同一 build.mjs（含同一首页补丁）、同一 CSS。
    """
    if not (PERFETTO_DIR / "infra/perfetto.dev/build").exists():
        err("仅支持新构建系统（build.mjs），上游仓库过旧")
        sys.exit(2)
    if docs_zh:
        shutil.rmtree(PERFETTO_DIR / "docs", ignore_errors=True)
        shutil.copytree(REPO_DIR / "docs", PERFETTO_DIR / "docs")
    else:
        run(["git", "restore", "docs/"], cwd=PERFETTO_DIR, check=False)
    patch_homepage()
    out_dir = PERFETTO_DIR / "out" / out_name
    p = run([str(PERFETTO_DIR / "infra/perfetto.dev/build"), "--out", f"out/{out_name}"],
            cwd=PERFETTO_DIR, timeout=TIMEOUT_BUILD, check=False, capture=True)
    if p.returncode != 0 or not (out_dir / "site").exists():
        err(f"构建失败（{out_name}）:\n" + "\n".join((p.stdout or "").splitlines()[-15:]))
        sys.exit(1)
    return out_dir / "site"


def classify_diff(sig_o, sig_l, i):
    """把首个差异元素归类：hljs=代码高亮类（注释翻译）、inline=行内格式互换、struct=结构差异。"""
    a, b = sig_o[i], sig_l[i]
    if "hljs" in a[2] or "hljs" in b[2]:
        return "hljs"
    if {a[1], b[1]} <= {"strong", "em", "code"}:
        return "inline"
    return "struct"


def cmd_compare_structure(args):
    pages = [args.page.removesuffix(".md").removeprefix("docs/")] if args.page else toc_pages()

    if args.live:
        # 部署抽查模式：本地中文构建 vs 线上抓取（验证部署路径，非内容）
        zh_site = build_site("zh-site", docs_zh=True)
        total = failed = miss = t_total = 0
        report_lines = []
        for p in pages:
            total += 1
            zh_file = zh_site / "docs" / ("index.html" if p == "README" else p)
            cache_f = CACHE_DIR / "live" / p.replace("/", "__")
            cache_f.parent.mkdir(parents=True, exist_ok=True)
            if args.refresh:
                cache_f.unlink(missing_ok=True)
            if not fetch(f"{LIVE_BASE}/docs/{p}.html", cache_f, use_proxy=False):
                miss += 1
                report_lines.append(f"  ❌ {p}: 线上抓取失败")
                continue
            if not zh_file.exists():
                miss += 1
                report_lines.append(f"  ❌ {p}: 本地构建产物缺失")
                continue
            sig_o, _ = parse_html_file(cache_f)
            sig_l, prose_l = parse_html_file(zh_file)
            diffs = [(i, f"{sig_o[i]} vs {sig_l[i]}") for i in range(min(len(sig_o), len(sig_l)))
                     if sig_o[i] != sig_l[i]]
            resid = [x for _, x in prose_l if not prose_whitelisted(x)]
            t_total += len(resid)
            if diffs or len(sig_o) != len(sig_l):
                failed += 1
                report_lines.append(f"  ⚠️  {p}: {diffs[0][1] if diffs else f'元素总数 {len(sig_o)} vs {len(sig_l)}'}")
            print(f"\r[{total}] {p:<46} {'差异' if (diffs or len(sig_o) != len(sig_l)) else 'OK'}   ",
                  end="", flush=True)
        print("\n")
        print(f"==== 部署抽查(线上 vs 本地构建): 总计 {total} | 差异 {failed} | 失败 {miss} | 残留候选 {t_total} ====")
        if report_lines:
            print("\n".join(report_lines)); sys.exit(1)
        print("线上与本地构建一致，部署路径正常 ✅")
        return

    # 默认：双构建对比（同一上游 commit 的英文站 vs 中文站，文件级，无网络）
    info("双构建对比：构建英文站（git HEAD docs）...")
    en_site = build_site("en-site", docs_zh=False)
    info("双构建对比：构建中文站...")
    zh_site = build_site("zh-site", docs_zh=True)

    total = failed = t_total = 0
    cats = {"hljs": 0, "inline": 0, "struct": 0}
    report_lines, detail = [], []
    for p in pages:
        total += 1
        rel = "index.html" if p == "README" else p
        en_f, zh_f = en_site / "docs" / rel, zh_site / "docs" / rel
        if not (en_f.exists() and zh_f.exists()):
            report_lines.append(f"  ❌ {p}: 构建产物缺失(en={en_f.exists()} zh={zh_f.exists()})")
            continue
        sig_e, _ = parse_html_file(en_f)
        sig_z, prose_z = parse_html_file(zh_f)
        # 政策 B：容忍 hljs 高亮类差异（代码注释翻译惯例），--strict-hljs 严查
        sig_e, sig_z = normalize_sig(sig_e, not args.strict_hljs), normalize_sig(sig_z, not args.strict_hljs)
        diffs = [(i, f"第{i}个元素: {sig_e[i]} vs {sig_z[i]}")
                 for i in range(min(len(sig_e), len(sig_z))) if sig_e[i] != sig_z[i]]
        if not diffs and len(sig_e) != len(sig_z):
            diffs = [(-1, f"元素总数: {len(sig_e)} vs {len(sig_z)}")]
        resid = [x for _, x in prose_z if not prose_whitelisted(x)]
        t_total += len(resid)
        if diffs:
            failed += 1
            cat = classify_diff(sig_e, sig_z, diffs[0][0]) if diffs[0][0] >= 0 else "struct"
            cats[cat] += 1
            report_lines.append(f"  ⚠️  [{cat}] {p}: {diffs[0][1]}")
            detail.append((p, cat, diffs))
        print(f"\r[{total}] {p:<46} {'差异' if diffs else 'OK'}   ", end="", flush=True)

    print("\n")
    print(f"==== 双构建比对: 总计 {total} | 差异页 {failed} "
          f"| 高亮类 {cats['hljs']} 行内格式 {cats['inline']} 结构 {cats['struct']} "
          f"| 英文残留候选 {t_total} ====")
    if report_lines:
        print("\n".join(report_lines))
        if args.verbose:
            print("\n---- 全量差异明细 ----")
            for p, cat, diffs in detail:
                for _, d in diffs:
                    print(f"  [{cat}] {p}: {d}")
        sys.exit(1)
    print("全部页面 DOM 结构一致（同一构建器/CSS，渲染必然一致）✅")


# ============================================================
# deploy-local / deploy-gh-pages
# ============================================================

def port_in_use(port):
    try:
        out = run(["lsof", "-Pi", f":{port}", "-sTCP:LISTEN", "-t"],
                  check=False, capture=True, timeout=10).stdout.strip()
        return bool(out)
    except Exception:
        return False


def cleanup_port(port):
    if port_in_use(port):
        info(f"清理端口 {port} 占用...")
        run(["bash", "-c", f"lsof -Pi :{port} -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true"],
            check=False, timeout=15)
        time.sleep(2)


HOMEPAGE_PATCH_OLD = """  pages.push({
    key: "index",
    markdown: null,
    mdFile: tmplIndex,
    templatePath: tmplIndex,
    sitePath: "index.html",
  });"""
HOMEPAGE_PATCH_NEW = """  pages.push({
    key: "index",
    markdown: fs.readFileSync(pjoin(DOCS_DIR, "README.md"), "utf8"),
    mdFile: pjoin(DOCS_DIR, "README.md"),
    templatePath: tmplMarkdown,
    sitePath: "index.html",
  });"""


def patch_homepage():
    build_mjs = PERFETTO_DIR / "infra/perfetto.dev/src/build.mjs"
    if not build_mjs.exists():
        return  # 旧构建系统：BUILD.gn 路径已随上游迁移废弃
    s = build_mjs.read_text(encoding="utf-8")
    if HOMEPAGE_PATCH_NEW in s:
        ok("首页补丁已就绪")
        return
    if HOMEPAGE_PATCH_OLD not in s:
        err("build.mjs 首页补丁失败（模板不匹配，上游可能已变更）")
        sys.exit(1)
    build_mjs.write_text(s.replace(HOMEPAGE_PATCH_OLD, HOMEPAGE_PATCH_NEW, 1), encoding="utf-8")
    ok("首页配置已修改（README.md 渲染 / 首页）")


def run_build(use_new):
    info("清理旧构建输出...")
    shutil.rmtree(PERFETTO_DIR / "out/perfetto.dev", ignore_errors=True)
    if use_new:
        info("构建（build.mjs，约 10-60 秒）...")
        p = run([str(PERFETTO_DIR / "infra/perfetto.dev/build")], cwd=PERFETTO_DIR,
                timeout=TIMEOUT_BUILD, check=False, capture=True)
        if p.returncode != 0:
            err("构建失败，最后 30 行:")
            print("\n".join((p.stdout or "").splitlines()[-30:]))
            sys.exit(1)
    else:
        info("构建（旧 GN+ninja，约 2-5 分钟）...")
        p = run(["node", "infra/perfetto.dev/build.js"], cwd=PERFETTO_DIR,
                timeout=TIMEOUT_BUILD, check=False, capture=True)
        if p.returncode != 0:
            err("构建失败")
            sys.exit(1)
    site_index = PERFETTO_DIR / "out/perfetto.dev/site/index.html"
    if not site_index.exists():
        err("构建输出缺失: out/perfetto.dev/site/index.html")
        sys.exit(1)
    # fail-closed 断言：首页必须是中文 README 渲染
    if "什么是 Perfetto" not in site_index.read_text(encoding="utf-8"):
        err("首页断言失败：index.html 不含「什么是 Perfetto」——上游构建/补丁可能失效")
        err("参考 .project/plan/ 的 fail-closed 防护设计")
        sys.exit(1)
    ok("构建完成 + 首页断言通过")


def fix_gh_pages_paths(temp, repo_name):
    """路径修补（原 sed 逻辑的跨平台移植）+ fail-closed 校验。"""
    for f in (temp / "docs").iterdir():
        if f.is_file() and "." not in f.name:
            f.rename(f.with_name(f.name + ".html"))
    for f in (temp / "docs").rglob("*"):
        if f.is_file() and f.suffix not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".html"):
            f.rename(f.with_name(f.name + ".html"))
    subs = [
        ('href="/assets/', f'href="/{repo_name}/assets/'),
        ('src="/assets/', f'src="/{repo_name}/assets/'),
        ('href="/docs/', f'href="/{repo_name}/docs/'),
        ('src="/docs/', f'src="/{repo_name}/docs/'),
        ('data="/docs/', f'data="/{repo_name}/docs/'),
        ('href="/"', f'href="/{repo_name}/"'),
    ]
    for f in temp.rglob("*.html"):
        s = f.read_text(encoding="utf-8")
        for a, b in subs:
            s = s.replace(a, b)
        s = re.sub(rf'href="/{repo_name}/docs/([^"]*)"', lambda m: f'href="/{repo_name}/docs/{m.group(1)}.html"', s)
        s = s.replace(f'href="/{repo_name}/docs/.html"', f'href="/{repo_name}/docs/"')
        f.write_text(s, encoding="utf-8")
    js = temp / "assets/script.js"
    if js.exists():
        js.write_text(js.read_text(encoding="utf-8")
                      .replace('"/assets/mermaid.min.js"', f'"/{repo_name}/assets/mermaid.min.js"'),
                      encoding="utf-8")
    css = temp / "assets/style.css"
    if css.exists():
        css.write_text(css.read_text(encoding="utf-8")
                       .replace('"/assets/sprite.png"', f'"/{repo_name}/assets/sprite.png"'),
                       encoding="utf-8")
    (temp / ".nojekyll").touch()

    # fail-closed 校验
    idx = (temp / "index.html").read_text(encoding="utf-8")
    checks = [
        (f'href="/{repo_name}/assets/style.css"' in idx, "style.css 前缀缺失"),
        (f'src="/{repo_name}/assets/script.js"' in idx, "script.js 前缀缺失"),
        (f'href="/{repo_name}/docs/' in idx, "docs 链接前缀缺失"),
        ("什么是 Perfetto" in idx, "首页中文断言失败"),
    ]
    bad = [msg for good, msg in checks if not good]
    if bad:
        err(f"路径修补校验失败: {bad}（上游模板可能变更，中止部署）")
        sys.exit(1)
    ok("路径修补校验通过 (fail-closed)")


def cmd_deploy(args):
    cleanup_port(8082)
    ensure_perfetto_repo()

    step(2, "替换为中文文档")
    shutil.rmtree(PERFETTO_DIR / "docs", ignore_errors=True)
    shutil.copytree(REPO_DIR / "docs", PERFETTO_DIR / "docs")
    md_count = sum(1 for _ in (PERFETTO_DIR / "docs").rglob("*.md"))
    if not (PERFETTO_DIR / "docs/README.md").exists():
        err("docs/README.md 缺失"); sys.exit(1)
    ok(f"中文文档已复制（{md_count} 个 md）")

    patch_homepage()

    use_new = (PERFETTO_DIR / "infra/perfetto.dev/build").exists() and \
              not (PERFETTO_DIR / "infra/perfetto.dev/build.js").exists()
    info(f"构建系统: {'build.mjs（新）' if use_new else 'GN+ninja（旧）'}")
    run_build(use_new)

    if args.command == "deploy-gh-pages":
        step(3, "部署到 gh-pages")
        repo_name = REPO_DIR.name
        temp = Path(tempfile.mkdtemp(prefix="ghpages-"))
        shutil.copytree(PERFETTO_DIR / "out/perfetto.dev/site", temp, dirs_exist_ok=True)
        fix_gh_pages_paths(temp, repo_name)

        run(["git", "init"], cwd=temp)
        run(["git", "config", "user.email", "deploy@perfetto-docs.local"], cwd=temp)
        run(["git", "config", "user.name", "Deploy Bot"], cwd=temp)
        run(["git", "add", "-A"], cwd=temp)
        run(["git", "commit", "-m", "Deploy to GitHub Pages"], cwd=temp)

        # 回退点：旧 gh-pages 打 pre-deploy-* tag
        old = run(["git", "ls-remote", str(REPO_DIR), "gh-pages"],
                  check=False, capture=True).stdout.split()[0] if \
            run(["git", "ls-remote", str(REPO_DIR), "gh-pages"], check=False, capture=True).stdout.strip() else None
        tag = None
        if old:
            tag = f"pre-deploy-{time.strftime('%Y%m%d-%H%M%S')}"
            run(["git", "fetch", str(REPO_DIR), "gh-pages"], cwd=temp, check=False)
            run(["git", "tag", tag, "FETCH_HEAD"], cwd=temp, check=False)
            run(["git", "push", str(REPO_DIR), f"refs/tags/{tag}"], cwd=temp, check=False)
            info(f"回退点: {tag} → {old[:7]}（回退: workwork.py rollback-gh-pages）")

        run(["git", "push", "--force", str(REPO_DIR), "main:gh-pages"], cwd=temp)
        run(["git", "push", "origin", "gh-pages", "--force"], cwd=REPO_DIR)
        if tag:
            run(["git", "push", "origin", f"refs/tags/{tag}"], cwd=REPO_DIR, check=False)
        shutil.rmtree(temp, ignore_errors=True)
        ok(f"GitHub Pages 部署成功: https://gugu-perf.github.io/{repo_name}/")
        return

    # deploy-local: 启动服务器
    step(3, "启动本地服务器")
    log = tempfile.NamedTemporaryFile(prefix="perfetto-server-", suffix=".log", delete=False)
    cmd = [str(PERFETTO_DIR / "infra/perfetto.dev/build"), "--serve"] if use_new \
        else ["node", "infra/perfetto.dev/build.js", "--serve"]
    subprocess.Popen(cmd, cwd=PERFETTO_DIR, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(30):
        time.sleep(1)
        if port_in_use(8082):
            ok("服务器已启动: http://localhost:8082/docs/")
            info(f"日志: {log.name}")
            return
    err("服务器未能在 30 秒内启动，检查日志: " + log.name)
    sys.exit(1)


def cmd_rollback(args):
    run(["git", "fetch", "origin", "--tags"], cwd=REPO_DIR, check=False)
    tag = args.tag
    if not tag:
        tags = git_out(["tag", "-l", "pre-deploy-*"], cwd=REPO_DIR).splitlines()
        if not tags:
            err("未找到 pre-deploy-* tag"); sys.exit(1)
        tag = sorted(tags)[-1]
    sha = git_out(["rev-parse", f"{tag}^{{commit}}"], cwd=REPO_DIR)
    info(f"回退 gh-pages → {tag} ({sha[:7]})")
    run(["git", "push", "--force", "origin", f"{sha}:refs/heads/gh-pages"], cwd=REPO_DIR)
    ok("完成。等待 1-2 分钟 CDN 刷新后验证")


# ============================================================
# main
# ============================================================

def main():
    ap = argparse.ArgumentParser(prog="workwork.py", description="Perfetto 中文文档统一工具")
    sub = ap.add_subparsers(dest="command", required=True)

    for name in ("deploy-local", "deploy-gh-pages"):
        sub.add_parser(name)
    rp = sub.add_parser("rollback-gh-pages")
    rp.add_argument("tag", nargs="?")
    sub.add_parser("sync-check")
    sub.add_parser("sync-update")

    au = sub.add_parser("audit", help="全量结构审计 vs 上游 git HEAD")
    au.add_argument("--files", nargs="+", help="只审计指定文件")
    pr = sub.add_parser("proofread", help="术语/标志/标点 lint")
    pr.add_argument("--all", action="store_true")
    pr.add_argument("--strict", action="store_true")
    pr.add_argument("files", nargs="*")
    cs = sub.add_parser("compare-structure", help="渲染层比对（默认双构建：同源英文站 vs 中文站）")
    cs.add_argument("--live", action="store_true", help="部署抽查：本地中文构建 vs 线上页面")
    cs.add_argument("--strict-hljs", action="store_true",
                    help="严格比对代码高亮类（默认容忍：注释翻译惯例，政策 B）")
    cs.add_argument("--page", help="单页（如 docs/analysis/xxx.md）")
    cs.add_argument("--refresh", action="store_true")
    cs.add_argument("--verbose", action="store_true", help="输出全量差异明细")

    args = ap.parse_args()
    {"sync-check": cmd_sync, "sync-update": cmd_sync,
     "audit": cmd_audit, "proofread": cmd_proofread,
     "compare-structure": cmd_compare_structure,
     "deploy-local": cmd_deploy, "deploy-gh-pages": cmd_deploy,
     "rollback-gh-pages": cmd_rollback}[args.command](args)


if __name__ == "__main__":
    main()
