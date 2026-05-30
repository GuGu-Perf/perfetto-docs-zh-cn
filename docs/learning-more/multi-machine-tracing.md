# 多机器记录

本文档介绍如何记录一个同时捕获两台 Linux 机器事件的 Perfetto Trace。它在第二台机器上使用 `traced_relay` 将 Producer IPC 转发到第一台机器上运行的 `traced`。

关于多机器 Tracing 的背景知识及其底层工作原理，请参阅[多机器架构](/docs/deployment/multi-machine-architecture.md)。

## 使用场景

你有一个跨两台 Linux 机器的工作负载——例如机器 A 上的客户端驱动机器 B 上的服务器，或者宿主机运行一个 Linux VM——你想要一个涵盖两台机器的单一 Trace，这样跨机器的因果关系在一个 Timeline 中可见，并且可以在一个 Trace 文件中查询。

在本指南的其余部分，`host` 是运行 `traced` 并拥有 Trace Buffer 的机器，`guest` 是第二台机器，其 Producer 通过 `traced_relay` 接入同一个 Trace。将 `<host-ip>` 替换为 `guest` 可达的 `host` 的 IP 地址（或主机名）。

## 前提条件

* 两台机器上都可用的 `tracebox`。获取二进制文件的方法请参阅[开始使用 Perfetto](/docs/getting-started/start-using-perfetto.md)。
* 从 `guest` 到 `host` 在选定 TCP 端口（例如端口 `20001`）上的网络路径。如果两者之间有防火墙，请开放该端口。
* 两台机器上都没有已运行的 `traced`。在 `guest` 上，`traced` 和 `traced_relay` 会争用同一个本地 Producer Socket；在 `host` 上，你需要下面启动的 `traced`，而不是系统自带的。
* `host` 和 `guest` 是独立的 OS 镜像——两台机器、宿主机加 VM 等。将两个 Producer 指向同一个内核是不行的。

NOTE: 本指南以 ftrace 事件为例进行记录，在 Linux 上通常需要以 root（或具有 `CAP_SYS_ADMIN`）身份运行 Producer 命令。IPC 命令本身不需要 root。

## 用法

### 步骤 1：在 host 上启动 `traced`，监听 TCP

在 `host` 上：

```bash
PERFETTO_PRODUCER_SOCK_NAME=0.0.0.0:20001 \
  tracebox traced --enable-relay-endpoint
```

`PERFETTO_PRODUCER_SOCK_NAME` 将 Producer Socket 从默认的 UNIX 路径重新绑定到远程机器可达的 TCP 监听器。`--enable-relay-endpoint` 使该 Socket 除了接受普通本地 Producer 连接外，还接受 `traced_relay` 连接。

保持此进程运行。

### 步骤 2：在 host 上启动 `traced_probes`

在 `host` 的第二个 Shell 中：

```bash
PERFETTO_PRODUCER_SOCK_NAME=127.0.0.1:20001 \
  sudo -E tracebox traced_probes
```

重新绑定 `traced` 监听器的同一环境变量也告诉本地 Producer 去哪里连接——没有它，`traced_probes` 仍会尝试默认的 UNIX Socket 并失败。`sudo -E` 在 ftrace 所需的权限提升过程中保留环境变量。

### 步骤 3：在 guest 上启动 `traced_relay`

在 `guest` 上：

```bash
PERFETTO_RELAY_SOCK_NAME=<host-ip>:20001 \
  tracebox traced_relay
```

`traced_relay` 在 `guest` 上打开标准的本地 Producer Socket，并将每个 Producer IPC 帧转发到 host 的 Relay 端点。你应该会看到如下启动信息：

```
Started traced_relay, listening on /tmp/perfetto-producer, forwarding to <host-ip>:20001
```

（如果存在 `/run/perfetto/` 目录，监听路径可能是 `/run/perfetto/traced-producer.sock`——两者都是有效的 Linux 默认值。）

保持此进程运行。

### 步骤 4：在 guest 上启动 `traced_probes`

在 `guest` 的第二个 Shell 中：

```bash
sudo tracebox traced_probes
```

不需要环境变量：在 `PERFETTO_PRODUCER_SOCK_NAME` 未设置的情况下，`traced_probes` 连接到默认的 Linux Producer Socket——这正是 `traced_relay` 监听的路径，因此两者会自动找到彼此。

### 步骤 5：从 host 记录 Trace

多机器 Tracing 需要显式的 `TraceConfig`——`tracebox perfetto -t 10s ... sched/sched_switch` 简写只在 host 机器上记录（参见[多机器架构](/docs/deployment/multi-machine-architecture.md#data-source-dispatch)）。

在 `host` 上，编写配置文件：

```bash
cat > config.pbtx <<'EOF'
buffers {
  size_kb: 32768
  fill_policy: RING_BUFFER
}
trace_all_machines: true
data_sources {
  config {
    name: "linux.ftrace"
    ftrace_config {
      ftrace_events: "sched/sched_switch"
    }
  }
}
duration_ms: 10000
EOF
```

然后记录：

```bash
tracebox perfetto --txt -c config.pbtx -o trace.pftrace
```

### 步骤 6：验证两台机器都在 Trace 中

在 <https://ui.perfetto.dev> 打开 `trace.pftrace`。在 SQL 查询视图中运行：

```sql
SELECT id, raw_id, sysname, release, arch, num_cpus FROM machine;
```

应看到两行。`id = 0` 始终是 host；远程机器的 `raw_id` 非零。完整列信息参见 [`machine` 表参考][machine-table]。

要确认两台机器的事件都进入了 Trace，按机器对 ftrace 事件分组。`ftrace_event` 不直接携带 `machine_id`——每行引用一个 `cpu`（通过 `ucpu`），而 `cpu` 携带 `machine_id`：

```sql
SELECT cpu.machine_id, COUNT(*) AS num_events
FROM ftrace_event
JOIN cpu USING (ucpu)
GROUP BY cpu.machine_id;
```

你应该看到每台机器一行，且计数均非零。同样的 JOIN 模式也适用于 `thread` 或 `process` 表，以按不同维度按机器切片数据。

## 故障排除

* **`machine` 表中只有一行。** 连接问题。检查从 `guest` 是否可达 `<host-ip>:20001`（例如使用 `nc -zv`），防火墙是否开放，以及 host 上的 `traced` 是否绑定了 `0.0.0.0`（而非 `127.0.0.1`）。
* **`traced_relay` 立即退出并打印用法。** `PERFETTO_RELAY_SOCK_NAME` 未设置或为空——`traced_relay` 没有可转发的主机。
* **guest 上的 `traced_probes` 连接失败。** 确保 guest 上的 `traced_relay` 正在运行（步骤 3），且没有过期的 `traced` 也在该处运行争用 Producer Socket。
* **host 上的 Producer 连接失败。** 确认 `traced` 使用 `PERFETTO_PRODUCER_SOCK_NAME=0.0.0.0:20001` 启动（步骤 1），且 Producer 指向同一地址（步骤 2）。

## 下一步

* [多机器架构](/docs/deployment/multi-machine-architecture.md)——原理：`traced_relay`、机器标识和跨内核时钟同步如何协同工作。
* [PerfettoSQL：入门](/docs/analysis/perfetto-sql-getting-started.md)——用于按 `machine_id` 跨 `cpu`、`thread` 和 `process` 切片生成的 Trace。
* [Trace Processor](/docs/analysis/trace-processor.md)——当记录可重复时，将分析嵌入脚本或流水线。

[machine-table]: /docs/analysis/sql-tables.autogen#machine
