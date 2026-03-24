# 跨重启 trace

_此数据源仅在基于 Linux 的系统上受支持。_

"linux.frozen_ftrace" 数据源用于读取在持久环形缓冲区中记录的上一次启动的 ftrace trace 数据。

此数据源允许你转储上一次启动时间的 ftrace trace 数据的最后几秒，以便从 ftrace trace Log 分析系统崩溃原因。

因此，预期用户在特殊的持久环形缓冲区上在后台运行另一个 perfetto trace 会话。

### 创建持久环形缓冲区

你必须通过内核 cmdline 设置 ftrace 持久环形缓冲区。如果你需要 20MiB 持久环形缓冲区，则需要在启动时向内核 cmdline 添加以下内核选项：

```
reserve_mem=20M:2M:trace trace_instance=boot_mapped^traceoff@trace
```

这将在保留的内存区域上创建一个 `boot_mapped` ftrace 实例，该实例将保留数据并在下一次启动时重新附加。（注意: 如果内核配置已更改或内核地址映射由 KASLR 更改，则这不是 100% 确定。）

### 使用持久环形缓冲区

通常，perfetto 将在顶级实例而不是子实例中记录 ftrace 数据。因此，你需要向 trace 配置指定 `instance_name:` 选项。此外，你需要将 trace 会话作为长时间运行的后端会话运行。你需要：

- 将 `RING_BUFFER` fill_policy 指定给接收 ftrace 数据源的所有缓冲区。
- 将 `instance_name: "boot_mapped"` 指定给 ftrace 数据源。（注意: 从此数据源拆分 `atrace` 数据源，因为与此实例不能使用 atrace 相关事件。）
- 不要指定 `duration_ms:`。

并使用 `--background` 选项运行 perfetto 命令。

完成后，准备崩溃。

### 崩溃后读取数据

系统崩溃后，你将看到 `boot_mapped` 实例，该实例应保留最后几秒记录的 trace 数据。

使用 `"linux.frozen_ftrace"` 数据源运行 perfetto，如：

```
buffers {
 size_kb: 65536
 fill_policy: DISCARD
}

data_sources {
 config {
 name: "linux.frozen_ftrace"
 frozen_ftrace_config {
 instance_name: "boot_mapped"
 }
 }
}

duration_ms: 5000
```
