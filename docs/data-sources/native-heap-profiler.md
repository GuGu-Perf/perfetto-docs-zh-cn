# 内存：基于调用堆栈的分配 Profiling

NOTE: **heapprofd 需要 Android 10 或更高版本**

Heapprofd 是一个跟踪 Android 进程在给定时间范围内的堆分配和释放的工具。生成的 profile 可用于将内存使用归因于特定的调用堆栈，支持混合的 native 和 java 代码。该工具可供 Android 平台和应用程序开发人员用于调查内存问题。

默认情况下，该工具记录使用 malloc/free（或 new/delete）进行的 native 分配和释放。它可以配置为记录 java 堆内存分配：请参见下面的 [Java 堆采样](#java-heap-sampling)。

在调试 Android 构建上，你可以 profile 所有应用程序和大多数系统服务。在"user"构建上，你只能对具有 debuggable 或 profileable 清单标志的应用程序使用它。

## 快速入门

有关 heapprofd 的入门，请参见 [内存指南](/docs/case-studies/memory.md#heapprofd)。

## UI

Heapprofd 的转储在 UI 中显示为火焰图，单击菱形后显示。每个菱形对应于在该时间点收集的分配和调用堆栈的快照。

![UI track 中的 heapprofd 快照](/docs/images/profile-diamond.png)

![heapprofd 火焰图](/docs/images/native-heap-prof.png)

## SQL

有关调用堆栈的信息写入以下表：

* [`stack_profile_mapping`](/docs/analysis/sql-tables.autogen#stack_profile_mapping)
* [`stack_profile_frame`](/docs/analysis/sql-tables.autogen#stack_profile_frame)
* [`stack_profile_callsite`](/docs/analysis/sql-tables.autogen#stack_profile_callsite)

分配本身写入
[`heap_profile_allocation`](/docs/analysis/sql-tables.autogen#heap_profile_allocation)。

离线符号化数据存储在
[`stack_profile_symbol`](/docs/analysis/sql-tables.autogen#stack_profile_symbol) 中。

有关示例 SQL 查询，请参见 [示例查询](#heapprofd-example-queries)。

## 记录

Heapprofd 可以通过三种方式配置和启动。

#### 手动配置

这需要手动设置 trace 配置的 [HeapprofdConfig](/docs/reference/trace-config-proto.autogen#HeapprofdConfig) 部分。这样做的唯一好处是，通过这种方式，可以在任何其他 trace 数据源的同时启用 heap profiling。

#### 使用 tools/heap_profile 脚本（推荐）

你可以使用 `tools/heap_profile` 脚本。如果你遇到问题，请确保你使用的是 [最新版本](
https://raw.githubusercontent.com/google/perfetto/main/tools/heap_profile)。

该脚本有两个子命令：

* `heap_profile android` - 通过 `adb` 对连接的 Android 设备上的进程进行 profile（如果未指定子命令则为默认，保留历史调用方式）。
* `heap_profile host` - 对本地 Linux 进程进行 profile；参见下面的 [(非 Android) Linux 支持](#non-android-linux-support)。

对于 Android，你可以按名称（`-n com.example.myapp`）或按 PID（`-p 1234`）定位进程。在第一种情况下，heap profiling 将在已经运行并匹配包名的进程以及在 profiling session 启动后启动的新进程上启动。有关完整的参数列表，请参见 [heap_profile 命令行参考页面](/docs/reference/heap_profile-cli)。

你可以使用 [Perfetto UI](https://ui.perfetto.dev) 可视化堆转储。上传输出目录中的 `raw-trace` 文件。你将在 Timeline 上看到所有堆转储作为菱形，单击其中任何一个即可获得火焰图。

#### 使用 Perfetto UI 的记录页面

你还可以使用 [Perfetto UI](https://ui.perfetto.dev/#!/record/memory) 采集 heapprofd profile。在 trace 配置中勾选"Heap profiling"，输入你要定位的进程，单击"Add Device"配对你的手机，并直接从浏览器采集 profile。这在 Windows 上也是可能的。

## 查看数据

![Profile Diamond](/docs/images/profile-diamond.png)

生成的 profile proto 包含数据的四个视图，对于每个菱形。

* **未释放的 malloc 大小**：在此调用堆栈上分配但未释放的字节数，从记录开始到菱形的时间戳。
* **总 malloc 大小**：在此调用堆栈上分配（包括在转储时刻释放的字节）的字节数，从记录开始到菱形的时间戳。
* **未释放的 malloc 计数**：在此调用堆栈上完成的没有匹配释放的分配数，从记录开始到菱形的时间戳。
* **总 malloc 计数**：在此调用堆栈上完成的分配（包括具有匹配释放的分配）数，从记录开始到菱形的时间戳。

TIP: profile 应用程序时，你可能希望将 `libart.so` 设置为"隐藏正则表达式"。

TIP: 单击左上角的 Left Heavy 以获得良好的可视化。

## 持续转储

默认情况下，heap profiler 从记录开始捕获所有分配，并存储单个快照，在 UI 中显示为单个菱形，汇总所有分配/释放。

可以配置 heap profiler 定期（不仅仅是在 trace 结束时）存储快照（连续转储），例如每 5000ms:

* 通过在 UI 中将"Continuous dumps interval"设置为 5000。
* 通过在 [HeapprofdConfig](/docs/reference/trace-config-proto.autogen#HeapprofdConfig) 中添加
  ```
  continuous_dump_config {
    dump_interval_ms: 5000
  }
  ```
* 通过向 [`tools/heap_profile android`](/docs/reference/heap_profile-cli) 的调用添加 `-c 5000`（或 `tools/heap_profile host` 用于本地 Linux 进程）。

![连续转储火焰图](/docs/images/heap_prof_continuous.png)

生成的可视化显示多个菱形。单击每个菱形显示从 trace 开始到该点的分配/释放的摘要（即，摘要是累积的）。

## 采样间隔

Heapprofd 通过 Hook 对 malloc/free 和 C++ 的 operator new/delete 的调用来采样堆分配。给定 n 字节的采样间隔，平均每分配 n 字节采样一次分配。这允许减少对目标进程的性能影响。默认采样率为 4096 字节。

对此进行推理的最简单方法是将内存分配想象为一个单字节分配的流。从这个流中，每个字节都有 1/n 的概率被选择为样本，相应的调用堆栈获得完整的 n 字节。为了更准确，大于采样间隔的分配绕过采样逻辑并以其实际大小记录。有关详细信息，请参见 [heapprofd 采样](/docs/design-docs/heapprofd-sampling) 文档。

## 启动时 profiling

当指定目标进程名称（相对于 PID）时，从启动开始 profile 匹配该名称的新进程。生成的 profile 将包含在进程启动和 profiling session 结束之间完成的所有分配。

在 Android 上，Java 应用程序通常不是从头开始 exec()-ed 的，而是从 [zygote] fork()-ed 的，然后专门化为所需的应用程序。如果应用程序的名称与 profiling session 中指定的名称匹配，profiling 将作为 zygote 专业化的一部分启用。生成的 profile 包含在 zygote 专业化中的该点和 profiling session 结束之间完成的所有分配。在专业化过程早期完成的一些分配未被计算在内。

在 trace proto 级别，生成的 [ProfilePacket] 将在相应的 `ProcessHeapSamples` 消息中将 `from_startup` 字段设置为 true。这不会在转换的 pprof 兼容 proto 中公开。

[ProfilePacket]: /docs/reference/trace-packet-proto.autogen#ProfilePacket
[zygote]: https://developer.android.com/topic/performance/memory-overview#SharingRAM

## 运行时 profiling

启动 profiling session 时，将枚举所有匹配的进程（按名称或 PID）并发送信号以请求 profiling。在应用程序执行的下一个分配后的几百毫秒内，实际上不会启用 profiling。如果在请求 profiling 时应用程序处于空闲状态，然后进行突发分配，这些可能会被遗漏。

生成的 profile 将包含在启用 profiling 和 profiling session 结束之间完成的所有分配。

生成的 [ProfilePacket] 将在相应的 `ProcessHeapSamples` 消息中将 `from_startup` 设置为 false。这不会在转换的 pprof 兼容 proto 中公开。

## 并发 profiling session

如果多个会话命名相同的目标进程（按名称或 PID），只有第一个相关会话将 profile 该进程。其他会话将在转换为 pprof 兼容 proto 时报告该进程已被 profiled。

如果你看到此消息但不希望有任何其他会话，请运行：

```shell
adb shell killall perfetto
```

以停止可能正在运行的任何并发会话。

生成的 [ProfilePacket] 将在否则为空的相应 `ProcessHeapSamples` 消息中将 `rejected_concurrent` 设置为 true。这不会在转换的 pprof 兼容 proto 中公开。

## {#heapprofd-targets} 目标进程

根据运行 heapprofd 的 Android 构建，某些进程可能不符合 profiling 条件。

在 _user_ (即生产版本、不可 root) 构建上，只能 profile 设置了 profileable 或 debuggable 清单标志的 Java 应用程序。对不可 profileable/debuggable 进程的 profiling 请求将导致空 profile。

在 userdebug 构建上，可以 profile 除一小部分关键服务之外的所有进程(要查找不允许的目标集，请在 [heapprofd.te](
https://cs.android.com/android/platform/superproject/main/+/main:system/sepolicy/private/heapprofd.te?q=never_profile_heap) 中查找 `never_profile_heap`)。可以通过运行 `adb shell su root setenforce 0` 禁用 SELinux 或向 `heap_profile` 脚本传递 `--disable-selinux` 来取消此限制。

<center>

|                         | userdebug setenforce 0 | userdebug | user |
|-------------------------|:----------------------:|:---------:|:----:|
| critical native service |            Y           |     N     |  N   |
| native service          |            Y           |     Y     |  N   |
| app                     |            Y           |     Y     |  N   |
| profileable app         |            Y           |     Y     |  Y   |
| debuggable app          |            Y           |     Y     |  Y   |

</center>

要将应用程序标记为 profileable，请将 `<profileable android:shell="true"/>` 放入应用程序清单的 `<application>` 部分。

```xml
<manifest ...>
    <application>
        <profileable android:shell="true"/>
        ...
    </application>
</manifest>
```

## {#java-heap-sampling} Java Allocation Profiling (Churn Profiling)

NOTE: **Java 分配 profiling 在 Android 12 或更高版本上可用**

NOTE: **Java 分配 profiling 不得与 [Heap dumps](/docs/data-sources/java-heap-profiler.md) 混淆**

Heapprofd 可以配置为跟踪 Java 分配而不是 native 分配。
* 通过在 [HeapprofdConfig](/docs/reference/trace-config-proto.autogen#HeapprofdConfig) 中添加 `heaps: "com.android.art"`。
* 通过向 [`tools/heap_profile android`](/docs/reference/heap_profile-cli) 的调用添加 `--heaps com.android.art`。

与 java heap dumps（显示活动对象快照的保留图）不同，但与 native heap profiles 类似，java 堆样本显示整个 profile 随时间分配的调用堆栈。

Java 堆样本仅显示创建对象时的调用堆栈，而不显示删除或垃圾回收对象时的调用堆栈。

![javaheapsamples](/docs/images/java-heap-samples.png)

生成的 profile proto 包含数据的两个视图：

* **总分配大小**：在此调用堆栈上从 profiling 开始到此点分配的字节数。字节可能已被释放或未释放，工具不跟踪该内容。
* **总分配计数**：在此调用堆栈上从 profiling 开始到此点分配的对象数。对象可能已被释放或未释放，工具不跟踪该内容。

Java 堆样本对于理解内存流变很有用，显示代码哪些部分的大分配归因于的调用堆栈以及来自 ART 运行时的分配类型。

## DEDUPED 帧

如果 Java 方法的名称包括 `[DEDUPED]`，这意味着多个方法共享相同的代码。ART 仅在其元数据中存储单个方法的名称，在此处显示。这不一定是被调用的方法。

## 按需触发堆快照

堆快照以定期时间间隔记录到 trace 中（如果使用 `continuous_dump_config` 字段），或者在会话结束时记录。

你还可以通过运行 `adb shell killall -USR1 heapprofd` 来触发所有当前 profiling 进程的快照。这对于在实验室测试中记录目标在特定状态下的当前内存使用情况很有用。

此转储将除 profiling 结束时始终产生的转储之外显示。你可以创建多个这样的转储，它们将在输出目录中枚举。

## 符号化和反混淆

如果你的 profile 显示原始地址或混淆的 Java/Kotlin 名称，请对收集的 trace 运行 `traceconv bundle` 以生成丰富的归档。有关完整工作流程，请参阅[符号化和反混淆](/docs/learning-more/symbolization.md)，包括传统的 `PERFETTO_BINARY_PATH` / `PERFETTO_PROGUARD_MAP` 方法。

## 故障排除

### 缓冲区溢出

如果分配率太高，heapprofd 无法跟上来，由于缓冲区溢出，profiling session 将提前结束。如果缓冲区溢出是由分配的瞬时峰值引起的，增加共享内存缓冲区大小（向 `tools/heap_profile android` / `tools/heap_profile host` 传递 `--shmem-size`）可以解决问题。否则，可以通过传递 `--interval=16000` 或更高来增加采样间隔（以降低生成的 profile 中的准确性为代价）。

### profile 为空

通过查阅上面的 [目标进程](#heapprofd-targets) 检查你的目标进程是否符合 profiling 条件。

此外，请检查 [已知问题](#known-issues)。

### 不可信的调用堆栈

如果你看到一个从查看代码来看似乎不可能的调用堆栈，请确保没有涉及 [DEDUPED 帧](#deduped-frames)。

此外，如果你的代码使用 _相同代码折叠_(ICF) 链接，即向链接器传递 `-Wl,--icf=...`，大多数微不足道的函数，通常是构造函数和析构函数，可以别名化为完全不相关类的二进制等效运算符。

### 符号化问题

对于"找不到库"、Build ID 不匹配和"仅显示一帧"的问题，请参阅[符号化和反混淆](/docs/learning-more/symbolization.md#troubleshooting)中的故障排除部分。

## {#non-android-linux-support} (非 Android) Linux 支持

```bash
tools/heap_profile host -- ./my_binary --some-flag
```

该脚本：

1. 首次运行时将 `tracebox` 和 `libheapprofd_glibc_preload.so` (linux-amd64 / arm / arm64) 自动下载到 `~/.local/share/perfetto/prebuilts/` 中。
2. 通过 `tracebox --system-sockets` 启动捆绑的 `traced` 守护进程。
3. 使用 `LD_PRELOAD` 指向预加载库并设置 `PERFETTO_HEAPPROFD_BLOCKING_INIT=1` 启动目标二进制文件。默认情况下 heapprofd 懒惰初始化以避免阻塞主线程，这意味着启动分配可能会被遗漏；设置此变量后，第一次 `malloc` 会阻塞，直到 heapprofd 完全附加，因此每个分配都会被正确跟踪。
4. 等待目标退出（或你按 `Ctrl-C`），然后运行 `traceconv` 以生成 gzip 压缩的 pprof 文件和原始 trace。

如果省略 `-n` / `--name`，进程名称默认为你在 `--` 后传递的二进制文件的基本名称。

运行完成后，脚本打印输出目录：

```text
Wrote profiles to /tmp/heap_profile-XXXXXX (symlink /tmp/heap_profile-latest)
The raw-trace and heap_dump.* (pprof) files can be visualized with https://ui.perfetto.dev.
```

将 `raw-trace` 文件上传到 [Perfetto UI](https://ui.perfetto.dev)。

### 使用自定义构建的预加载库

如果你的平台尚无预构建版本，请从 Perfetto checkout 构建该库（[构建说明](/docs/contributing/build-instructions.md)）并通过 `--preload-library` 传递它：

```bash
tools/setup_all_configs.py
tools/ninja -C out/linux_clang_release heapprofd_glibc_preload

tools/heap_profile host \
  --preload-library out/linux_clang_release/libheapprofd_glibc_preload.so \
  -- ./my_binary --some-flag
```

## 已知问题

### {#known-issues-android13} Android 13

* 解除 java 帧可能无法正常工作，具体取决于使用的 ART 模块版本。在这种情况下，UI 在堆栈顶部报告单个"未知"帧。此问题在 Android 13 QPR1 中已修复。

### {#known-issues-android12} Android 12

* 解除 java 帧可能无法正常工作，具体取决于使用的 ART 模块版本。在这种情况下，UI 在堆栈顶部报告单个"未知"帧。

### {#known-issues-android11} Android 11

* 无法在 64 位设备上定位 32 位程序。
* 将 `sampling_interval_bytes` 设置为 0 会使目标进程崩溃。这是一个应该被拒绝的无效配置。
* 对于启动时 profiling，某些帧名称可能缺失。这将在 Android 12 中解决。
* 在每个 profiling 结束时，logcat 中显示 `Failed to send control socket byte.`。这是良性的。
* 对象计数在 `dump_at_max` profile 中可能不正确。
* 选择较低的共享内存缓冲区大小和 `block_client` 模式可能会锁定目标进程。

### {#known-issues-android10} Android 10
* 具有加载偏差的库中的函数名称可能不正确。使用[离线符号化](/docs/learning-more/symbolization.md) 解决此问题。
* 对于启动时 profiling，某些帧名称可能缺失。这将在 Android 12 中解决。
* 无法在 64 位设备上定位 32 位程序。
* 不支持 x86 / x86_64 平台。这包括 Android _Cuttlefish_ 模拟器。
* 在 ARM32 上，最底层的帧始终是 `ERROR 2`。这是无害的，调用堆栈仍然是完整的。
* 如果 heapprofd 独立运行（通过在 root shell 中运行 `heapprofd`，而不是通过 init），`/dev/socket/heapprofd` 被分配不正确的 SELinux 域。除非你禁用 SELinux 强制执行，否则你将无法 profile 任何进程。在 root shell 中运行 `restorecon /dev/socket/heapprofd` 以解决。
* 使用 `vfork(2)` 或带有 `CLONE_VM` 的 `clone(2)` 并在子进程中分配/释放内存将过早结束 profiling。`java.lang.Runtime.exec` 执行此操作，调用它将过早结束 profiling。请注意，这违反了 POSIX 标准。
* 将 `sampling_interval_bytes` 设置为 0 会使目标进程崩溃。这是一个应该被拒绝的无效配置。
* 在每个 profiling 结束时，logcat 中显示 `Failed to send control socket byte.`。这是良性的。
* 对象计数在 `dump_at_max` profile 中可能不正确。
* 选择较低的共享内存缓冲区大小和 `block_client` 模式可能会锁定目标进程。

## Heapprofd vs malloc_info() vs RSS

使用 heapprofd 并解释结果时，重要的是了解可以从操作系统获得的不同内存 metrics 的精确含义。

**heapprofd** 给你目标程序从默认 C/C++ 分配器请求的字节数。如果你从启动开始 profiling Java 应用程序，则应用程序初始化早期发生的分配将不会被 heapprofd 看见。不从 Zygote fork 的 Native 服务不受此影响。

**malloc\_info** 是一个为你提供有关分配器信息的 libc 函数。可以通过在 userdebug 构建上使用 `am dumpheap -m <PID> /data/local/tmp/heap.txt` 来触发它。通常，这将大于 heapprofd 看到的内存，具体取决于分配器，并非所有内存都被立即释放。特别是，jemalloc 在线程缓存中保留一些释放的内存。

**Heap RSS** 是分配器从操作系统请求的内存量。这比前两个数字大，因为内存只能以页面大小的块获得，并且碎片化导致其中一些内存被浪费。这可以通过运行 `adb shell dumpsys meminfo <PID>` 并查看"Private Dirty"列来获得。如果设备内核使用内存压缩（ZRAM，在 android 的最近版本上默认启用）并且进程的内存被交换到 ZRAM 上，RSS 也可能最终比其他两个小。

|                     | heapprofd         | malloc\_info | RSS |
|---------------------|:-----------------:|:------------:|:---:|
| from native startup |          x        |      x       |  x  |
| after zygote init   |          x        |      x       |  x  |
| before zygote init  |                   |      x       |  x  |
| thread caches       |                   |      x       |  x  |
| fragmentation       |                   |              |  x  |

如果你观察到高 RSS 或 malloc\_info metrics 但 heapprofd 不匹配，你可能会遇到分配器中的一些病理性碎片问题。

## 转换为 pprof

你可以使用 [traceconv](/docs/quickstart/traceconv.md) 将 trace 中的堆转储转换为 [pprof](https://github.com/google/pprof) 格式：

```bash
tools/traceconv profile /tmp/profile
```

这将在 `/tmp/` 中创建一个包含堆转储的目录。运行：

```bash
gzip /tmp/heap_profile-XXXXXX/*.pb
```

以获取处理 pprof profile proto 的工具期望的 gzip 压缩的 proto。

## {#heapprofd-example-queries} 示例 SQL 查询

我们可以通过在 Trace Processor 中使用 SQL 查询来获取分配的调用堆栈。对于每个帧，我们为分配的字节数获得一行，其中 `count` 和 `size` 为正，如果其中任何一个已被释放，则获得另一行具有负 `count` 和 `size` 的行。这些的总和为我们提供了"未释放的 malloc 大小"视图。

```sql
select a.callsite_id, a.ts, a.upid, f.name, f.rel_pc, m.build_id, m.name as mapping_name,
        sum(a.size) as space_size, sum(a.count) as space_count
      from heap_profile_allocation a join
           stack_profile_callsite c ON (a.callsite_id = c.id) join
           stack_profile_frame f ON (c.frame_id = f.id) join
           stack_profile_mapping m ON (f.mapping = m.id)
      group by 1, 2, 3, 4, 5, 6, 7 order by space_size desc;
```

| callsite_id | ts | upid | name | rel_pc | build_id | mapping_name | space_size | space_count |
|-------------|----|------|-------|-----------|------|--------|----------|------|
|6660|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |106496|4|
|192 |5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |26624 |1|
|1421|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |26624 |1|
|1537|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |26624 |1|
|8843|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |26424 |1|
|8618|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |24576 |4|
|3750|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |12288 |1|
|2820|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |8192  |2|
|3788|5|1| malloc |244716| 8126fd.. | /apex/com.android.runtime/lib64/bionic/libc.so |8192  |2|

我们可以看到所有函数都是"malloc"和"realloc"，这不是非常有信息。通常，我们对函数中分配的 _累积_ 字节数感兴趣（否则，我们总是只会看到 malloc / realloc）。在 SQL 中递归地跟踪调用站点的 parent_id（未在此表中显示）非常困难。但是，我们在标准库中有一个辅助表可以为你完成此操作。

```sql
INCLUDE PERFETTO MODULE android.memory.heap_profile.summary_tree;

SELECT
  -- 此调用堆栈的帧的函数名称。
  name,
  -- 包含帧的映射的名称。这
  -- 可以是 native 二进制文件、库、JAR 或 APK。
  mapping_name AS map_name,
  -- 使用此函数分配且 *未释放* 的内存量
  -- 出现在调用堆栈的任何位置。
  cumulative_size
FROM android_heap_profile_summary_tree;
order by abs(cumulative_size) desc;
```

| name | map_name | cumulative_size |
|------|----------|----------------|
|__start_thread|/apex/com.android.runtime/lib64/bionic/libc.so|392608|
|_ZL15__pthread_startPv|/apex/com.android.runtime/lib64/bionic/libc.so|392608|
|_ZN13thread_data_t10trampolineEPKS|/system/lib64/libutils.so|199496|
|_ZN7android14AndroidRuntime15javaThreadShellEPv|/system/lib64/libandroid_runtime.so|199496|
|_ZN7android6Thread11_threadLoopEPv|/system/lib64/libutils.so|199496|
|_ZN3art6Thread14CreateCallbackEPv|/apex/com.android.art/lib64/libart.so|193112|
|_ZN3art35InvokeVirtualOrInterface...|/apex/com.android.art/lib64/libart.so|193112|
|_ZN3art9ArtMethod6InvokeEPNS_6ThreadEPjjPNS_6JValueEPKc|/apex/com.android.art/lib64/libart.so|193112|
|art_quick_invoke_stub|/apex/com.android.art/lib64/libart.so|193112|
