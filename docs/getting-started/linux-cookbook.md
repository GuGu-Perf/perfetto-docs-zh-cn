# 实战指南：Linux 追踪方案

本页面收集了在 Linux 上对你的程序进行 profiling 和 tracing 的
**端到端方案**：如何构建以便 trace 可以被符号化、如何录制最常见类型
的 trace，以及事后如何将原始地址转换为函数名。

面向在 Linux 主机或嵌入式 Linux 目标（包括 Yocto、QNX 及类似平台）上
对原生二进制文件进行 profiling 的开发者。每个方案都是独立的，包含下载
所需工具的命令。关于每个主题的完整参考，请点击链接进入更深入的指南：

- [录制系统 trace](/docs/getting-started/system-tracing.md)
- [CPU profiling 和 perf counter](/docs/getting-started/cpu-profiling.md)
- [原生 heap profiling](/docs/data-sources/native-heap-profiler.md)
- [内核函数图追踪](/docs/data-sources/funcgraph.md)
- [符号化与反混淆](/docs/learning-more/symbolization.md)

## 准备：工具和权限 {#setup}

两个工具覆盖了本页面的所有内容。两者都是单文件、自包含的下载：

- **`tracebox`**：录制引擎。它将 `traced`、`traced_probes` 和所有数据源
  实现打包到一个静态链接的二进制文件中。
  ```bash
  curl -LO https://get.perfetto.dev/tracebox
  chmod +x tracebox
  ```
- **`traceconv`**：主机端工具集，用于转换和（此处重要的）符号化 trace。
  它是一个轻量级 Python 包装器，首次使用时会为你的平台下载正确的原生
  二进制文件。
  ```bash
  curl -LO https://get.perfetto.dev/traceconv
  chmod +x traceconv
  ```

从 ftrace 和 `perf_event_open` 录制需要提升的权限。最简单的选项是以
root 身份运行 `tracebox`（`sudo ./tracebox ...`）。或者，在每次启动后
授予一次性特定权限：

```bash
# 基于 ftrace 的数据源（调度、function_graph 等）。
sudo chown -R $USER /sys/kernel/tracing

# perf / 调用栈采样（linux.perf）。
echo -1 | sudo tee /proc/sys/kernel/perf_event_paranoid

# 解析 KERNEL 符号名称（kallsyms）。内核调用栈帧和下面的
# function_graph 方案需要此项。
echo 0  | sudo tee /proc/sys/kernel/kptr_restrict
```

## 构建 Perfetto 可符号化的二进制文件 {#building-with-symbols}

Perfetto 为原生调用栈（来自 CPU profiler 和 heap profiler）录制原始
指令**地址**。要将这些地址转换为函数名、文件和行号，执行符号化的主机
需要未剥离的 ELF 二进制文件，其 **Build ID 要匹配**目标机器上运行的
二进制文件。在录制之前完成此操作。

**1. 使用调试信息编译。**添加 `-g`。这不会改变生成的代码，仅改变附加
的 DWARF 调试信息：

```bash
gcc -g -O2 -o myapp myapp.c        # 或 clang，相同的标志
```

`-O2 -g` 是 profiling 的推荐组合：优化后的代码（因此你 profiling 的是
你实际发布的内容）加上足够的调试信息以将地址映射回源代码行。

**2. 保留 Build ID。**现代工具链默认生成 GNU Build ID。使用以下命令确认：

```bash
readelf -n ./myapp | grep -A1 'Build ID'
```

Build ID 是 Perfetto 将磁盘上的二进制文件与 trace 中记录的映射进行匹配
的方式。两次不同的构建有不同的 Build ID，Perfetto 会拒绝应用不匹配的
符号（这是一个特性，它防止了错误的符号化）。

**3.（可选）发布剥离版本，保留符号。**你不需要将调试信息部署到目标
设备。将其拆分到 sidecar 文件中，并剥离部署的二进制文件；匹配基于
Build ID，因此文件名无需一致：

```bash
gcc -g -O2 -o myapp myapp.c

# 将调试信息拆分到 sidecar 文件中，通过 Build ID 关联回去。
objcopy --only-keep-debug myapp myapp.debug
objcopy --strip-debug --add-gnu-debuglink=myapp.debug myapp

# 将小型、剥离后的 `myapp` 部署到目标设备。
# 在你的主机上保留 `myapp.debug`（或原始的未剥离二进制文件）。
```

在单独打包调试信息的分发版上（`-dbg` / `-dbgsym` / `debuginfo` 包），
在你的主机上安装它们可获得相同结果：`/usr/lib/debug` 下的未剥离符号。

## 方案：带完整符号的 CPU profiling {#cpu-profiling}

目标：一个显示进程 CPU 时间消耗位置、带有真实函数名的火焰图。
这是 [CPU profiling 指南](/docs/getting-started/cpu-profiling.md)的
端到端版本。

**1. 按上述说明[构建带符号的二进制文件](#building-with-symbols)。**

**2. 编写配置。**这会对每个 CPU 每秒采样 100 次调用栈，仅在进程在 CPU
上运行时展开，并添加调度上下文。保存为 `cpu.cfg`，将 `target_cmdline`
改为你的进程名的子串：

```protobuf
duration_ms: 10000

buffers {
  size_kb: 65536
  fill_policy: DISCARD
}

# Periodic callstack sampling, scoped to one process.
data_sources {
  config {
    name: "linux.perf"
    perf_event_config {
      timebase {
        counter: SW_CPU_CLOCK
        frequency: 100
        timestamp_clock: PERF_CLOCK_MONOTONIC
      }
      callstack_sampling {
        scope {
          target_cmdline: "myapp"
        }
        # Also unwind into the kernel. Needs kptr_restrict lowered (see Setup).
        kernel_frames: true
      }
    }
  }
}

# Scheduling context on the same timeline.
data_sources {
  config {
    name: "linux.ftrace"
    ftrace_config {
      ftrace_events: "sched/sched_switch"
      ftrace_events: "sched/sched_waking"
    }
  }
}

# Process and thread names.
data_sources {
  config {
    name: "linux.process_stats"
    process_stats_config {
      scan_all_processes_on_start: true
    }
  }
}
```

**3. 录制**（关于 `tracebox` 下载和权限，参见[准备](#setup)）：

```bash
sudo ./tracebox -c cpu.cfg --txt -o /tmp/trace.pftrace
```

此时**内核**帧已经符号化（从 kallsyms 在设备端解析），但**用户空间**
帧仍是原始地址。

**4. 使用 `traceconv bundle` 嵌入用户空间符号。**它会自动发现已加载的
二进制文件（使用 trace 中记录的绝对路径，这在同机 profiling 时工作良好），
并写出一个独立的自包含 trace：

```bash
# llvm-symbolizer 必须在 $PATH 上，例如 `sudo apt install llvm`。
./traceconv bundle /tmp/trace.pftrace /tmp/trace.bundle
```

如果你的符号文件在其他位置（构建主机、`.debug` 目录、嵌入式 sysroot），
将 `bundle` 指向它们：

```bash
./traceconv bundle \
  --symbol-paths /path/to/sysroot/usr/lib/debug,/path/to/build/out \
  --verbose \
  /tmp/trace.pftrace /tmp/trace.bundle
```

**5. 查看。**在 [Perfetto UI](https://ui.perfetto.dev) 中打开
`/tmp/trace.bundle`；选择样本上方的时间范围以获得火焰图。Build-ID
查找顺序和"找不到库"的故障排除在
[符号化指南](/docs/learning-more/symbolization.md#callstacks) 中有记录。

要生成聚合后的 [pprof](https://github.com/google/pprof) profile：

```bash
./traceconv profile --perf /tmp/trace.pftrace
```

## 方案：原生 heap（内存）profiling {#heap-profiling}

目标：查看哪些调用栈分配了最多的原生（malloc）内存。在 Linux 上，
`heap_profile` 辅助工具可端到端驱动此过程，包括启动带预加载 profiler
的二进制文件。

下载辅助脚本：

```bash
curl -LO https://raw.githubusercontent.com/google/perfetto/main/tools/heap_profile
chmod +x heap_profile
```

在其下运行你的二进制文件：

```bash
python3 heap_profile host -- ./myapp --some-flag
```

该脚本自动下载 `tracebox` 和 `libheapprofd_glibc_preload.so` 预加载库，
在附带 heapprofd 的情况下运行你的二进制文件，并在退出（或 `Ctrl-C`）时
将 `raw-trace` 加上每个进程的 pprof 文件写入它打印的 `/tmp` 目录。
由于你在本地进行 profiling，匹配的二进制文件存在，因此符号会自动解析。

在 [Perfetto UI](https://ui.perfetto.dev) 中打开 `raw-trace` 文件即可
看到分配火焰图。关于完整选项集（自定义预加载库、采样间隔等），参见
[原生 heap profiler：Linux 支持](/docs/data-sources/native-heap-profiler.md#non-android-linux-support)。

## 方案：内核函数图追踪 {#funcgraph}

目标：以嵌套 slice 的形式精确查看哪些内核函数运行了以及运行了多长时间。
最常见的错误是忘记设置 `symbolize_ksyms`，这会导致每个函数都显示为
十六进制地址。

保存为 `funcgraph.cfg`（此配置追踪 `__schedule` 及其调用的所有内容）：

```protobuf
duration_ms: 10000

buffers {
  size_kb: 65536
  fill_policy: DISCARD
}

data_sources {
  config {
    name: "linux.ftrace"
    ftrace_config {
      # Without this, functions show as hex addresses.
      symbolize_ksyms: true
      enable_function_graph: true
      function_graph_roots: "__schedule"
      function_graph_max_depth: 10
    }
  }
}
```

录制（函数图驱动内核 tracer，因此需要 root）：

```bash
sudo ./tracebox -c funcgraph.cfg --txt -o /tmp/funcgraph.pftrace
```

在 UI 中打开 `/tmp/funcgraph.pftrace`；调用以嵌套 slice 形式显示在上文
`Funcgraph` track 中。关于内核要求（`CONFIG_FUNCTION_GRAPH_TRACER`）、
过滤选项以及调用如何可视化，参见专门的
[函数图数据源](/docs/data-sources/funcgraph.md)页面。请注意，与
[CPU profile](#cpu-profiling) 方案不同，这些内核符号来自
`symbolize_ksyms`，**不能**事后通过 `traceconv bundle` 添加。

## 方案：找出线程阻塞的原因 {#blocked-thread}

目标：理解线程为何不断被调离 CPU（锁竞争、优先级反转、阻塞系统调用）。

在 Linux 上，正确的工具是**由调度事件触发的调用栈采样**：使用
`sched/sched_switch`（和 `sched/sched_waking`）tracepoint 作为 perf
的 `timebase`，这样你可以在线程阻塞或被唤醒的精确时刻捕获调用栈。
对于阻塞分析，这远比基于时间的采样精确。

WARNING：Android 的 `blocked_function` 字段（来自
[sched/sched_blocked_reason](/docs/getting-started/android-trace-analysis.md)
中使用的 `sched/sched_blocked_reason` ftrace 事件）是 Android 内核特性，
在主线/桌面 Linux 内核上通常**不**存在。请改用下面的调用栈采样方法。

最小配置（保存为 `blocked.cfg`，将 `comm` filter 调整为你自己的进程）。
tracepoint 的 `filter` 可防止采样器被无关线程淹没：

```protobuf
duration_ms: 10000

buffers {
  size_kb: 102400
  fill_policy: DISCARD
}

data_sources {
  config {
    name: "linux.perf"
    perf_event_config {
      timebase {
        period: 1
        tracepoint {
          name: "sched/sched_switch"
          filter: "prev_comm ~ \"*myapp*\" || next_comm ~ \"*myapp*\""
        }
        timestamp_clock: PERF_CLOCK_MONOTONIC
      }
      callstack_sampling {
        kernel_frames: true
      }
      ring_buffer_pages: 2048
    }
  }
}
```

录制和符号化方式与 [CPU profiling 方案](#cpu-profiling)完全相同
（`sudo ./tracebox -c blocked.cfg --txt -o ...`，然后
`./traceconv bundle ...`）。

关于完整实例，包括同时在 `sched_switch` 和 `sched_waking` 上过滤以及
如何分析捕获的调用栈，参见
[调度阻塞案例分析](/docs/case-studies/scheduling-blockages.md)。
