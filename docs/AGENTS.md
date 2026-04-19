# AI Agent 的 Perfetto 项目开发指南

本文档提供了在 Perfetto 代码库中开发的基本说明和最佳实践。遵循这些指南以确保一致性和质量。

## 概述

perfetto 仓库包含几个项目。这些是主要项目：

1. Tracing 服务：一组 C++ 项目，部署在被 trace 的目标设备上。它们位于 src/{traced, traced_probes, tracing}。目标名称：perfetto、traced、traced_probes、traced_perf、heapprofd。

2. Tracing SDK：位于 src/tracing 中。它们由想要使用 Perfetto 发出 trace 事件的应用程序使用。此 SDK 有两种版本。
  - (较旧的)C++ SDK：通过 include/perfetto/tracing/ 可访问。
  - (较新的)C SDK：通过 include/perfetto/public 可访问。

3. TraceProcessor：位于 src/trace_processor/ 中的 C++ 项目。此代码通常不会部署在设备上，而是由离线工具使用。它内部基于 sqlite，并通过 vtable API 扩展其查询引擎。UI 在 Wasm(Web Assembly) 中使用此构建。

4. Perfetto UI：这是一个单页 Web 应用程序，仅客户端（无服务器组件），使用 TypeScript 编写，为 ui.perfetto.dev 提供动力。它位于 ui/ 中。它通过 Wasm 嵌入 TraceProcessor。如果你计划进行 UI 更改，请查看 /docs/AGENTS-ui.md 并停止查看此文件的其余部分。

5. 其他一些不常用的工具和实用程序，位于 tools/ 和 src/tools 中。

## 核心软件工程原则

在编写和修改代码时遵循这些原则。

- 避免代码重复：在编写新函数之前，在代码库中搜索提供类似功能的现有函数。
- 重用和重构：如果存在合适的函数，请重用它。如果接近但不完全匹配，请考虑重构现有函数以适应新用例，而不是创建副本。
- 如果不确定，请咨询：如果你考虑复制函数或重要的代码块，请先咨询用户。

## C++ 项目概述

GN 支持不同的配置，每个 out/* 文件夹一个。你可以通过查看 out/xxx/args.gn 来检查它们。通常在开发时构建/运行测试，我们的目标是本地机器（linux 或 mac），我们不使用 android 目标。

使用以下命令为不同配置构建项目。
所有命令都应从仓库根目录运行。

代码构建的输出文件夹位于 out/xxx 中。不同的人使用不同的输出文件夹。

**重要：在运行任何构建或测试命令之前，首先确定输出目录：**

1. 通过运行 `echo $OUT` 检查是否设置了 `$OUT`
2. 如果设置了 `$OUT`，则使用该值
3. 如果 `$OUT` 为空/未设置，运行 `ls -t1 out | head -n1` 查找最近的输出目录

然后在所有后续命令中使用该具体路径（例如，`out/linux_clang_release`）。**切勿将 `$(ls -t1 out | head -n1)` 内联到命令中** - 始终替换实际目录名称。

### 构建 C++ 代码

我们的主要构建系统是"gn"(GenerateNinja) + "ninja"。
这些工具已检入，可以通过我们仓库中的包装脚本 tools/gn 和 tools/ninja 访问。

- 如果你修改 .gn 或 .gni 文件，重新运行 `tools/gn gen --check out/linux_clang_release`
- 之后，你可以通过运行 `tools/ninja -C out/linux_clang_release TARGET_NAME` 来构建代码
- TARGET_NAME 是：
  - perfetto_unittests：用于 src/**/*_unittest.cc 中的任何文件
  - perfetto_integrationtests：用于 src/**/*_integrationtest.cc 中的任何文件(以及 test/ 下的大部分代码)
  - perfetto_benchmarks：用于 src/**/*_benchmark.cc 中的任何文件(以及 test/ 下的大部分代码)
  - 其他目标名称通常是：traced、traced_probes、perfetto、trace_processor_shell。你可以通过跟随根 /BUILD.gn 文件来发现它们

当添加/删除源文件时，保持 BUILD.gn 文件更新。
通常每个目录中都有一个 BUILD.gn 文件。如果没有，请在更近的父目录中查找先例。

永远不要手动更新 Android.bp 文件或 bazel BUILD 文件。
这些文件稍后在上传拉取请求时通过 `tools/gen_all out/linux_clang_release` 自动生成，但人类会处理。

要构建一个或多个目标：

```sh
tools/ninja -C out/linux_clang_release -k 10000 trace_processor_shell perfetto_unittests
```

所有 C++ 项目共享相同的"base"目标（include/perfetto/base、include/ext/perfetto/base），并且可以共享一些其他目标（参见 GN）。

### C++ 代码风格

我们主要遵循 Google C++ 风格指南，你可以在此处查阅
https://google.github.io/styleguide/cppguide.html

亮点：

- 使用 C++17。
- 不要使用异常，不要费心 try/catch。
- 尽量减少模板使用。
- 在头文件中首选前向声明，并在 .cc 文件中 #include 所需的依赖项。
- 我们快速失败。如果某些事情不应该发生，请添加 PERFETTO_DCHECK()（仅调试）或 PERFETTO_CHECK()(生产)。
- 记住永远不要将带有副作用的代码放在 PERFETTO_DCHECK 内部，因为它们在发布构建中会变成无操作。
- 如果函数参数是输出或输入输出，请通过指针传递，而不是通过引用。
- 删除复制和移动构造函数，除非真的需要它们。
- 如果你需要复制/移动构造函数，请使用 include/perfetto/ext/base/circular_queue.h 中看到的相同模式
- 使用 PERFETTO_DLOG(仅调试)、PERFETTO_LOG/ILOG/ELOG() 进行记录。
- 变量名称应与作用域和距离成比例。在小循环中使用的变量可以称为 i，j；作用域为函数的变量应该更短；在不同文件中使用的变量/函数应该更长（在合理范围内），并且在代码搜索时更不容易发生冲突。
- 避免使用 STL、posix/Unix 常用头文件以及我们已经在 buildtools/ 中拉取的其他库以外的库。如果你认为你需要新库，请询问用户。
- 通常，与文件的风格保持一致。

在可能的情况下，尝试使用 include/perfetto/base/ 和 include/perfetto/ext/base/ 中可用的数据结构和构造。通常在代码库中查找先例。如果有疑问，请询问。

你应该查看的常用包括，在 include/ 下：

- perfetto/base/task_runner.h
- perfetto/base/compiler.h
- perfetto/base/time.h
- perfetto/ext/base/status_or.h
- perfetto/ext/base/scoped_file.h
- perfetto/ext/base/file_utils.h
- perfetto/ext/base/flat_hash_map.h
- perfetto/ext/base/utils.h
- perfetto/ext/base/string_view.h
- perfetto/ext/base/string_utils.h
- perfetto/base/status.h
- perfetto/base/logging.h

创建新文件时，这是你放置头文件的位置：

- .cc 文件始终放在 src/ 下，某些 test/ 代码除外。
- 如果可能，将 .h 头文件保持私有，并将它们与 .cc 文件放在一起。
- 如果需要，你可以将头文件放在 include/perfetto/ext 中，因为那是非公共 API 表面。
- 在极少数情况下，如果用户这样说，你可以将新头文件放在 include/perfetto/public 中，但这仅适用于 C-SDK 情况。
- 注意"include/"在 include 路径中，因此你永远不需要输入 #include "include/perfetto/foo"，而只需要 #include "perfetto/foo"。

### 在 C++ 中支持不同操作系统

我们通常在我们的代码库中支持所有主要平台（Linux、Android、MacOS/iOS、Windows），除了 src/traced 仅支持 Linux/Android(MacOS 上很少有部分)。

如果你需要为不同平台拆分代码，你必须使用 perfetto/base/build_config.h，特别是其中定义的宏，如 `#if PERFETTO_BUILDFLAG(PERFETTO_OS_ANDROID)` 等。

注意你在那里看到的每个 PERFETTO_BUILDFLAG_DEFINE_XXX 都必须通过 PERFETTO_BUILDFLAG(XXX) 包装器使用。
例如，当你看到 PERFETTO_BUILDFLAG_DEFINE_PERFETTO_OS_QNX 时，使用 PERFETTO_BUILDFLAG(PERFETTO_OS_QNX)。

### 运行 C++ 测试

Perfetto 使用 Google Test 框架。你将看到 c++ 源代码，如

```cpp
TEST(ProtozeroToJsonTest, Foo) {
...
}
```

ProtozeroToJsonTest 是测试套件名称，Foo 是测试名称。

你可以通过执行以下操作来运行测试套件中的所有测试：

```sh
out/linux_clang_release/perfetto_unittests --gtest_brief=1 --gtest_filter="ProtozeroToJsonTest.*"
```

或者，如果你修改特定测试，你可以通过执行以下操作仅运行该测试

```sh
out/linux_clang_release/perfetto_unittests --gtest_brief=1 --gtest_filter="ProtozeroToJsonTest.Foo"
```

perfetto_integrationtests 也是如此。

对于 perfetto_benchmarks，你需要改为运行

```sh
out/linux_clang_release/perfetto_benchmarks --benchmark_filter='.*BM_RtMutex_NoContention.*'
```

注意，与 Google Test 不同，其中过滤器是 glob，在 Google Benchmarks 中过滤器是正则表达式。

### Trace Processor 差异测试

通过运行以下命令来执行 Trace Processor 差异测试(或简称差异测试):

```sh
tools/diff_test_trace_processor.py out/linux_clang_release/trace_processor_shell --keep-input --quiet --name-filter="<test names 的 regex>"
```

**注意：**这些测试也可以通过将路径从 `out/linux_clang_release/` 更改为 `out/linux_asan/` 或 `out/linux_msan/` 来使用 ASan 或 MSan 构建运行。

**注意：**`--name-filter` 参数是可选的。

**注意:**使用 `--name-filter` 标志时，不要在过滤器中包含 `test_`。测试运行程序会自动删除此前缀。
例如，要运行 `test_my_cool_test`，请使用过滤器 `MyTestSuite.my_cool_test`。

### 测试指南

- **首选测试套件而非单个测试。** 使用 `--gtest_filter` 标志时，指定整个测试套件（例如，`"MyTestSuite.*"`）而不是单个测试用例（例如，`"MyTestSuite.MySpecificTest"`）。这确保更广泛的测试覆盖。
- **不要测试不稳定的 ID。** 编写差异测试时，不要在输出中包含包含不稳定 ID（例如 `upid`、`utid`、`id` 等）的列。这些 ID 可能会在同一测试的不同运行之间更改，这将导致测试失败。
 
- **为差异测试删除 `test_` 前缀。** 对差异测试使用 `--name-filter` 标志时，不要在过滤器中包含 `test_`。测试运行程序会自动删除此前缀。例如，要运行 `test_my_cool_test`，请使用过滤器 `MyTestSuite.my_cool_test`。

## 获取差异

当被要求"获取差异"或"读取当前差异"时，运行以下命令：

```sh
git diff $(git config branch.$(git rev-parse --abbrev-ref HEAD).parent)
```

## 修复 GN 依赖项

当被要求修复 GN 依赖项时，运行以下命令并修复报告的任何错误：

```sh
tools/gn check out/linux_clang_release
```

**注意:**修复包含错误时，除非用户明确指示，否则不要将依赖项添加到 `public_deps`。而是向需要它的目标添加直接依赖项。

## 其他配置

### ASan (AddressSanitizer) 构建

要使用 ASan 构建以进行内存错误检测：

```sh
tools/ninja -C out/linux_asan -k 10000 trace_processor_shell perfetto_unittests
```

### MSan (MemorySanitizer) 构建

要使用 MSan 构建以进行未初始化读取检测：

```sh
tools/ninja -C out/linux_msan -k 10000 trace_processor_shell perfetto_unittests
```

### ASan (AddressSanitizer) 测试

**注意：**确保正确设置了 `ASAN_SYMBOLIZER_PATH`。

```sh
ASAN_SYMBOLIZER_PATH="$(pwd)/buildtools/linux64/clang/bin/llvm-symbolizer" \
out/linux_asan/perfetto_unittests --gtest_brief=1 --gtest_filter="<TestSuiteName.*>"
```

### MSan (MemorySanitizer) 测试

**注意:**确保正确设置了 `MSAN_SYMBOLIZER_PATH`。

```sh
MSAN_SYMBOLIZER_PATH="$(pwd)/buildtools/linux64/clang/bin/llvm-symbolizer" \
out/linux_msan/perfetto_unittests --gtest_brief=1 --gtest_filter="<TestSuiteName.*>"
```

## 创建拉取请求

创建拉取请求时，请遵循以下步骤：

1. **创建新分支：**
 使用命令 `git new-branch dev/$USER/<name-of-branch>` 为你的拉取请求创建新分支。

2. **创建堆叠/依赖拉取请求：**
 要创建依赖于另一个的拉取请求，请使用命令 `git new-branch --parent <name-of-parent-branch> dev/alitm/<name-of-branch>`。

**注意:** `git new-branch` 命令仅创建并切换到新分支。应该使用正常的 `git add` 和 `git commit` 工作流将更改添加到分支。

## 提交消息

编写提交消息时，请遵循以下指南：

- 为提交添加前缀：将 Trace Processor 代码的更改前缀为 `tp:`,UI 代码为 `ui:`，常规 Perfetto 更改为 `perfetto:`。
- 保持简洁：简短的一行摘要，后跟一个 \n，然后是一个描述更改的段落，是最佳提交消息。将提交消息换行在 72 列。
