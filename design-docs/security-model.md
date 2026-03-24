# Android/Linux 系统范围 tracing 的安全模型

tracing 服务有两个端点(在 Chromium 中：Mojo 服务，在 Android/Linux 上：UNIX sockets)：一个用于 producer(s)，一个用于 consumer(s)。前者通常是公共的，后者仅限于受信任的 consumers。

![Security overview](https://storage.googleapis.com/perfetto/markdown_img/security-overview.png)

## 生产者

Producers 永远不被信任。我们假设它们会尽最大努力 DoS / 崩溃 / 利用 tracing 服务。我们在 [service/tracing_service_impl.cc](/src/tracing/service/tracing_service_impl.cc) 中这样做，以便无论嵌入者和 IPC 传输如何，都应用相同级别的安全性和测试。

## Tracing 服务

- tracing 服务必须验证所有输入。
- 在最坏情况下，tracing 服务中的允许远程代码执行的错误，tracing 服务应该没有任何有意义的可利用功能。
- tracing 服务的设计具有有限的系统调用表面，以简化其沙盒化：
  - 它不打开或创建文件（% tmpfs）。
  - 它只写入通过 IPC 通道传递的文件描述符。
  - 它不打开或创建 sockets(在 Android 上，IPC sockets 由 init 传递，请参阅 [perfetto.rc](/perfetto.rc))
  - 在 Android 上，它以 nobody:nobody 身份运行，并且被允许做的事情很少，请参阅 [traced.te](https://android.googlesource.com/platform/system/sepolicy/+/main/private/traced.te)。
  - 在 Chromium 中，它应该作为实用程序进程运行。

## 消费者
Consumers 始终被信任。它们仍然不应该能够崩溃或利用服务。然而，它们很容易 DoS 它，但这是有意的。
  - 在 Chromium 中，信任路径通过服务清单建立。
  - 在 Android 中，信任路径通过将 consumer socket 锁定到 shell 通过 SELinux 来建立。

## 共享内存隔离
内存仅在每个 producer 和 tracing 服务之间点对点共享。我们永远不应该跨 producers 共享内存（以避免泄漏属于不同 producers 的 trace 数据），也不应该在 producers 和 consumers 之间共享（这将打开难以审计的路径，连接不受信任和无特权实体与受信任和更多权限实体）。

## trace 内容的证明
tracing 服务保证 Service 编写的 `TracePacket` 字段不能由 Producer(s) 欺骗。尝试定义这些字段的数据包将被拒绝，除了时钟快照。有关更多详细信息，请参阅 [PacketStreamValidator](/src/tracing/service/packet_stream_validator.cc) 和 [其单元测试](/src/tracing/service/packet_stream_validator_unittest.cc)。
目前没有什么可以阻止 producer 编写不属于其数据源的 `TracePacket(s)`。实际上，服务永远不会阻止这样做，因为这样做意味着服务知道所有可能的数据包类型，这无法扩展。但是，服务将 producer 的 POSIX uid 附加到每个 `TracePacket` 以执行 trace 内容的离线证明。
