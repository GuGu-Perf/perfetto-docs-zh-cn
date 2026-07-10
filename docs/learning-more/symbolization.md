# 符号化与反混淆

本文档描述如何将采集的 trace 中的原始指令地址和混淆的 Java/Kotlin 名称转换为人类可读的函数名、源代码位置和类/方法名。

正确的方法取决于**你拥有哪种类型的 trace**，因此本页按这一问题组织。本文档中使用的两个定义：

- **符号化（Symbolization）**：使用被 profile 进程中加载的未剥离 ELF 二进制文件（或等效的 Breakpad 符号文件），将 native 指令地址映射回函数名、源文件和行号。
- **反混淆（Deobfuscation）**：使用构建时生成的 `mapping.txt`，将 R8/ProGuard 发出的混淆 Java/Kotlin 名称（例如 `fsd.a`）映射回原始标识符。

## 你需要哪种工作流？ {#which-workflow}

根据你的 trace 匹配以下类别之一并点击链接。选择错误的工作流是符号"不起作用"的最常见原因。关键经验法则：**用户空间**符号在主机上离线解析（`traceconv bundle`），而**内核**符号始终在设备上录制时解析（Perfetto 故意不存储绝对内核地址，以避免泄露
[KASLR](https://en.wikipedia.org/wiki/Address_space_layout_randomization)）。

| 你的 trace 包含&hellip; | 示例 | 你需要什么 |
| --- | --- | --- |
| **调用栈** | Native heap profiler、`traced_perf` / Linux perf CPU 采样、ART 堆转储 | [符号化与反混淆](#callstacks)。用户空间帧离线解析（`traceconv bundle`）；内核帧在设备上自动符号化。 |
| **内核 ftrace 事件** | `function_graph` 追踪、`sched_blocked_reason`、kprobes | [录制时 `symbolize_ksyms`](#ftrace)。这些地址**无法**事后符号化。 |
| **用户空间事件名称** | atrace slice 名称、ART 方法追踪 | 目前[不支持](#userspace-event-names)离线反混淆；在插桩时发出可读名称。 |

## 调用栈：符号化和反混淆 {#callstacks}

这适用于任何采集调用栈的 DataSource：native heap profiler、基于 perf 的 CPU profiler（`traced_perf` 和导入的 Linux `perf` 数据）以及 ART 分配 profiler。

这些数据源记录原始的**用户空间**指令地址（在 Android 上还包括混淆的 Java/Kotlin 帧），你可以在**录制后**使用以下步骤在主机上解析。只要你仍然有匹配的二进制文件和 mapping 文件，你**不需要**重新采集即可获得用户空间符号或反混淆名称。

调用栈还可能包含**内核**帧，它们的处理方式不同；请参阅本节末尾的[调用栈中的内核帧](#callstack-kernel-frames)。

### {#option-1-traceconv-bundle} 方式 1：`traceconv bundle`（推荐）

`traceconv bundle` 是一个一键命令，它接受一个 trace 并生成一个**丰富化的 trace**：原始 trace 加上分析它所需的所有符号和反混淆数据，打包在单个文件中。

```bash
traceconv bundle input.perfetto-trace enriched-trace
```

丰富化的 trace 可以像任何其他 trace 一样在 [Perfetto UI](https://ui.perfetto.dev) 或 `trace_processor_shell` 中打开，符号和反混淆名称已自动应用。

NOTE: 作为实现细节，丰富化的 trace 目前被打包为 TAR 归档文件，包含原始 trace、native 符号 Packet 和 Java/Kotlin 反混淆 Packet。UI 和 `trace_processor_shell` 透明地读取此格式，因此你通常不需要自行解包。

**要求：**

- `$PATH` 上需要有 `llvm-symbolizer` 以生成函数名和行号的 native 符号化（在 Debian/Ubuntu 上使用 `sudo apt install llvm`）。
- 输入和输出必须是文件路径；不支持 stdin/stdout。
- 磁盘上有匹配的未剥离二进制文件 / Breakpad 符号（Build ID 必须与设备上采集的匹配）。
- 对于 Java/Kotlin：需要设备上运行的构建所产生的 `mapping.txt`。

### 自动路径发现

相比[方式 2](#option-2-legacy-traceconv-symbolize-deobfuscate) 的主要优势是，`bundle` 会在所有常见位置查找符号和 mapping 文件，无需配置。它搜索：

- 在 `lunch` 过的 AOSP 检出中运行时的 AOSP 构建输出（`$ANDROID_PRODUCT_OUT/symbols`）。
- 标准系统调试目录（`$HOME/.debug`、`/usr/lib/debug`）。
- trace 的 `stack_profile_mapping` 中记录的绝对库路径（当在你用于分析的同一台机器上进行 profile 时很有用）。
- ProGuard/R8 mapping 文件的标准 Android Gradle 项目布局（`./app/build/outputs/mapping/<variant>/mapping.txt`）。

### 使用标志补充发现

当自动发现不够时：

```bash
traceconv bundle \
  --symbol-paths /path/to/symbols1,/path/to/symbols2 \
  --proguard-map com.example.app=/path/to/mapping.txt \
  --verbose \
  input.perfetto-trace enriched-trace
```

`bundle` 标志的属性：

- `--symbol-paths PATH1,PATH2,...`：搜索 native 符号的额外目录（除了自动发现的路径）。
- `--no-auto-symbol-paths`：禁用 native 符号路径的自动发现。仅搜索通过 `--symbol-paths` 给出的路径。
- `--proguard-map [pkg=]PATH`：用于 Java/Kotlin 反混淆的额外 ProGuard/R8 `mapping.txt`。对多个 mapping 重复此标志。可选的 `pkg=` 前缀将 mapping 限定到特定的 Java 包。
- `--no-auto-proguard-maps`：禁用 ProGuard/R8 mapping 文件的自动发现（例如标准 Android Gradle 布局）。仅应用通过 `--proguard-map` 给出的 mapping。
- `--verbose`：打印尝试的每个路径和查找的每个库——在调试"could not find"错误时很有用。

## {#option-2-legacy-traceconv-symbolize-deobfuscate} 方式 2：传统 `traceconv symbolize` / `deobfuscate`

NOTE: 此流程是为了与已有的脚本和 CI 流水线向后兼容而保留的。对于新使用场景，请始终优先使用[方式 1](#option-1-traceconv-bundle)——它更简单，具有自动发现功能，并且适用于非 Perfetto trace 格式。

较旧的 `traceconv symbolize` 和 `traceconv deobfuscate` 子命令生成独立的符号和反混淆文件，完全由环境变量驱动，然后必须手动拼接到 trace 上。

### Native 符号化

所有工具（`traceconv`、`trace_processor_shell`、`heap_profile` 脚本）都遵循 `PERFETTO_BINARY_PATH` 环境变量：

```bash
PERFETTO_BINARY_PATH=somedir tools/heap_profile android --name ${NAME}
```

为已采集的 trace 生成独立的符号文件：

```bash
PERFETTO_BINARY_PATH=somedir traceconv symbolize raw-trace > symbols
```

或者，设置 `PERFETTO_SYMBOLIZER_MODE=index`，符号化器将按 Build ID 递归索引目录中的 ELF 文件，因此文件名不需要匹配。

### Java/Kotlin 反混淆

通过 `PERFETTO_PROGUARD_MAP` 提供 ProGuard/R8 mapping，使用格式 `packagename=map_filename[:packagename=map_filename...]`：

```bash
PERFETTO_PROGUARD_MAP=com.example.pkg1=foo.txt:com.example.pkg2=bar.txt \
  ./tools/heap_profile android -n com.example.app
```

为现有 trace 生成独立的反混淆文件：

```bash
PERFETTO_PROGUARD_MAP=com.example.pkg=proguard_map.txt \
  traceconv deobfuscate ${TRACE} > deobfuscation_map
```

### 将输出附加到 trace

上面的 `symbols` 和 `deobfuscation_map` 都是序列化的 `TracePacket` proto，因此对于 **Perfetto protobuf trace**，你可以简单地将它们拼接：

```bash
cat ${TRACE} symbols > symbolized-trace
cat ${TRACE} deobfuscation_map > deobfuscated-trace
# 或者两者都加：
cat ${TRACE} symbols deobfuscation_map > enriched-trace
```

`tools/heap_profile` 脚本在设置了 `PERFETTO_BINARY_PATH` 时，会在其输出目录中自动执行此操作。

**限制：**

- 拼接技巧**仅适用于 Perfetto protobuf trace**。其他 trace 格式（Chrome JSON、systrace、Firefox profile 等）不能以这种方式追加 `TracePacket` 字节。对于这些格式，请使用[方式 1](#option-1-traceconv-bundle)并通过 `trace_processor_shell` 加载符号。
- 你必须手动管理 `PERFETTO_BINARY_PATH` / `PERFETTO_PROGUARD_MAP`；方式 1 中的自动发现不适用。

## 符号查找顺序

对于 trace 中的每个 native mapping，符号化器查找具有匹配 Build ID 的文件。对于每个搜索路径 `P`，它按以下顺序尝试：

1. 库文件相对于 `P` 的绝对路径。
2. 同上，但去掉文件名中的 `base.apk!`。
3. 库文件相对于 `P` 的基本名称。
4. 基本名称，去掉 `base.apk!`。
5. `P/.build-id/<前 2 个十六进制数字>/<其余部分>.debug`（标准的 [Fedora Build ID 布局](https://fedoraproject.org/wiki/RolandMcGrath/BuildID#Find_files_by_build_ID)）。

例如，带有 Build ID `abcd1234...` 的 `/system/lib/base.apk!foo.so` 在符号路径 `P` 下查找：

1. `P/system/lib/base.apk!foo.so`
2. `P/system/lib/foo.so`
3. `P/base.apk!foo.so`
4. `P/foo.so`
5. `P/.build-id/ab/cd1234...debug`

第一个具有匹配 Build ID 的文件胜出。如果磁盘上的 Build ID 与 trace 中记录的不同，则跳过该文件。

## 从 C++ 库使用符号化/反混淆

目前**没有稳定的公共 C++ API** 用于在进程内执行符号化或反混淆。底层实现存在（`src/traceconv/trace_to_bundle.h` 中的 `TraceToBundle`，由 `src/trace_processor/util/trace_enrichment/trace_enrichment.h` 中的 `EnrichTrace` 支持），但它位于 `src/` 而非 `include/` 下，不属于公共 API 接口。

如果你需要此功能，请在 [GitHub issue #5534](https://github.com/google/perfetto/issues/5534) 上 +1，以便我们评估需求并确定优先级。

### 故障排除

#### 找不到库

在对 Profile 进行符号化时，你可能会看到如下消息：

```text
Could not find /data/app/invalid.app-wFgo3GRaod02wSvPZQ==/lib/arm64/somelib.so
(Build ID: 44b7138abd5957b8d0a56ce86216d478).
```

检查 `somelib.so` 是否存在于某个搜索路径下（`--symbol-paths`、`PERFETTO_BINARY_PATH` 或自动发现的位置）。然后使用 `readelf -n /path/to/somelib.so` 比较磁盘上的 Build ID 与消息中报告的 Build ID。如果它们不匹配，磁盘上的副本是不同于设备上的构建，无法使用。

使用 `--verbose` 重新运行 `traceconv bundle` 会打印尝试的每个路径，这通常可以清楚地表明文件是完全缺失还是找到了但 Build ID 不匹配。

### 调用栈中的内核帧 {#callstack-kernel-frames}

采样的调用栈可能包含**内核**帧（例如使用 `callstack_sampling { kernel_frames: true }` 进行 perf 采样）。与上述用户空间帧不同，这些帧在**设备上录制时**自动从 `/proc/kallsyms` 符号化 &mdash; 本节中的离线工具不会处理它们。

为了使内核帧具有名称，录制必须能够读取 `/proc/kallsyms`，这需要以 root 身份运行或降低 `kptr_restrict`：

```bash
echo 0 | sudo tee /proc/sys/kernel/kptr_restrict
```

如果内核帧显示为十六进制地址，这是录制时的权限问题，你必须重新录制。这与下面的[内核 ftrace 事件](#ftrace)具有相同的 KASLR 限制，但请注意两者使用不同的机制：调用栈内核帧**不**使用 `symbolize_ksyms` ftrace 选项 &mdash; 该标志仅影响 ftrace 事件。

## 内核 ftrace 事件：`symbolize_ksyms` {#ftrace}

如果你正在进行**系统 Tracing** 并在预期出现内核函数名的地方看到原始十六进制地址 &mdash; 例如在
[函数图 Tracing](/docs/data-sources/funcgraph.md) 中，在不可中断休眠
[调度阻塞](/docs/case-studies/scheduling-blockages.md) 的 `blocked_function` 字段中，或在 kprobe 事件中 &mdash; 修复方法**不是**离线符号化。

这些内核地址通过在 ftrace 配置中启用 `symbolize_ksyms` 在**录制时**解析：

```protobuf
data_sources: {
    config {
        name: "linux.ftrace"
        ftrace_config {
            symbolize_ksyms: true
            # ... 你的 ftrace_events / function_graph 配置 ...
        }
    }
}
```

这会读取设备上的 `/proc/kallsyms`，并将（偏移后的）符号表嵌入 trace 中。它要求 `traced_probes` 以 root 身份运行或手动降低 `kptr_restrict`。

WARNING: `traceconv bundle` 和上述离线符号器**无法**恢复内核符号。Perfetto 故意不在 trace 中存储绝对内核地址，因为这样做会破坏
[KASLR](https://en.wikipedia.org/wiki/Address_space_layout_randomization) 并泄露内核内存布局。符号名称在设备上进行了偏移处理，因此可以在不泄露绝对地址的情况下工作。如果你忘记设置 `symbolize_ksyms`，必须重新录制。

此标志仅适用于 ftrace **事件**。在采样调用栈中捕获的内核帧另有处理方式；参见[调用栈中的内核帧](#callstack-kernel-frames)。

## 用户空间事件名称：atrace 和 ART 方法追踪 {#userspace-event-names}

某些数据源记录的是人类可读的**名称字符串**而非地址或栈帧。当这些字符串被混淆时（例如 R8 混淆的类名），**没有离线机制可以反混淆它们** &mdash; 名称必须在插桩时以可读形式发出。这与[调用栈部分](#callstacks)中的 Java/Kotlin **栈帧**反混淆不同，后者仅适用于堆转储和采样调用栈。

目前影响两种情况：

- **atrace / 用户空间 slice 名称**：[atrace](/docs/data-sources/atrace.md) slice 名称（以及出现在 `TRACE_EVENT` 字面值中的其他字符串）会逐字记录。没有事后映射步骤。
- **ART 方法追踪**：ART 方法追踪捕获的方法名称不会经过 ProGuard/R8 反混淆路径，因此混淆的构建将显示混淆的方法名称。

基于 `mapping.txt` 的反混淆路径原则上可行但目前尚未实现。相关支持正在讨论中；参见
[GitHub issue #6391](https://github.com/google/perfetto/issues/6391) 了解背景并表达兴趣。
