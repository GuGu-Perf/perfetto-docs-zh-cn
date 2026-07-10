# Trace manifest 格式

Trace manifest（`perfetto_manifest`）是一个放置在 trace 归档
（ZIP 或 TAR）中的 JSON 文件，用于控制
[Trace Processor](/docs/analysis/trace-processor.md) 和 Perfetto UI
如何解读归档中的其他文件。它是一个通用机制；目前定义的字段用于配置
多个 trace 文件如何合并到一条时间线上（每个文件属于哪台机器、它们的
时钟如何关联、合并后的 trace 使用哪个时钟作为其时间线），以及附加
标注归档的[属性](#attributes)。

本页面是该格式的规范性参考。关于面向任务的合并指南，参见
[使用 Trace Processor 合并 trace](/docs/analysis/merging-traces.md)；
关于底层模型，参见
[Trace 合并的工作原理](/docs/concepts/merging-traces.md)。

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
      {"path": "watch.pftrace", "machine": {"name": "watch"},
       "clocks": {
         "BOOTTIME": {
           "sync_to": {"file": "phone.pftrace"},
           "offset_ns": 5000000000
         }
       }}
    ]
  }
}
```

## 顶层字段

| 字段 | 类型 | 必需 | 默认值 | 含义 |
|------|------|------|--------|------|
| `version` | integer | 是 | — | 必须是 `1`。 |
| `trace_time` | object | 否 | 自动检测 | 合并后 trace 使用哪个时钟作为其时间线。 |
| `files` | array | 否 | `[]` | 每个 trace 文件的一个条目。 |
| `attributes` | object | 否 | `{}` | 附加到归档的自由格式元数据。 |

### `trace_time`

如果设置，必须是带有以下字段的对象：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `machine` | string | 否 | 提供此时钟的 `files` 条目中的 `machine.name`。如果是默认机器则省略。 |
| `clock` | string | 是 | 时钟域名称（`BOOTTIME`、`REALTIME` 等，或自定义名称）。 |

如果未设置，Trace Processor 会自动选择一个：来自第一个文件的时钟
（因为 manifest 先被处理，第一个文件即 `files[0]`，但 trace 文件之间
的大致顺序也是稳定的）。

### `files`

`files` 数组中的每个条目描述一个 trace 文件：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `path` | string | 是 | 文件在归档内的路径（如同 `tar tf` 或 `unzip -l` 所示）。 |
| `machine` | object | 否 | 将整个 trace 归因到一台命名机器。 |
| `machines` | object | 否 | 用于多机 trace：将嵌入的机器 ID 映射到名称。与 `machine` 互斥。 |
| `clocks` | object | 否 | 将文件中的时钟与 trace time 关联。 |
| `clock_overrides` | object | 否 | 覆盖 trace 声明的时钟；用于修复或增强时钟不精确的 trace。 |

`machine` 对象：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `name` | string | 是 | 人类可读的机器名称（出现在 UI 的 track 标签中）。 |

`machines` 是一个从嵌入机器 ID（字符串化的整数，0 到 4294967295）
到 `{"name": "..."}` 的映射。

`clocks` 从时钟域名称（`BOOTTIME`、`REALTIME`、`MONOTONIC` 或任何
自定义名称）映射到关联对象：

| 字段 | 类型 | 必需 | 默认值 | 含义 |
|------|------|------|--------|------|
| `sync_to` | object | 否 | 自动推断 | 哪个（文件，可选机器，时钟）作为该时钟的参照。 |
| `offset_ns` | integer | 否 | `0` | 固定的纳秒偏移量（正值 = 该时钟领先于参照）。 |
| `machine` | string | 否 | — | 当时钟来自多机 trace 中的特定机器时使用。 |

`sync_to` 对象：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `file` | string | 是 | 在 `files` 中声明的 trace 路径。 |
| `machine` | string | 否 | 该文件的 `machines` 条目中的机器。如果省略则取该文件的默认机器。 |
| `clock` | string | 否 | 该机器上的时钟域。省略时与源时钟域相同。 |

`clock_overrides` 从时钟域名称映射到覆盖对象：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `snapshots` | array | 是 | 固定一个时钟将其锁定为单一周期性快照序列，或替换其 snapshots。 |

每个 `snapshots` 条目：

| 字段 | 类型 | 必需 | 含义 |
|------|------|------|------|
| `timestamp_ns` | integer | 是 | 该快照的原始时间戳（即该时钟当时的读数）。 |
| `trace_time_ns` | integer | 是 | 对应的 trace time（当时钟为该值时，trace time 的读数）。 |
| `clock_value` | integer | 是 | trace time 时钟的值。 |

### `attributes`

任意字符串到字符串或整数的映射，用作标注。所有值必须是字符串或整数
（布尔值请使用 `"true"` / `"false"` 或 `1` / `0`）；键必须是非空
字符串。

存储在归档的 `metadata` 表中，`name` 为 `perfetto_manifest.attributes`
（作为 JSON 字符串），因此可以像查询任何其他元数据键一样按 `trace_id` 查询。

## 错误参考

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

- [使用 Trace Processor 合并 trace](/docs/analysis/merging-traces.md)：
  构建和查询合并归档。
- [在 Perfetto UI 中合并 trace](/docs/visualization/merging-traces.md)：
  交互式合并对话框，为你生成此格式。
- [Trace 合并的工作原理](/docs/concepts/merging-traces.md)：
  机器、时钟图和自动放置规则。
