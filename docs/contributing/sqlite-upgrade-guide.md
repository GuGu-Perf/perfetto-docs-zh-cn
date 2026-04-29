# SQLite 升级指南

## 概述

Perfetto 依赖于 SQLite 内部：

- 通过 syntaqlite 库处理 SQLite 语法
- 内部 SQLite 常量和结构体

## 升级过程

### 先决条件

仅在 Chrome、Android 和 Google3 都支持目标 SQLite 版本时升级。

### 步骤

1. **更新版本引用：**
   - `tools/install-build-deps` - 更新 SQLite 版本/哈希
   - `bazel/deps.bzl` - 更新 SQLite 版本/哈希

2. **重新生成 PerfettoSQL 解析器：**

```bash
python3 tools/gen_syntaqlite_parser
```

3. **构建和测试：**

```bash
tools/ninja -C out/linux_clang_release trace_processor_shell perfetto_unittests
out/linux_clang_release/perfetto_unittests --gtest_filter="*Sql*"
tools/diff_test_trace_processor.py out/linux_clang_release/trace_processor_shell --quiet
```

## 常见问题

### SQLite 内部 API 更改

**错误：** `sqlite_utils.h` 或 `sqlite/bindings/*.h` 中的编译错误

**修复：** 为 SQLite API 更新绑定

## 关键文件

### 始终审查

- `tools/install-build-deps` - SQLite 版本/哈希
- `bazel/deps.bzl` - SQLite 版本/哈希
- `tools/gen_syntaqlite_parser` - 解析器重新生成脚本

### 生成文件（不要编辑）

- `src/trace_processor/perfetto_sql/syntaqlite/syntaqlite_perfetto.c`
- `src/trace_processor/perfetto_sql/syntaqlite/syntaqlite_perfetto.h`

### 语法源文件（可编辑）

- `src/trace_processor/perfetto_sql/syntaqlite/perfetto.y` - Perfetto 方言语法
- `src/trace_processor/perfetto_sql/syntaqlite/perfetto.synq` - AST 节点定义

## 回滚

1. 恢复 `tools/install-build-deps` 和 `bazel/deps.bzl` 中的版本更改
2. 重新运行 `python3 tools/gen_syntaqlite_parser`
3. 重新构建
