# Perfetto tracing session 的生命周期

本文档解释了 producer、service 和 consumer 在 tracing session 期间如何端到端交互，并引用了代码和 IPC 请求/响应。

1. 一个或多个 producers 连接到 tracing 服务并设置它们的 IPC 通道。
2. 每个 producer 通过 [`RegisterDataSource`](/protos/perfetto/ipc/producer_port.proto#34) IPC 宣告一个或多个数据源。Producer 在此之前没有任何其他操作。默认情况下没有任何内容被 trace。
3. Consumer 连接到 tracing 服务并设置 IPC 通道。
4. Consumer 通过 [`EnableTracing`](/protos/perfetto/ipc/consumer_port.proto#65) IPC 向服务发送 [trace config](/docs/concepts/config.md) 启动 tracing session。
6. 服务创建配置中指定的多个新 trace 缓冲区。
7. 服务遍历 trace config 的 [`data_sources`](/protos/perfetto/config/trace_config.proto#50) 部分：对于每个条目，如果在 producer（s）中找到匹配的数据源(根据步骤 2 中宣告的内容):
8. 服务发送 [`SetupTracing`](/protos/perfetto/ipc/producer_port.proto#112) IPC 消息，向 producer（s）传递共享内存缓冲区（每个 producer 只一次）。
9. 服务向每个 producer 发送 [`StartDataSource`](/protos/perfetto/ipc/producer_port.proto#105) IPC 消息，针对 trace config 中配置的且在 producer 中存在的每个数据源（如果有）。
10. Producer 按照上一步骤的指示创建一个或多个数据源实例。
11. 每个数据源实例创建一个或多个 [`TraceWriter`](/include/perfetto/ext/tracing/core/trace_writer.h)(通常每个线程一个)。
12. 每个 `TraceWriter` 写入一个或多个 [`TracePacket`](/protos/perfetto/trace/trace_packet.proto)。
13. 这样做时，每个 `TraceWriter` 使用 [`SharedMemoryArbiter`](/include/perfetto/ext/tracing/core/shared_memory_arbiter.h) 获取共享内存缓冲区的 chunks 所有权。
14. 在写入 `TracePacket` 时，`TraceWriter` 将不可避免地跨越 chunk 边界（通常为 4KB，但可以配置为更小）。
15. 当发生这种情况时，`TraceWriter` 将释放当前 chunk 并通过 `SharedMemoryArbiter` 获取新 chunk。
16. `SharedMemoryArbiter` 将带外发送 [`CommitDataRequest`](/protos/perfetto/ipc/producer_port.proto#41) 到服务，请求将共享内存缓冲区的某些 chunk 移动到最终 trace 缓冲区。
17. 如果一个或多个长 `TracePacket` 在几个 chunks 上分段，则这些 chunk 中的某些可能已经从共享内存缓冲区消失并提交到最终 trace 缓冲区（步骤 16）。在这种情况下，`SharedMemoryArbiter` 将发送另一个 `CommitDataRequest` IPC 消息以请求将 chunk 数据带外修补到最终 trace 缓冲区。
18. 服务将检查由元组 `{ProducerID (unspoofable), WriterID, ChunkID}` 标识的给定 chunk 是否仍存在于 trace 缓冲区中，如果是，则继续修补它（% 检查）。
19. Consumer 向服务发送 [`FlushRequest`](/protos/perfetto/ipc/consumer_port.proto#52)，要求它提交 trace 缓冲区中所有正在传输的数据。
20. 服务向 tracing session 中涉及的所有 producers 发出 [`Flush`](/protos/perfetto/ipc/producer_port.proto#132) 请求。
21. Producer(s) 将 `Flush()` 所有它们的 `TraceWriter` 并向服务刷新请求回复。
22. 一旦服务收到来自所有 producers 的所有刷新请求的 ACK(或 [刷新超时](/protos/perfetto/ipc/consumer_port.proto#117) 已过期)，它就向消费者的 `FlushRequest` 回复。
23. Consumer 可选地发送 [`DisableTracing`](/protos/perfetto/ipc/consumer_port.proto#38) IPC 请求以停止 tracing 并冻结 trace 缓冲区的内容。
24. 服务将向每个 Producer 中的每个数据源广播 [`StopDataSource`](/protos/perfetto/ipc/producer_port.proto#110) 请求。
25. 此时 Consumer 发出 [`ReadBuffers`](/protos/perfetto/ipc/consumer_port.proto#41) IPC 请求（除非它之前在通过 trace config 的 `write_into_file` 字段启用 tracing 时向服务传递了文件描述符）。
26. 服务读取 trace 缓冲区并将所有 `TracePacket(s)` 流式传输回消费者。
27. 如果存储在 trace 缓冲区中的 trace 数据包不完整（例如，缺少片段）或标记为待带外修补，则给定的 writer 序列被中断，不再读取该序列的更多数据包。其他 `TraceWriter` 序列的数据包不受影响。
28. Consumer 发送 `FreeBuffers`(或简单地断开连接)。
29. 服务为会话拆除所有 trace 缓冲区。
