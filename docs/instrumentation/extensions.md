# 使用自定义 Proto 扩展 TrackEvent

Perfetto 的 trace 格式是可扩展的：你可以在不 fork Perfetto 或修改其上游 proto 定义的情况下，将自己的强类型字段附加到 `TrackEvent` 上。这是通过 [protobuf extensions](https://developers.google.com/protocol-buffers/docs/overview#extensions) 实现的，并且是一个完全受支持的机制。

这是向 trace 中添加自定义结构化数据的推荐方式。它可以端到端地工作：事件通过 C++ SDK 的类型安全访问器写入，或者在手动生成 trace 时直接发出 protobuf 字节，自动解析到 Trace Processor 的 `args` 表中，并在 Perfetto UI 中显示。

在以下情况下使用扩展：

- 你需要的不仅仅是非结构化的调试注解（字符串、整数）——你的事件具有 SQL 查询将从中受益的结构。
- 你不想（或无法）将你的 proto 定义上游到 Perfetto。
- 你需要在生产者、Trace Processor 和 UI 之间使用相同的事件 schema，而无需协调发布。

本指南分为两部分：

- [**基础知识**](#fundamentals)——定义 `.proto`、向 Trace Processor 传递描述符，以及在 SQL 中查询扩展字段。请先阅读此部分；它适用于每个生产者。
- **发出事件**——选择适合你的配置的路径：
  - [使用 C++ SDK](#emitting-events-with-the-c-sdk)——从 `TRACE_EVENT` 进行类型化或内联字段访问。
  - [不使用 SDK](#emitting-events-without-the-sdk)——任何直接写入 Perfetto protobuf 的工具，例如在[将任意数据转换为 Perfetto](/docs/getting-started/converting.md) 时。

## Fundamentals

### 定义扩展

将你的 schema 拆分到两个 `.proto` 文件中：一个*数据*文件，定义你的字段承载的嵌套消息类型；一个*扩展*文件，将这些类型 Hook 到 [`TrackEvent`](/docs/instrumentation/track-events.md) 的特定字段编号上。这种拆分是 Python 演练所依赖的（数据文件为运行时使用而编译；扩展文件仅编译为 Trace Processor 的 `FileDescriptorSet`），并且使 C++ SDK 的布局保持对称。

**文件 1 — `acme_data.proto`** 是你的常规数据 schema。

```protobuf
syntax = "proto2";
package com.acme;

message AcmeRequestMetadata {
  optional string endpoint = 1;
  optional uint32 priority = 2;
}
```

**文件 2 — `acme_extension.proto`** 是扩展 *Hook*。按照惯例，将 `extend` 块放在一个包装消息中：如果你计划生成 C++ SDK 绑定，这是必需的——[Protozero](/docs/design-docs/protozero.md) 使用包装消息名作为生成的类名——无论是否生成绑定，都建议这样做以确保可移植性。

```protobuf
syntax = "proto2";
import "protos/perfetto/trace/perfetto_trace.proto";
import "acme_data.proto";
package com.acme;

message AcmeExtension {
  extend perfetto.protos.TrackEvent {
    optional string request_id = 9900;
    repeated int32 retry_latencies_ms = 9901;
    optional AcmeRequestMetadata request_metadata = 9902;
  }
}
```

将 `perfetto_trace.proto` 的副本（[从 GitHub 下载](https://github.com/google/perfetto/blob/main/protos/perfetto/trace/perfetto_trace.proto)）放在 `protos/perfetto/trace/` 下，以便 import 能够解析。最终布局：

```
project/
├── protos/perfetto/trace/perfetto_trace.proto   # 来自 Perfetto 仓库
├── acme_data.proto
└── acme_extension.proto
```

字段编号 1000 及以上保留给扩展使用。选择一个不会与你共享 trace 的其他扩展生产者冲突的范围。

### 使扩展对 Trace Processor 和 UI 可见

Trace Processor 需要你的扩展的 proto 描述符才能解析它们。一旦描述符可用，每个扩展字段都会自动解码并插入到 `args` 表中——Trace Processor 本身不需要逐字段注册。

有三种传递描述符的方式：

#### 方式 1：在 trace 中嵌入描述符（`ExtensionDescriptor` Packet）

这是最便携的选项：trace 是自描述的，因此 Trace Processor 可以在任何地方解析它而无需额外配置。

将你的 `.proto` 编译为 `FileDescriptorSet`（例如 `protoc --include_imports --descriptor_set_out=acme.desc acme_extension.proto`），并在 trace 前面添加一个包含该描述符集字节的 [`ExtensionDescriptor`](/docs/reference/trace-packet-proto.autogen#ExtensionDescriptor) Packet。

如果你在启动服务时将描述符集传递给 `TracingService::InitOpts::extension_descriptors`，Tracing 服务可以自动执行此操作。如果你需要在特定 Session 中退出，请设置 `TraceConfig.disable_extension_descriptors = true`。

对于不使用 C++ SDK 的写入器，[synthetic track event 演练](/docs/reference/synthetic-track-event.md#proto-extensions)在 Python 中端到端地展示了这种方法，包括如何编译描述符集并将其嵌入 trace 中。

#### 方式 2：Android 系统级描述符

在 Android 上，`traced` 在启动时从 `/etc/tracing_descriptors.gz` 和 `/vendor/etc/tracing_descriptors.gz` 读取描述符集，并将它们作为 `ExtensionDescriptor` Packet 发出到每个 trace 中。将你的扩展描述符集发布到这些路径之一，即可覆盖设备上采集的所有 trace。

> NOTE: 这是 Perfetto 于 2026 年 2 月通过 [RFC-0017](https://github.com/google/perfetto/discussions/4783) 添加的，因此仅适用于搭载了该日期或之后 Perfetto 构建版本的 Android 版本——具体来说，Android 16 QPR2 及更高版本。在更早的版本上，`traced` 不会读取这些路径；请使用方式 1 或方式 3。

#### 方式 3：Extension Server（UI 端）

如果你为团队运行共享的 [Extension Server](/docs/visualization/extension-servers.md)，请将你的描述符添加到其中。Perfetto UI 在启动时从服务器获取描述符，并在打开任何 trace 时使用它们——无需逐 trace 嵌入。当生产者无法修改时（例如来自旧版本的录制），这很方便。

### 在 SQL 中查询扩展字段

Trace Processor 可以解码的每个扩展字段都暴露在 [`args`](/docs/analysis/sql-tables.autogen#args) 表中，以扩展字段名为键。读取值最简单的方法是使用 `EXTRACT_ARG` 内置函数，它接受一个 `arg_set_id` 和一个键，并返回匹配的值。键对嵌套消息使用点表示法，对重复字段使用 `[N]` 索引：

```sql
SELECT
  slice.name,
  EXTRACT_ARG(slice.arg_set_id, 'request_id') AS request_id,
  EXTRACT_ARG(slice.arg_set_id, 'request_metadata.endpoint') AS endpoint,
  EXTRACT_ARG(slice.arg_set_id, 'retry_latencies_ms[0]') AS first_retry_ms
FROM slice
WHERE EXTRACT_ARG(slice.arg_set_id, 'request_id') IS NOT NULL;
```

如果你需要遍历重复字段的所有元素，可以直接与 `args` 表 Join 并按键前缀过滤。

对于交互式探索，Perfetto UI 的详情面板也会在选定的 Slice 上显示扩展字段。

### 限制

- 扩展目前仅由 Trace Processor 为 `TrackEvent` 解析。扩展其他消息可以用于写入，但不能用于自动 args 表解码。
- C++ SDK 的 Protozero 代码生成要求扩展位于包装消息内。非 SDK 生产者技术上可以将 `extend` 块放在文件作用域，但建议使用包装惯例以确保可移植性。

## 使用 C++ SDK 发出事件

[Tracing SDK](/docs/instrumentation/tracing-sdk.md) 支持两种扩展发送风格。

### 类型化字段访问

将你的包装消息作为模板参数传递给 `ctx.event<...>()`，以获取扩展字段的 setter 以及所有内置的 `TrackEvent` 字段：

```cpp
#include "acme_extension.pbzero.h"  // 从你的 .proto 生成。

TRACE_EVENT("my_cat", "HandleRequest", [&](perfetto::EventContext ctx) {
  auto* event = ctx.event<perfetto::protos::pbzero::AcmeExtension>();
  event->set_request_id("req-42");
  event->add_retry_latencies_ms(12);
  event->add_retry_latencies_ms(34);
  event->set_request_metadata()->set_endpoint("/api/v1/search");
});
```

### 内联字段访问

对于简单的情况，将字段元数据和值作为额外参数直接传递给 `TRACE_EVENT`：

```cpp
TRACE_EVENT(
    "my_cat", "HandleRequest",
    perfetto::protos::pbzero::AcmeExtension::kRequestId, "req-42",
    perfetto::protos::pbzero::AcmeExtension::kRetryLatenciesMs,
        std::vector<int>{12, 34});
```

## 不使用 SDK 发出事件

如果你手动编写 Perfetto protobuf——例如从 Python、Java 或任何其他语言，同时[将任意数据转换为 Perfetto](/docs/getting-started/converting.md)——扩展的工作方式相同：使用你语言的 protobuf 库在 `TrackEvent` 消息上设置扩展字段，然后按照[使扩展对 Trace Processor 可见](#making-extensions-visible-to-trace-processor-and-the-ui)中所述传递描述符集。

有关完整的 Python 演练——定义 `.proto` 文件、编译描述符、使用线路格式拼接发送事件、在 trace 中嵌入描述符集以及查询结果——请参阅程序化 Trace 生成高级指南中的[使用 Proto 扩展附加自定义类型化字段](/docs/reference/synthetic-track-event.md#proto-extensions)。
