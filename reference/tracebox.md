# TRACEBOX(1)

## 名称

tracebox - 用于 Perfetto tracing 服务的一体化二进制文件

## 描述

`tracebox` 是一个包含所有 tracing 服务(`traced`,
`traced_probes`)和 `perfetto` 命令行客户端的二进制文件。

它可以用于手动生成各种子进程，或用于"自动启动"模式，该模式将负责为你启动和拆除服务。

## 自动启动模式

如果未指定 applet 名称，`tracebox` 的行为将类似于 `perfetto`
命令，但还会启动 `traced` 和 `traced_probes`。

有关命令行客户端的文档，请参见 [perfetto(1)](perfetto-cli.md)。

### 自动启动模式用法

自动启动模式支持 `perfetto` 操作的简单和普通模式，并额外提供 `--system-sockets` 标志。

在 *自动启动模式* 下使用 `tracebox` 的通用语法如下：

```
 tracebox [PERFETTO_OPTIONS] [TRACEBOX_OPTIONS] [EVENT_SPECIFIERS]
```

`--system-sockets`
:：在使用自动启动模式时强制使用系统套接字。
 默认情况下，`tracebox` 使用私有套接字命名空间以避免
 与系统范围的 `traced` 守护程序冲突。此标志强制它
 使用标准系统套接字，这对于调试与系统 `traced` 服务的交互很有用。

#### 简单模式示例

要在自动启动模式下捕获 10 秒的 `sched/sched_switch` 事件 trace：

```bash
tracebox -t 10s -o trace_file.perfetto-trace sched/sched_switch
```

#### 普通模式示例

要在自动启动模式下使用自定义配置文件捕获 trace：

```bash
cat <<EOF > config.pbtx
duration_ms: 5000
buffers {
 size_kb: 1024
 fill_policy: RING_BUFFER
}
data_sources {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "sched/sched_switch"
 }
 }
}
EOF

tracebox -c config.pbtx --txt -o custom_trace.perfetto-trace
```

## 手动模式

`tracebox` 可用于调用绑定的 applets。

在 *手动模式* 下使用 `tracebox` 的通用语法如下：

```
 tracebox [applet_name] [args ...]
```

以下 applets 可用：

`traced`
:: Perfetto tracing 服务守护程序。

`traced_probes`
:：用于系统范围 tracing 的 Probe(ftrace、/proc 轮询器)。

`traced_relay`
:：将 trace 数据中继到远程 tracing 服务。

`traced_perf`
:：基于 Perf 的 CPU profiling 数据源。

`perfetto`
:：用于控制 Tracing Session 的命令行客户端。

`trigger_perfetto`
:：用于激活 Tracing Session 触发器的实用程序。

`websocket_bridge`
:：用于通过 websocket 连接到 tracing 服务的桥接。