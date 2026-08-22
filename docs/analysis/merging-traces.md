# 从命令行合并 trace

Trace Processor 可以将多个 trace 文件作为一个合并后的 trace 导入：
来自每个文件的事件最终放在同一条时间线上，其进程、线程和 CPU
保持归属于它们来源的机器。本页面展示如何从命令行以及在脚本化或
CI 环境中执行此操作。关于交互式等效操作，参见
[在 UI 中合并 trace](/docs/visualization/merging-traces.md)；
关于合并的实际工作原理，参见
[Trace 合并](/docs/concepts/merging-traces.md)。

## 模型：一个归档进，一个 trace 出

`trace_processor` 接受单个 trace 文件参数。要合并，传入一个包含待合并
文件的归档（ZIP 或 TAR）。`util merge` 子命令构建此类归档：

```bash
trace_processor util merge -o merged.tar trace_a.pftrace trace_b.pftrace
trace_processor merged.tar
```

归档是普通 TAR，因此 `tar cf merged.tar trace_a.pftrace ...`（或任何
ZIP 工具）也可以；`util merge` 只是一个便捷辅助工具，说明见
[下文](#merge-util)。

接受普通 trace 的一切都接受此类归档：交互式 shell、`-q` 批量查询、
提供 UI 的 [httpd 模式](/docs/analysis/trace-processor.md#subcommands)，
以及 [C++](/docs/analysis/trace-processor.md#embedding) 和
[Python](/docs/analysis/trace-processor-python.md) API，
它们像处理任何其他 trace 一样流式处理归档字节。

文件在时间线上如何对齐由时钟决定。三种配置覆盖了大多数情况，
按所需配置量递增排序。

## {#no-config} 无需配置的合并

当 Trace Processor 已经可以关联文件的时钟时，无需额外配置：

- **来自同一设备的 trace。**在同一次启动期间录制的文件共享时钟域
  （例如 `BOOTTIME`），带有 `ClockSnapshot` 数据包的文件则显式关联
  其时钟域。
- **来自不同设备且带墙上时钟同步的 trace。**假设每台机器上
  `REALTIME` 的值相同（实践中：NTP），因此同时录制的两个手机 trace
  会自动在其真实的墙上时钟位置对齐。
- **预标记机器 ID 的 trace。**用机器 ID 初始化的 SDK producer 会标记
  其写入的每个数据包，因此合并的文件无需 manifest 即可将其数据保持
  在独立的机器上：

  ```c++
  perfetto::TracingInitArgs args;
  args.backends = perfetto::kInProcessBackend;
  args.machine_id = 42;  // 非零，每台机器唯一。
  perfetto::Tracing::Initialize(args);
  ```

  C SDK 等效代码为 `PerfettoProducerBackendInitArgsSetMachineId()`。
  producer 还可以额外设置 `SystemInfo.machine_name`，为合并后的 trace
  中的机器提供人类可读名称。

如果共享时钟域和 `REALTIME` 都无法定位文件，其事件将被丢弃而非猜测
（参见下文[检查结果](#checking)）；这时你需要使用 manifest。

## {#manifest} 使用 trace manifest 合并

[trace manifest](/docs/reference/perfetto-manifest.md)
（`perfetto_manifest`）是添加到归档中的 JSON 文件，用于控制
Trace Processor 如何解读其中的文件；对于合并，它可以命名机器、
重新映射嵌入的机器 ID 以及手动关联时钟。无论 manifest 在归档中的
什么位置，Trace Processor 总是在处理 trace 文件之前先处理它。

Manifest 使合并可自动化。如果你正在构建一个每次运行生成多个 trace
的工具（性能测试框架同时跟踪客户端和服务器、每设备录制一个 trace
的测试平台），你的工具知道其 trace 如何关联；将这些信息写入 manifest
并打包成一个归档。该归档随即成为一个独立的、自我描述的结构：
你的用户在 UI 或 `trace_processor` 中打开它，每次都获得正确合并的
视图，无需每次采集时进行配置。

你的工具如何构建归档并不重要：它是普通的 TAR 或 ZIP，因此任何
tar/zip 库都可以。下文中的 [`util merge` 辅助工具](#merge-util)仅是
从命令行完成相同操作的便捷方式，并在其上附加了一些验证。

### 保持两个设备的数据独立

默认情况下，两个看似来自同一设备的 trace 会合并到一台机器上。命名
机器可使每个文件的进程、线程和 CPU 保持独立分组：

```json
{
  "perfetto_manifest": {
    "version": 1,
    "files": [
      {"path": "device_a.pftrace", "machine": {"name": "device-a"}},
      {"path": "device_b.pftrace", "machine": {"name": "device-b"}}
    ]
  }
}
```

```bash
trace_processor util merge -o merged.tar --manifest manifest.json \
    device_a.pftrace device_b.pftrace
trace_processor merged.tar
```

被赋予相同机器名称的文件共享同一台机器；不同的名称则创建不同的
`machine` 表行。

### 将无时钟的 trace 对齐到系统 trace

没有绝对时钟的格式（Chrome JSON、Gecko、Instruments）无法自行与系统
trace 对齐。`clocks` 条目可将该文件固定（pin）到另一个文件的时钟上，
还可以指定固定偏移量：

```json
{
  "perfetto_manifest": {
    "version": 1,
    "trace_time": {"clock": "BOOTTIME"},
    "files": [
      {"path": "system_trace.pftrace"},
      {
        "path": "app_trace.json",
        "clocks": {
          "sync_to": {"file": "system_trace.pftrace", "clock": "BOOTTIME"},
          "offset_ns": 100000000
        }
      }
    ]
  }
}
```

`offset_ns` 的含义是：在同一时刻，当参照时钟读数为 T + `offset_ns` 时，
源文件的时钟读数为 T，因此正值会使该文件在时间线上出现得更晚。注意
`sync_to.file` 本身必须也作为条目出现在 `files` 中。

### 重命名多机 trace 中的机器

通过 [traced_relay](/docs/learning-more/multi-machine-tracing.md) 录制的
trace 已经包含多台机器，以数字 ID 标识。`machines` 可以为它们赋予可读
名称（必须列出每个嵌入 ID）：

```json
{
  "perfetto_manifest": {
    "version": 1,
    "files": [
      {"path": "relay_capture.pftrace", "machines": [
        {"id": 0, "name": "host"},
        {"id": 1234, "name": "vm"}
      ]}
    ]
  }
}
```

完整语法、默认值和错误目录见
[trace manifest 参考](/docs/reference/perfetto-manifest.md)。

TIP: Perfetto UI 的 "Open multiple trace files" 对话框可交互式生成
此格式：在那里配置合并，然后使用 "Copy manifest" 或 "Download .tar"
来启动脚本化设置。

### {#merge-util} 使用 util merge 打包

`util merge` 是可选的：由于归档是普通 TAR（或 ZIP），你完全可以自己
tar/zip trace 文件和 manifest。该辅助工具负责归档布局（成员命名，
并将通过 `--manifest` 传入的文件以 `perfetto_manifest.json` 命名包含），
并对结果运行健全性检查，如果归档无法干净合并则发出警告。
`--strict` 将警告转为失败的退出码，适用于 CI；`--no-validate` 跳过检查。

## {#checking} 检查结果

合并后的 trace 会暴露合并过程中发生的情况：

```sql
-- 合并后 trace 中的机器及其各有多少数据。
SELECT
  m.name,
  m.raw_id,
  (SELECT COUNT(*) FROM thread t WHERE t.machine_id = m.id) AS threads
FROM machine m;

-- 输入文件及其处理顺序。
SELECT name, trace_type, size FROM trace_file;

-- 合并期间被丢弃或错位的任何内容。空结果意味着
-- 每个事件都成功放置在时间线上。
SELECT name, value, machine_id, trace_id
FROM stats
WHERE severity = 'error' AND value > 0;
```

合并需注意的统计项：`clock_sync_unrelatable_clock_domains` 和
`clock_sync_failure_no_path` 统计时钟无法关联到时间线的事件数量
（录制 clock snapshot 或添加 manifest `clocks` 条目）；
`trace_sorter_negative_timestamp_dropped` 统计被 `offset_ns`
移动到时间线开始之前的事件数量。

按文件元数据可通过 `metadata` 表的 `trace_id` 列获取，或者更高层
通过 `traceinfo.trace` stdlib 模块中的 `_metadata_by_trace` 视图。

## 互操作说明

- **Android bugreport**：`bugreport.zip` 文件已经以归档形式打开；
  Trace Processor 提取并合并其中的 trace。
- **trace_processor bundle**：由 [`trace_processor bundle`](/docs/learning-more/symbolization.md)
  生成的 TAR（trace 加符号文件）是相同的归档机制。
- **Python `BatchTraceProcessor`** 不合并：它将 N 个 trace 加载到 N 个
  独立实例中以进行并行查询。要合并，将单个归档传递给一个
  `TraceProcessor` 实例。
- 包含归档的归档不能递归合并；直接合并叶子文件。
- **隐藏文件被忽略**：任何名称中包含以 `.` 开头的路径组件的归档条目
  会被跳过，永远不会被解析为 trace。这涵盖了归档工具自动添加的元数据，
  尤其是 macOS `tar` 和 Finder 创建的 ZIP 中散落在真实文件旁边的
  AppleDouble 资源派生文件（`._foo`）和 `.DS_Store` 条目。因此，在
  macOS 上构建的 `.tar`/`.zip` 可以正常加载，不会出现虚假的
  "unknown trace type" 错误。如果你有意要让一个点前缀文件被解析，
  请重命名它使所有路径组件都不以 `.` 开头。

## 后续步骤

- [Trace manifest 格式](/docs/reference/perfetto-manifest.md)：
  manifest 的规范性参考。
- [Trace 合并](/docs/concepts/merging-traces.md)：
  时钟图、放置规则和机器模型。
- [多机录制](/docs/learning-more/multi-machine-tracing.md)：
  实时从多台机器录制单个 trace，而非事后合并。
