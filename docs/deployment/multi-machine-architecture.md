# 多机器架构

Perfetto 可以记录跨越多个操作系统镜像的单一 Trace——例如宿主机和一个或多个虚拟机 Guest、SoC 和协处理器、或驱动共享工作负载的测试机集群。结果是一个跨机器因果关系可见且可查询的 Timeline，而不是每台机器一个需要手动关联的 Trace。

本页解释多机器 Tracing *是什么*以及各个组件*如何*协同工作。分步设置请参阅[多机器记录](/docs/learning-more/multi-machine-tracing.md)。

## 问题描述

标准的[服务模型](/docs/concepts/service-model.md)假设所有 Producer、`traced` 服务和 Consumer 共享同一个 OS 镜像：它们通过本地 UNIX Socket 连接 `traced`，共识 PID，并观察相同的 `CLOCK_BOOTTIME`。

当 Producer 位于不同内核时，这个假设就失效了。没有共享的文件系统 Socket。PID 命名空间是独立的。启动时钟在不同时间点开始，并且各自独立漂移。在每台机器上运行单独的 `traced` 然后事后拼接结果 Trace 是可行的，但很脆弱，特别是对任何时间敏感的场景（如跨机器调度或 RPC 延迟）。

多机器 Tracing 在不重复每台机器的 Buffer 或 Consumer 机制的情况下解决了这个问题。

## 架构

配置中只有一台机器运行 `traced`（"host"）。其余每台机器运行 `traced_relay`，将 Producer 端 IPC 转发到 host：

```
   远程机器                               Host 机器
  ┌────────────────────────┐               ┌────────────────────────────┐
  │ traced_probes          │               │  traced --enable-relay-    │
  │ + 其他 Producer        │               │          endpoint          │
  │        │               │               │           ▲                │
  │        ▼ (本地 IPC)    │   TCP/vsock   │           │ (本地 IPC)     │
  │  traced_relay  ────────┼──────────────►│  relay 端点               │
  └────────────────────────┘               │           ▲                │
                                           │           │                │
                                           │   traced_probes / 其他     │
                                           │   本地 Producer            │
                                           │           ▲                │
                                           │           │ (Consumer IPC) │
                                           │      perfetto 命令行       │
                                           └────────────────────────────┘
```

`traced_relay` 被有意设计得很轻量：它在本地 Producer Socket 上接受 Producer 连接，与 host 交换少量元数据（见下文），然后通过 TCP 或 vsock 代理 Producer IPC 帧。它不缓冲 Trace 数据，不解析 Trace Packet，也不实现任何 Consumer 端功能。

Consumer（`perfetto` 命令行或 UI 的 WebSocket 桥接）只与 host 的 `traced` 通信。Trace 配置、Buffer 所有权和最终读取都停留在同一台机器上。

## 机器标识

当 `traced_relay` 首次连接到 host 时，它发送一个包含 `machine_id_hint` 的 `SetPeerIdentity` 消息——在 Linux 上，这来源于 `/proc/sys/kernel/random/boot_id`（如果可用），或者以 `uname(2)` 加启动时间戳源的哈希作为回退。该提示在同一内核的重新连接中是稳定的，但在不同内核之间是不同的。

Host 的 `traced` 将每个唯一提示映射到一个小的整数 `MachineId`，并为从该 Relay 到达的每个 `TracePacket` 加盖该 ID（`TracePacket` 上的 `machine_id` 字段）。在导入时，[Trace Processor] 在 `machine` 表中为每台机器生成一行：

| 列 | 描述 |
| -- | ---- |
| `id` | Trace Processor 分配的机器 ID。host 始终为 `0`。 |
| `raw_id` | Trace Packet 中的原始机器标识符（host 为 `0`，远程机器非零）。 |
| `sysname`、`release`、`version`、`arch` | 该机器的 `uname(2)` 字段。 |
| `num_cpus` | 该内核可见的 CPU 数量。 |
| `system_ram_bytes`、`system_ram_gb` | 总 RAM。 |
| `android_build_fingerprint`、`android_device_manufacturer`、`android_sdk_version` | 仅对 Android 机器填充。 |

具有每 CPU 或每线程维度的表（`thread`、`cpu`、`gpu_counter_track` 等）携带可为空的 `machine_id`，以便跨机器数据可以通过 SQL 切片。UI 对每机器 Track 的支持仍在完善中，因此 `machine_id` JOIN 目前仍是回答跨机器问题最可靠的方式。

## 跨机器时钟同步

每台远程机器都有自己的 `CLOCK_BOOTTIME`，因此其 Producer 写入的时间戳不能直接与 host 时间戳比较。`traced_relay` 针对 host 的 Relay 端点运行一个轻量级 Ping 协议，发送和接收带时间戳的消息来估算每机器的时钟偏移和往返时间。Host 定期将估算的偏移作为 `ClockSnapshot` Packet 发出到 Trace 中。

此后一切复用[时钟同步](/docs/concepts/clock-sync.md)中描述的现有单机器机制：Trace Processor 将跨机器偏移折叠到它已经为 `CLOCK_REALTIME`、`CLOCK_MONOTONIC` 等构建的同一时钟图中，并在导入时将每个事件解析为单一的全局 Trace 时钟。DataSource 不需要做任何额外工作。

## {#data-source-dispatch} DataSource 调度

默认情况下，`traced` 只将 DataSource 调度到 host 机器上的 Producer。要从远程机器收集数据，Consumer 的 `TraceConfig` 必须显式选择，可以通过全局设置 `trace_all_machines: true`，或针对每个 DataSource 设置 `DataSource.machine_name_filter`。没有其中之一，远程机器上的 `traced_probes` 仍然会注册并作为一行出现在 `machine` 表中，但不会被分配请求的 DataSource，因此不会有事件从中流出。

`trace_all_machines` 在 v54 中引入；早期版本默认匹配所有机器。远程端的机器名来自启动 `traced_relay` 时的 `PERFETTO_MACHINE_NAME` 环境变量，回退到 `uname -s`。字面名称 `"host"` 是运行 `traced` 的机器的同义词。

单个内核上的 Producer 不能代替"两台机器"，即使用于测试。两个 `traced_probes` 实例会争用相同的 `/sys/kernel/tracing/` 环形 Buffer，每 CPU 事件会在两个 `machine_id` 之间任意分区——Trace 看起来有效但实际上已被撕裂。多机器设置需要两个内核（两台机器、宿主机加 VM、具有独立内核命名空间的容器等）。

## 限制与约束

* `traced_relay` 不能与 `traced` 运行在同一台机器上——两者都绑定本地 Producer Socket。配置中的每台机器运行 `traced`（host）*或* `traced_relay`（其余每台机器）。
* 每台远程机器必须有到 host 的 Relay 端点的网络路径，基于 TCP 或 vsock。
* 跨机器时钟对齐仅取决于 Ping 协议对偏移的测量精度；大致对齐的挂钟（NTP 或类似）有助于初始 Snapshot，但并非严格要求。
* UI 的每机器 Track 渲染仍在完善中。对 `machine` 表和 `machine_id` 列进行 SQL 查询是目前切片跨机器数据的权威方式。

## 下一步

* [多机器记录](/docs/learning-more/multi-machine-tracing.md)——两台 Linux 主机之间记录多机器 Trace 的分步演练。
* [时钟同步](/docs/concepts/clock-sync.md)——跨机器偏移在导入时折叠进去的单机器时钟同步图。
* [`machine` 表参考](/docs/analysis/sql-tables.autogen#machine)——从 `SetPeerIdentity` 填充的表完整 Schema。

[Trace Processor]: /docs/analysis/trace-processor.md
