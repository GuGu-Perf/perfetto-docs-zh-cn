# 实战指南：本地 Android Trace 录制

本页面收集了在标准交互式工作流无法覆盖的情况下，在 Android 上录制
Perfetto trace 的**端到端方案**。

- [追踪 Android 启动](#boot-tracing)：录制覆盖启动序列的 trace，
  这是设备启动时无法手动启动的。
- [在 OutOfMemoryError 时捕获 heap dump](#oom-heap-dump)：
  当应用因 `OutOfMemoryError` 崩溃时自动转储 Java heap，
  以便精确看到当分配开始失败时是什么占用了内存。

这些方案假设主机可以通过 `adb` 访问设备。每个方案都是独立的：按原样
复制配置和命令，然后调整高亮的参数。如果你从未录制过 trace，请先从
[系统追踪教程](/docs/getting-started/system-tracing.md) 开始。
关于每个主题的完整参考，请点击链接进入更深入的指南：

- [Trace 配置](/docs/concepts/config.md)
- [ART heap dump](/docs/data-sources/java-heap-profiler.md)
- [分析 Android trace](/docs/getting-started/android-trace-analysis.md)

## 方案：追踪 Android 启动 {#boot-tracing}

目标：录制覆盖 Android 启动序列的 trace，用于分析进程启动、调度
以及设备启动期间发生的所有其他内容。

设备启动时你无法手动启动 trace。取而代之的是，自 Android 13 (T)
起，perfetto 可以被预装以在下次启动时自动开始录制。

**1. 编写配置。**启动 trace 配置必须采用 **text** 格式（而非二进制）。
将以下内容保存为 `boottrace.pbtxt`。它会录制进程调度和生命周期事件，
但任何 [trace 配置](/docs/concepts/config.md) 都可在此使用
（更多示例见 [/test/configs/](/test/configs/)）：

```protobuf
# One buffer allocated within the central tracing binary for the entire trace,
# shared by the two data sources below.
buffers {
  size_kb: 32768
  fill_policy: DISCARD
}

# Ftrace data from the kernel, mainly the process scheduling events.
data_sources {
  config {
    name: "linux.ftrace"
    target_buffer: 0
    ftrace_config {
      ftrace_events: "sched_switch"
      ftrace_events: "sched_waking"
      ftrace_events: "sched_wakeup_new"

      ftrace_events: "task_newtask"
      ftrace_events: "task_rename"

      ftrace_events: "sched_process_exec"
      ftrace_events: "sched_process_exit"
      ftrace_events: "sched_process_fork"
      ftrace_events: "sched_process_free"
      ftrace_events: "sched_process_hang"
      ftrace_events: "sched_process_wait"
    }
  }
}

# Resolve process commandlines and parent/child relationships, to better
# interpret the ftrace events, which are in terms of pids.
data_sources {
  config {
    name: "linux.process_stats"
    target_buffer: 0
  }
}

# 10s trace, but can be stopped prematurely via `adb shell pkill perfetto`.
duration_ms: 10000
```

**2. 将配置推送到设备。**路径是固定的；perfetto 仅在
`/data/misc/perfetto-configs/boottrace.pbtxt` 中查找：

```bash
adb push boottrace.pbtxt /data/misc/perfetto-configs/boottrace.pbtxt
```

**3. 为下次启动预装追踪：**

```bash
adb shell setprop persist.debug.perfetto.boottrace 1
```

该属性在启动期间被重置，因此每次启动 trace 都是一次性的：要追踪
另一次启动，需要再次设置该属性。

**4. 重启设备：**

```bash
adb reboot
```

**5. 拉取 trace。**Trace 写入
`/data/misc/perfetto-traces/boottrace.perfetto-trace`。该文件仅在
录制停止后出现，即 `duration_ms` 经过之后，因此请保持合理的时间值。
（如果你的配置设置了 `write_into_file: true`，文件则会以
`file_write_period_ms` 为间隔增量写入。）

```bash
adb pull /data/misc/perfetto-traces/boottrace.perfetto-trace
```

该文件在下次启动 trace 开始前会被移除，因此在预装下一次之前先拉取它。

**6. 查看。**在 [Perfetto UI](https://ui.perfetto.dev) 中打开
`boottrace.perfetto-trace`。要使用 SQL 深入分析数据，参见
[Android trace 分析实战指南](/docs/getting-started/android-trace-analysis.md)。

### Trace 在启动的哪个阶段开始？

Trace 由 `perfetto_trace_on_boot` 一次性 init 服务启动，该服务定义于
[perfetto.rc](/perfetto.rc) 中。Init 在三个条件满足时启动它：持久属性
已加载（仅在 `/data` 挂载后发生）、`traced` 守护进程已启动，且启动尚
未完成。最后一个条件就是为什么在已启动的设备上设置该属性会预装
*下次*启动而非立即启动 trace。因此，最早启动阶段（内核初始化、挂载
文件系统）不在 trace 覆盖范围内。

## 方案：在 OutOfMemoryError 时捕获 heap dump {#oom-heap-dump}

目标：在进程因 `java.lang.OutOfMemoryError` 崩溃的瞬间自动捕获 ART
（Java/Kotlin）heap dump，以便精确看到当分配开始失败时是什么占用了内存。

自 Android 14 (U) 起，当 Java 进程即将因 `OutOfMemoryError` 崩溃时，
ART 会通知 perfetto，perfetto 可以将该通知用作触发器来转储崩溃进程的
Java heap。

### 选项 A：使用辅助脚本

如果你有 perfetto 仓库检出，`tools/java_heap_dump` 可以端到端驱动此
过程。传入 `--wait-for-oom` 以及要监视的进程（`-n '*'` 匹配所有进程）：

```bash
tools/java_heap_dump --wait-for-oom --oom-wait-seconds 3600 \
  -n 'com.example.myapp' -o oome.pftrace
```

脚本启动一次 tracing session，等待最多 `--oom-wait-seconds` 秒直到
抛出 `OutOfMemoryError`，然后将 heap dump 拉取到 `oome.pftrace`。

### 选项 B：仅使用 adb

如果你没有检出仓库，以下命令仅通过 `adb` 访问即可完成相同操作。
可以直接复制粘贴使用：

```bash
cat << EOF | adb shell perfetto -c - --txt -o /data/misc/perfetto-traces/oome.pftrace
buffers: {
    size_kb: 524288
    fill_policy: DISCARD
}

data_sources: {
    config {
        name: "android.java_hprof.oom"
        java_hprof_config {
          process_cmdline: "*"
        }
    }
}

data_source_stop_timeout_ms: 100000

trigger_config {
    trigger_mode: START_TRACING
    trigger_timeout_ms: 3600000
    triggers {
      name: "com.android.telemetry.art-outofmemory"
      stop_delay_ms: 500
    }
}
data_sources {
  config {
    name: "android.packages_list"
  }
}
EOF
```

这会启动一个 tracing session，等待最多一小时
（`trigger_timeout_ms`）让任意 ART 运行时实例遇到
`OutOfMemoryError`。要仅监视你自己的应用，将 `process_cmdline` 中的
`"*"` 替换为应用的进程名（例如 `"com.example.myapp"`）。

一旦遇到错误，heap 被转储且追踪停止：

```text
[862.335]    perfetto_cmd.cc:1047 Connected to the Perfetto traced service, TTL: 3601s
[871.335]    perfetto_cmd.cc:1210 Wrote 19487866 bytes into /data/misc/perfetto-traces/oome.pftrace
```

然后拉取 heap dump：

```bash
adb pull /data/misc/perfetto-traces/oome.pftrace
```

### 分析 heap dump

在 [Perfetto UI](https://ui.perfetto.dev) 中打开 `oome.pftrace`，
点击 _"Heap Profile"_ track 中的菱形标记，即可获取保留内存的火焰图。
关于引导式调查，请参见：

- [Heap Dump Explorer](/docs/visualization/heap-dump-explorer.md)，
  交互式支配树和 heap dump 的类级别分析。
- [调试内存使用](/docs/case-studies/memory.md)，调查 Android 内存
  问题的端到端指南。
- [ART heap dump](/docs/data-sources/java-heap-profiler.md)，
  底层数据源的完整参考。
