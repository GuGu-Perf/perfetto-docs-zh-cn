#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""proofread.sh — 术语与格式校验（翻译质量门禁）

用法:
  python3 .project/proofread.sh docs/analysis/trace-processor.md   # 校验单个文件
  python3 .project/proofread.sh --all                              # 校验 docs/ 全部 md
  python3 .project/proofread.sh --all --strict                     # 警告也计为失败

检查项:
  [E1] 术语违规: glossary.json 中 translate=false 术语的禁用中文译法
       出现在代码块/行内代码之外
  [E2] 标志前缀违规: NOTE:/TIP:/WARNING: 等被汉化（注意：/提示：...），
       或英文标志后跟全角冒号（NOTE：）
  [E3] 标点违规: 中文语句使用半角句号结尾 / 中文之间使用半角逗号
  [W1] (警告) 中英文之间缺少空格

退出码: 0=通过(无 E 类违规), 1=存在 E 类违规(--strict 时 W 类也计入)
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GLOSSARY = Path(__file__).resolve().parent / "glossary.json"

CJK = r'\u4e00-\u9fff\u3400-\u4dbf'


def strip_inline_code(line):
    """移除行内代码 span，避免其中内容参与校验。"""
    return re.sub(r'`[^`]*`', '', line)


def iter_prose_lines(text):
    """产出 (行号, 行内容)，跳过代码块内与行内代码。

    代码块判定: ``` 围栏（允许缩进 0-3 空格）。
    """
    in_fence = False
    for i, raw in enumerate(text.splitlines(), 1):
        stripped = raw.lstrip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield i, raw


def load_glossary():
    data = json.loads(GLOSSARY.read_text(encoding='utf-8'))
    forbidden_terms = []
    for t in data['terms']:
        for f in t.get('forbidden', []):
            if f:
                forbidden_terms.append((t['en'], f))
    markers = data.get('markers', {})
    return (forbidden_terms,
            markers.get('forbidden_zh_markers', []),
            markers.get('forbidden_fullwidth_colon', []))


def check_file(path, forbidden_terms, zh_markers, fw_colon_markers):
    errors, warnings = [], []
    text = path.read_text(encoding='utf-8')

    for lineno, raw in iter_prose_lines(text):
        line = strip_inline_code(raw)
        if not line.strip():
            continue

        # E1 术语违规（禁用中文译法出现在散文中）
        for en, zh in forbidden_terms:
            if zh in line:
                errors.append(
                    (lineno, 'E1', f'术语 [{en}] 应保持英文，出现禁用译法「{zh}」'))

        # E2 标志前缀违规
        for m in zh_markers:
            if line.lstrip().startswith(m):
                errors.append(
                    (lineno, 'E2', f'标志前缀被汉化: 「{m}」应保留英文 (NOTE:/TIP:/WARNING:...)'))
        for m in fw_colon_markers:
            if line.lstrip().startswith(m):
                errors.append(
                    (lineno, 'E2', f'标志前缀后误用全角冒号: 「{m}」应为半角「{m[0:-1]}:」'))

        # E3 标点: 中文行以半角句号结尾
        if re.search(f'[{CJK}]\\s*\\.\\s*$', line):
            errors.append((lineno, 'E3', '中文语句以半角句号「.」结尾，应为「。」'))
        # E3 标点: 中文之间使用半角逗号
        if re.search(f'[{CJK}],[{CJK}]', line):
            errors.append((lineno, 'E3', '中文之间使用半角逗号「,」，应为「，」'))

        # W1 中英文之间缺空格
        for m in re.finditer(f'([{CJK}])([A-Za-z0-9])|([A-Za-z0-9])([{CJK}])', line):
            frag = line[max(0, m.start() - 8):m.end() + 8]
            warnings.append((lineno, 'W1', f'中英文之间建议加空格: ...{frag}...'))

    return errors, warnings


def main():
    raw_args = sys.argv[1:]
    strict = '--strict' in raw_args
    want_all = '--all' in raw_args or 'all' in raw_args
    args = [a for a in raw_args if not a.startswith('--')]

    if not raw_args:
        print(__doc__)
        sys.exit(2)

    forbidden_terms, zh_markers, fw_colon_markers = load_glossary()

    if want_all:
        files = sorted((REPO / 'docs').rglob('*.md'))
    else:
        files = [REPO / a if not Path(a).is_absolute() else Path(a) for a in args]
        files = [f for f in files if f.exists()]
        if not files:
            print(f'错误: 文件不存在: {args}')
            sys.exit(2)

    total_e = total_w = 0
    for f in files:
        errors, warnings = check_file(f, forbidden_terms, zh_markers, fw_colon_markers)
        rel = f.relative_to(REPO)
        if errors or warnings:
            print(f'\n== {rel} ==')
            for lineno, code, msg in errors:
                print(f'  L{lineno} [{code}] {msg}')
            for lineno, code, msg in warnings:
                print(f'  L{lineno} [{code}] {msg}')
        total_e += len(errors)
        total_w += len(warnings)

    print(f'\n==== proofread 汇总: {len(files)} 个文件 | 错误 {total_e} | 警告 {total_w} ====')
    failed = total_e > 0 or (strict and total_w > 0)
    if failed:
        print('结果: 未通过')
    else:
        print('结果: 通过')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
