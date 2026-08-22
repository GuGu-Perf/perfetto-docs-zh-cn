# Trace manifest 格式

Trace manifest（`perfetto_manifest`）是一个放置在 trace 归档
（ZIP 或 TAR）中的 JSON 文件，用于控制
[Trace Processor](/docs/analysis/trace-processor.md) 和 Perfetto UI
如何解读归档中的其他文件。它是一个通用机制；目前定义的字段用于配置
多个 trace 文件如何合并到一条时间线上（每个文件属于哪台机器、它们的
时钟如何关联、合并后的 trace 使用哪个时钟作为其时间线），以及附加
标注归档的[属性](#attributes)。

本页面是该格式的规范性参考。关于面向任务的合并指南，参见
[从命令行合并 trace](/docs/analysis/merging-traces.md)；
关于底层模型，参见
[Trace 合并](/docs/concepts/merging-traces.md)。

该格式是稳定的：`version` 1 是当前（也是唯一的）版本，并将持续支持。
新功能作为 version 1 中的新字段添加；给定 Trace Processor 版本不认识
的字段会被忽略。

## 为什么需要 manifest？

[Perfetto UI 的合并对话框](/docs/visualization/merging-traces.md)可以
交互式配置合并，这对于一次性调查是正确的工具。Manifest 则用于合并
不是一次性的情况：每次运行生成多个相关 trace 的工具和系统，例如一个
同时跟踪客户端和服务器的性能测试框架、每个设备录制一个 trace 的测试
平台，或者捕获一个应用 trace 与系统 trace 并列的流水线。

这样的工具不应让每个用户为每次采集在对话框中重新构建合并配置。它知道
其 trace 如何关联；manifest 就是它将这些知识写下来的方式。工具在 trace
旁边输出 manifest 并将所有内容打包到一个归档中，该归档随即成为一个
独立的、自我描述的制品：任何人都可以在 UI 或 `trace_processor` 中打开它，
无需任何配置即可获得正确合并的视图，无论是今天还是多年以后。

交互式对话框和 manifest 是同一机制的两面：对话框在底层生成 manifest，
其 "Copy manifest" 按钮是获取起始模板的便捷方式。由于文件名、偏移量
和机器名通常因每次采集而异，工具通常按每次运行以编程方式生成 manifest，
并将其与 trace 文件一起打包到归档中。

## 示例

```json
{
  "perfetto_manifest": {
    "version": 1,
    "trace_time": {"clock": "BOOTTIME"},
    "files": [
      {"path": "phone.pftrace", "machine": {"name": "phone"}},
      {"path": "watch.pftrace", "machine": {"name": "watch"}},
      {
        "path": "app_log.json",
        "clocks": {
          "sync_to": {"file": "phone.pftrace", "clock": "BOOTTIME"},
          "offset_ns": 250000000
        }
      }
    ]
  }
}
```

## {#detection} 检测与放置

Trace Processor 按内容而非文件名检测 manifest：任何内容（忽略前导空白后）以
`{"perfetto_manifest"` 开头的文件都会被视为 manifest。按照惯例，该文件命名为
`perfetto_manifest.json`，这也是 Perfetto UI 生成 manifest 时使用的名称，
但任何名称都可以。

放置规则：

- **在 ZIP 或 TAR 归档内**：位置无关紧要。无论 manifest 出现在归档中的哪个
  位置，Trace Processor 始终在处理任何 trace 文件之前先处理 manifest。
- **在拼接流中**（例如拼接在一起的 gzip 成员）：manifest 必须放在最前面。
  在另一个 trace 文件之后遇到的 manifest 会被拒绝并报错。
- 每个合并输入中**最多一个 manifest**。出现第二个 manifest 是一个错误。
- 独立的 manifest（不在归档内）可以成功解析，但没有可配置的内容。

manifest 会在任何 trace 文件被解析之前完整应用，因此条目可以以任意顺序引用
文件，包括在归档中出现得更晚的文件。

## {#schema} 顶层字段

| 字段 | 类型 | 必需 | 默认值 | 含义 |
|------|------|------|--------|------|
| `version` | integer | 是 | — | 必须是 `1`。 |
| `trace_time` | object | 否 | 自动检测 | 合并后 trace 使用哪个时钟作为其时间线。 |
| `files` | array | 否 | `[]` | 每个 trace 文件的一个条目。 |
| `attributes` | object | 否 | `{}` | 附加到归档的自由格式元数据。 |

### {#trace-time} trace_time

如果设置，必须是带有以下字段的对象：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `machine` | string | 否 | 提供此时钟的 `files` 条目中的 `machine.name`。如果是默认机器则省略。 |
| `clock` | string | 是 | 时钟域名称（`BOOTTIME`、`REALTIME` 等，或自定义名称）。 |

如果未设置，Trace Processor 会自动选择一个：来自第一个文件的时钟
（因为 manifest 先被处理，第一个文件即 `files[0]`，但 trace 文件之间
的大致顺序也是稳定的）。

### {#files} files

`files` 数组中的每个条目都是一个对象：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `path` | string | 是 | 归档内某个文件的确切名称（对于 TAR/ZIP，即成员路径）。 |
| `machine` | object | 否 | 将整个文件归因到一台命名机器。与 `machines` 互斥。 |
| `machines` | array | 否 | 将多机 trace 中嵌入的机器 ID 重新映射为命名机器。与 `machine` 互斥。 |
| `clocks` | object | 否 | 手动将该文件的时钟与另一个文件中的时钟相关联。参见 [clocks](#clocks)。 |

### {#machine} machine

```json
{"path": "watch.pftrace", "machine": {"name": "watch"}}
```

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `name` | string（非空） | 是 | 机器的名称。 |

将文件中的每个事件归因到一台具有给定名称的机器。使用相同名称的文件（或
`machines` 条目）共享同一台机器：它们的进程、线程和 CPU 在合并后的 trace
中被分组到一起。使用不同的名称则使每个设备的数据保持独立。

`machine` 是一个对象而非裸字符串，以便将来在不更改格式的情况下添加按机器
划分的属性。

对本身包含来自多台机器数据的文件（即通过
[traced_relay](/docs/deployment/multi-machine-architecture.md) 录制的多机
proto trace）使用 `machine` 是一个错误；此类文件应使用 `machines`。

### {#machines} machines

```json
{"path": "relay.pftrace", "machines": [
  {"id": 0, "name": "host"},
  {"id": 1234, "name": "vm"}
]}
```

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `id` | [0, 4294967295] 范围内的整数 | 是 | 嵌入在 trace packet 中的机器 ID。 |
| `name` | string（非空） | 是 | 赋予该机器的名称。 |

重命名已嵌入多机 trace 中的机器。必须声明出现在 trace 中的每个嵌入 ID；
来自未声明 ID 的 packet 是一个错误。带有 `id: 0` 的条目还会成为该文件的
基础机器。名称与 `machine` 名称共享同一命名空间，因此两个文件中的相同名称
会将它们合并为一台机器。

### {#clocks} clocks

通过将该文件的某个时钟与另一个文件中的时钟相关联，手动将该文件放置到共享
时间线上。当自动规则（共享时钟域、`REALTIME` 会合）无法放置该文件时，或者
需要应用已知的固定偏移量时，使用此字段。

```json
{
  "path": "app_log.json",
  "clocks": {
    "sync_to": {"file": "phone.pftrace", "clock": "BOOTTIME"},
    "offset_ns": 250000000
  }
}
```

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `clock` | string | 否 | 要关联的本文件自身的哪个时钟，以[时钟名称](#clock-names)表示。无时钟文件可省略。 |
| `machine` | string | 否 | 当本文件是多机 trace 时，指明其哪台机器拥有源时钟。该情况下必填。 |
| `sync_to` | object | 是 | 参照时钟。见下文。 |
| `offset_ns` | integer | 否（默认 0） | 两个时钟之间的固定偏移量：在同一时刻，当参照时钟读数为 T + `offset_ns` 时，源时钟读数为 T。因此正值会使该文件在参照时间线上出现得更晚。 |

`sync_to` 的字段：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `file` | string | 是 | 参照文件。必须与 `files` 中某个条目的 `path` 匹配。 |
| `machine` | string | 否 | 当参照文件是多机 trace 时，指明其声明的哪台机器拥有参照时钟。该情况下必填。仅给出机器名（不带 `file`）会因含义不明确而被拒绝。 |
| `clock` | string | 否 | 参照时钟，以[时钟名称](#clock-names)表示。省略时，参照物是该文件自身的每文件私有时间线（适用于参照文件本身是无时钟文件的情况）。 |

省略 `clock` 的语义很重要：

- **给出 `clock`**（RELATE）：该文件继续使用自己的时钟；此覆盖只是补充了
  命名时钟与参照之间缺失的关联。内部自带时钟的 trace（Perfetto proto、
  systrace 等）使用这种方式。
- **省略 `clock`**（PIN）：该文件被视为无时钟文件。其事件被放置在自身的
  每文件私有时间线上，而此覆盖将该时间线固定到参照物上。没有绝对时钟的
  格式（Chrome JSON、Gecko、Instruments）使用这种方式。对一个随后被发现
  会发出自身 clock snapshot 的文件进行固定（pin）是一个错误。

WARNING: 手动设置的 `offset_ns` 如果将事件移到合并时间线起点之前，会导致
这些事件被丢弃，并计入 `trace_sorter_negative_timestamp_dropped` 统计。
Perfetto UI 的合并对话框在打开前会报告这种情况。

## {#attributes} attributes

用于标注归档的任意键值对：基准测试名称、运行 ID、构建 ID 等。每个条目成为
`metadata` 表中的一行 `manifest_attribute.<key>`。

其命名空间有意与 `trace_attribute.*`
（[TraceAttributes](/protos/perfetto/common/trace_attributes.proto)）
分开：后者是记录在 trace 自身中的属性，而 manifest 属性描述的是整个归档。

```json
{
  "perfetto_manifest": {
    "version": 1,
    "attributes": {"benchmark": "startup", "run_id": 42}
  }
}
```

值必须是字符串或整数；键必须非空，并建议使用命名空间前缀（例如
`myapp.build_id`）以避免不同工具之间的冲突。同一键设置两次会覆盖：
最后一个值生效。

## {#clock-names} Clock names

凡期望出现时钟名称之处，均使用以下名称之一：

`REALTIME`、`REALTIME_COARSE`、`MONOTONIC`、`MONOTONIC_COARSE`、
`MONOTONIC_RAW`、`BOOTTIME`

它们对应 [builtin_clock.proto](/protos/perfetto/common/builtin_clock.proto)
中的内建时钟，以及同名的 POSIX `clock_gettime` 时钟域。

## {#sql} 对 SQL 层面的影响

导入后，manifest 的影响在 trace 中可见：

- 每台命名机器都会在
  [`machine`](/docs/analysis/sql-tables.autogen#machine) 表中获得一行，
  其 `name` 被设置。Manifest 机器获得从 2^32 开始的合成 `raw_id` 值，
  刻意位于 trace packet 中嵌入的 32 位 ID 空间之外。
- `trace_time` 设置 `metadata` 表中的 `trace_time_clock_id` 键。
- 每个 `attributes` 条目成为 `metadata` 表中的一行 `manifest_attribute.<key>`。
- 每个 `clocks` 覆盖都记录为 `clock_snapshot` 表中的一条边，与从 trace
  本身读取的快照并存。
- 每个输入文件在 `trace_file` 表中有一行；`stats` 和 `metadata` 行带有
  `machine_id` 和 `trace_id` 列，用于标识它们描述的是哪台机器和哪个文件。

## {#errors} 错误参考

Trace Processor 在导入时验证 manifest 并为其错误发出文本描述：

| 条件 | 错误信息 |
|------|----------|
| 不存在的文件 | `unknown file: X. Did you mean: Y?` |
| 重复文件路径 | `duplicate file path: X` |
| 同名机器（不同文件） | `duplicate machine name: X` |
| 缺少 `version` | `version is required` |
| `version` 不是 `1` | `unsupported version: N。仅支持版本 1。` |
| `trace_time` 未设置 `clock` | `trace_time: clock is required` |
| `trace_time.clock` 不是字符串 | `trace_time.clock must be a string` |
| `trace_time.machine` 不是字符串 | `trace_time.machine must be a string` |
| 未知的时钟名称 | `unknown clock name: X. Use one of REALTIME, ...` |
| 一个输入中有第二个 manifest | `multiple perfetto_manifest files in archive` |
| 拼接流中 manifest 在 trace 文件之后 | `perfetto_manifest file must be the first trace file in the input` |
| 同一条目上同时有 `machine` 和 `machines` | `machine and machines are mutually exclusive` |
| `attributes` 不是对象 | `attributes must be an object of string or integer values` |
| `attributes` 值不是字符串或整数 | `attributes: 'X' must be a string or an integer` |
| 空 `attributes` 键 | `attributes: keys must be non-empty` |
| 空机器名称 | `machine: name must be non-empty` |
| `machines` ID 超出 [0, 4294967295] | `machines: id must be in [0, 4294967295]` |
| 数据包来自 `machines` 中未声明的嵌入机器 ID | `undeclared machine id N` |
| 对多机文件使用 `machine` | 在文件数据包被解析时报告 |
| `clocks` 没有 `sync_to` | `clocks: a sync_to block is required` |
| `sync_to` 没有 `file` | `clocks: sync_to.file is required` |
| `sync_to.file` 不在 `files` 中 | `sync_to.file names unknown file 'X'. It must match the path of an entry in the files array` |
| `sync_to.machine` 没有 `file` | 仅机器名是不明确的，也需命名文件 |
| 参照文件是多机的但缺少 `sync_to.machine` | `'X' is a multi-machine trace; also name the machine` |
| `sync_to.machine` 未被该文件声明 | `'X' is not a machine declared by file 'Y'` |
| 此文件是多机的但缺少 `clocks.machine` | `file 'X' is a multi-machine trace; name which machine the clock is on` |
| `offset_ns` 不是整数 / 超出 INT64_MIN | `offset_ns must be an integer` / `offset_ns is out of range` |
| 对本身为归档或 manifest 的文件使用覆盖 | 被拒绝 |
| 对发出 clock snapshot 的文件使用固定覆盖 | `clock overrides require the trace to use a single clock` |

该格式的权威定义位于读取器
[perfetto_manifest_reader.cc](/src/trace_processor/plugins/perfetto_manifest/perfetto_manifest_reader.cc)
及其测试套件
[trace_manifest/tests.py](/test/trace_processor/diff_tests/parser/trace_manifest/tests.py)。

## 后续步骤

- [从命令行合并 trace](/docs/analysis/merging-traces.md)：
  构建和查询合并归档。
- [在 UI 中合并 trace](/docs/visualization/merging-traces.md)：
  交互式合并对话框，为你生成此格式。
- [Trace 合并](/docs/concepts/merging-traces.md)：
  机器、时钟图和自动放置规则。
