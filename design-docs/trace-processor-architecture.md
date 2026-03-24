# Trace Processor 架构

本文档解释了 Perfetto 的 trace processor 的工作原理，从摄取原始 trace 文件到提供可查询的 SQL 数据。它涵盖了使 trace processor 能够处理各种格式（Proto、JSON、Systrace 等）的 traces 并将它们转换为统一的 profile 数据库的关键组件、数据流和架构模式。

## 概述

Trace processor 是一个摄取各种格式的 trace 文件、解析其内容、按时间戳对事件进行排序并将数据存储在列式 SQL 数据库中进行 profile 的系统。它以块为单位处理 traces，以高效处理大文件。

## 核心数据管道

```
原始 Trace → ForwardingTraceParser → 格式特定的 ChunkedTraceReader →
TraceSorter → TraceStorage → SQL 查询引擎
```

## 格式检测和委托

**ForwardingTraceParser** (`src/trace_processor/forwarding_trace_parser.cc:95-134`)
- 使用来自第一个字节的 `GuessTraceType()` 检测 trace 格式
- 通过 **TraceReaderRegistry**（`src/trace_processor/trace_reader_registry.h`）创建适当的阅读器
- 所有阅读器实现 **ChunkedTraceReader** 接口(`src/trace_processor/importers/common/chunked_trace_reader.h`)

**格式注册** (`src/trace_processor/trace_processor_impl.cc:475-519`)
```cpp
context()->reader_registry->RegisterTraceReader<JsonTraceTokenizer>(kJsonTraceType);
context()->reader_registry->RegisterTraceReader<ProtoTraceReader>(kProtoTraceType);
context()->reader_registry->RegisterTraceReader<SystraceTraceParser>(kSystraceTraceType);
```

## 格式特定的阅读器(不同的方法)

### 1. JSON Traces
**JsonTraceTokenizer** (`src/trace_processor/importers/json/json_trace_tokenizer.h:73`)
- **数据流：** 原始 JSON → Tokenizer → JsonEvent 对象 → TraceSorter::Stream<JsonEvent>
- **解析器：** JsonTraceParser 处理排序的事件 → TraceStorage
- **架构：** 带有 JSON 特定状态机的 Tokenizer/Parser 分割

### 2. Proto Traces(复杂的模块化系统)
**ProtoTraceReader** (`src/trace_processor/importers/proto/proto_trace_reader.h:58`)
- **数据流：** Proto 字节 → ProtoTraceTokenizer → ProtoImporterModules → TraceSorter::Stream<TracePacketData>
- **模块：** 为特定的数据包字段 ID 注册(`src/trace_processor/importers/proto/proto_importer_module.h:110`)
  - 标记化阶段：排序之前的早期处理
  - 解析阶段：排序后的详细处理
- **示例：** FtraceModule、TrackEventModule、AndroidModule(`src/trace_processor/importers/proto/` 中的许多文件)

### 3. Systrace(基于行的处理)
**SystraceTraceParser** (`src/trace_processor/importers/systrace/systrace_trace_parser.h:34`)
- **数据流：** 文本行 → SystraceLineTokenizer → SystraceLine 对象 → TraceSorter::Stream<SystraceLine>
- **架构：** 用于 HTML + trace 数据部分的状态机

### 4. 其他格式
- **Perf:** `perf_importer::PerfDataTokenizer`(二进制 perf.data 格式)
- **Gecko:** `gecko_importer::GeckoTraceTokenizer`(Firefox traces)
- **Fuchsia:** `FuchsiaTraceTokenizer`(Fuchsia 内核 traces)

## 事件排序和处理

**TraceSorter** (`src/trace_processor/sorter/trace_sorter.h:43`)
- **目的：** 多流基于时间戳的合并排序
- **架构：** ftrace 的每 CPU 队列，用于流式传输的窗口排序
- **流：** 每种格式创建类型化流(JsonEvent、TracePacketData、SystraceLine 等)
- **输出：** 排序后的事件到格式特定的解析器

## 存储层

**TraceStorage** (`src/trace_processor/storage/trace_storage.h`)
- **架构：** 具有专门表类型的列式存储
- **表：** SliceTable、ProcessTable、ThreadTable、CounterTable 等
- **访问：** 由解析器直接插入，由引擎进行 SQL 查询

## 上下文和协调

**TraceProcessorContext** (`src/trace_processor/types/trace_processor_context.h`)
- **多级状态管理**：
  - 全局状态(跨机器共享)
  - 每个 trace 的状态(特定于每个 trace 文件)
  - 每机器状态(唯一于每个机器)
  - 每个 trace 和每机器状态(最特定)
- **协调：** 存储、排序器、跟踪器的中心访问点

## 关键架构模式

### 1. ChunkedTraceReader 接口
所有格式阅读器实现相同的接口，但内部架构完全不同：
- JSON：带有状态机的增量 JSON 解析
- Proto：带有基于字段的路由的模块化数据包处理
- Systrace：逐行文本处理
- 档案(ZIP/TAR)：提取并委托的容器格式

### 2. TraceSorter：：Stream<T> 模式
每种格式定义自己的事件类型并创建类型化流：
- `Stream<JsonEvent>` 用于 JSON traces
- `Stream<TracePacketData>` 用于 proto 事件
- `Stream<SystraceLine>` 用于 systrace 行

### 3. 解析器与 Tokenizer 分割
- **Tokenizer:** 排序前的处理，快速时间戳提取
- **解析器：** 排序后详细处理到存储
- 并非所有格式都使用此分割(取决于复杂性)

## 文件路径参考

**核心基础设施：**
- `src/trace_processor/forwarding_trace_parser.{h,cc}` - 格式检测和委托
- `src/trace_processor/trace_reader_registry.{h,cc}` - 阅读器注册
- `src/trace_processor/sorter/trace_sorter.h` - 事件排序
- `src/trace_processor/storage/trace_storage.h` - 列式存储

**格式阅读器**(示例):
- `src/trace_processor/importers/json/json_trace_tokenizer.h` - JSON 处理
- `src/trace_processor/importers/proto/proto_trace_reader.h` - Proto 入口点
- `src/trace_processor/importers/proto/proto_importer_module.h` - Proto 模块系统
- `src/trace_processor/importers/systrace/systrace_trace_parser.h` - Systrace 处理

**注册：**
- `src/trace_processor/trace_processor_impl.cc:475-519` - 所有阅读器注册的地方
