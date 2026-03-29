# SQLite 升级指南

## 概述

Perfetto 依赖于 SQLite 内部：
- 为 PerfettoSQL 修改的 SQLite 标记器(`tokenize.c`)
- SQLite 语法文件（`parse.y`）处理
- 内部 SQLite 常量和结构

## 升级过程

### 先决条件
仅在 Chrome、Android 和 Google3 都支持目标 SQLite 版本时升级。

### 步骤

1. **更新版本引用：**
  - `tools/install-build-deps` - 更新 SQLite 版本/哈希
  - `bazel/deps.bzl` - 更新 SQLite 版本/哈希

2. **运行解析器更新：**
 ```bash
 python3 tools/update_sql_parsers.py
 ```

3. **构建和测试：**
 ```bash
 tools/ninja -C out/linux_clang_release trace_processor_shell perfetto_unittests
 out/linux_clang_release/perfetto_unittests --gtest_filter="*Sql*"
 tools/diff_test_trace_processor.py out/linux_clang_release/trace_processor_shell --quiet
 ```

## 常见问题

### SQLite 特殊标记已更改
**错误：** `SQLite special tokens have changed! Expected: %token SPACE COMMENT ILLEGAL.`

**修复：** 更新 `tools/update_sql_parsers.py` 中的 `EXPECTED_SPECIAL_TOKENS`

### 缺少标记定义
**错误：** `use of undeclared identifier 'TK_COMMENT'` 或 `'SQLITE_DIGIT_SEPARATOR'`

**修复：** 将缺少的常量添加到 `tokenize_internal_helper.h`

### SQLite 内部 API 更改
**错误：** `sqlite_utils.h` 或 `sqlite/bindings/*.h` 中的编译错误

**修复：** 为 SQLite API 更新绑定

## 关键文件

### 始终审查
- `tools/install-build-deps` - SQLite 版本/哈希
- `bazel/deps.bzl` - SQLite 版本/哈希
- `tools/update_sql_parsers.py` - 解析器更新脚本
- `tokenize_internal_helper.h` - 标记器集成

### 生成(不要编辑)
- `perfettosql_grammar.*`
- `perfettosql_keywordhash.h`
- `tokenize_internal.c`

## 回滚
1. 恢复 `tools/install-build-deps` 和 `bazel/deps.bzl` 中的版本更改
2. 重新运行 `python3 tools/update_sql_parsers.py`
3. 重新构建
