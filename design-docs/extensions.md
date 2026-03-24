# 扩展：向 traces 添加新类型

NOTE: **扩展是正在进行的工作，目前还不能使用**

目前，在不修改 Perfetto 上游 proto 消息定义的情况下，不可能在使用 Perfetto 时向 traces 添加新类型。

本文档描述了正在进行的工作，即使用 [protobuf 扩展](https://developers.google.com/protocol-buffers/docs/overview#extensions)，以便能够在 Perfetto 存储库之外定义新的类型化消息。

### Protozero 支持

Perfetto 使用自己的协议缓冲消息代码生成实现，称为 [Protozero](/docs/design-docs/protozero.md)，这不是完整的 protobuf 实现。扩展的实现相当有限，所有扩展都应该嵌套在用于提供生成代码的类名的消息中。

例如，

```protobuf
 message MyEvent {
 extend TrackEvent {
 optional string custom_string = 1000;
 }
 }
```

将生成 `TrackEvent` 的子类，称为 `MyEvent`，除了 `TrackEvent` 中定义的所有其他 protobuf 字段外，它还有一个设置 `custom_string` 的新方法。

### 反序列化

在分析 traces 时，不直接使用 protos，而是将它们解析到数据库中，可以通过 SQL 查询该数据库。为了使其成为可能，Perfetto 必须知道扩展的字段描述符（扩展 proto 模式的二进制表示）。目前，唯一的方法是添加 [ExtensionDescriptor 数据包](reference/trace-packet-proto.autogen#ExtensionDescriptor)。将来，将有一种在编译时指定 protobuf 扩展的方法，以便能够在每个 trace 中避免这种开销。

然而，在 trace 本身中指定扩展描述符的能力仍然有用，以便能够在本地开发期间添加新类型化消息时使用预编译的 trace processor 的 UI。

目前仅支持 TrackEvent 消息的 protobuf 扩展反序列化，并通过 ProtoToArgsUtils 类在 trace processor 中实现。扩展将出现在 args 表中，类似于其他 trace 事件参数。

### 在 Perfetto 中测试扩展支持

Perfetto trace processor 主要通过集成测试进行测试，其中输入 traces 最常以 textproto 格式指定。Textproto 格式支持扩展，但解析器必须知道所有使用的扩展。为了使其成为可能，集成测试中使用的所有扩展都必须在 `test_extensions.proto` 文件中指定。由于此文件仅在测试工具中使用并由 protoc 解析，因此它不必遵守所有扩展都在包装器消息内的约定，这有助于使扩展标识符更简洁。
