# Trace 合并的工作原理

Trace Processor 可以同时打开多个 trace 文件并将其合并到一条
时间线上：来自不同设备的 trace、来自同一设备上不同进程的 trace，
或完全不同格式的 trace。本页面解释合并背后的模型：来自独立
文件的事件如何获得可比的时间戳，以及数据如何保持归属于其来源
机器。

这是原理层面的解释。面向任务的指南参见
[在 Perfetto UI 中合并 trace](/docs/visualization/merging-traces.md)
和[使用 Trace Processor 合并 trace](/docs/analysis/merging-traces.md)。

## 问题

两个同时录制的 trace 文件通常不共享同一时基。每个文件的时间戳
是某个时钟的读数：一台手机上的 `BOOTTIME`、Chrome 渲染器内部的
`MONOTONIC`，或者像 Chrome JSON 这样根本没有绝对时钟的格式。
不同机器上的时钟各自漂移，即使在同一台机器上，不同的时钟域
（例如 `BOOTTIME` vs `REALTIME`）也运行在不同的起点。

简单拼接文件会将无关的时间戳放在同一条轴上。合并则需要为
每个事件回答：这个时间戳是从哪个时钟读取的，该时钟与合并后
trace 用作时间线的那个时钟（"trace time"）之间有什么关系？

## 时钟的范围限定到机器和文件

在单个 trace 内，Perfetto 已经建模了多个时钟域并使用
`ClockSnapshot` 数据包在它们之间转换
（参见[时钟同步](/docs/concepts/clock-sync.md)）。合并将同一
模型扩展到跨文件和跨机器：每个时钟不仅由其域标识，还由它属于
哪台机器以及（在需要时）它是在哪个文件中被读取的来标识。
手机上的 `BOOTTIME` 和手表上的 `BOOTTIME` 是不同的时钟；
两个无时钟 JSON 文件的私有时间线也是不同的。

所有这些时钟都位于一个全局时钟图中。节点是时钟；边是两个时钟
之间已知的对应关系，每条表明"当时钟 A 读数为 X 时，时钟 B 读数
为 Y"。边来自三个来源：

- trace 内部的 `ClockSnapshot` 数据包。
- 录制时执行的时钟同步，例如
  [多机录制](/docs/deployment/multi-machine-architecture.md)
  中使用的 ping 协议。
- [trace manifest](/docs/reference/perfetto-manifest.md) 中的条目，
  允许用户声明 trace 中不包含的对应关系（可选带固定偏移量）。

为转换时间戳，Trace Processor 在图中找到从源时钟到 trace-time
时钟的一条路径，并依次应用沿途的每条边。无论来源如何，每条边
都记录在 `clock_snapshot` 表中，因此用于转换的图是可通过 SQL
完全检查的。

## 放置不共享时钟的文件

当文件的时钟有一条到 trace time 的 snapshot 路径时，使用该路径
且无需更多操作。否则 Trace Processor 按以下优先级顺序回退：

1. **REALTIME 交汇点。**假设 `REALTIME`（墙上时钟时间）在每台
   机器上读数值相同，因为实际上机器通过 NTP 同步它。如果文件的
   机器和 trace-time 机器都与 `REALTIME` 相关，则文件通过它来
   放置。这就是两个独立录制的手机 trace 在其真实的墙上时钟位置
   对齐的方式。
2. **同域假设。**不同机器或文件上同一域的两个时钟（例如两个
   `BOOTTIME`）仅在无更好选项时以零偏移关联；同样，文件的私有
   按文件时钟也可以固定在零偏移。这是一个猜测，适用于来自同台
   机器同次启动的文件。
3. **丢弃。**两个不同的真实时钟域（比如说这里的 `BOOTTIME` 和
   那里的 `REALTIME`）永远不会被盲目等同。无法关联到 trace time
   的时钟，其事件会被丢弃并记录在 trace 的错误统计中
   （参见[检查结果](/docs/analysis/merging-traces.md#checking)）。
   修复方法是录制 clock snapshot，或在 manifest 中声明该关系。

NOTE: `REALTIME` 交汇点的精度仅取决于机器的墙上时钟精度。
如果 NTP 尚未同步它们，trace 将偏移相应的差值；已知偏差可以
通过 manifest 的 `offset_ns` 修正。

## Trace time 和时间范围

一个时钟成为合并后 trace 的时间线。第一个声明 trace-time 时钟的
文件胜出；由于 manifest 总是最先被处理，其 `trace_time` 字段优先
于 trace 自身声明的任何内容。

合并后 trace 的时间范围是每个（机器，文件）对的录制窗口的并集。
因此间隔几分钟录制的两个 trace 会合并成一条较长的时间线，
两端各有活动簇："合并"将文件放在它们的真实相对时间上，而不是
覆盖它们。

转换到 trace time 开始之前的时间戳无法表示并被丢弃，同样记录在
trace 的错误统计中。在合并的 trace 中，最常见的原因是 manifest
的 `offset_ns` 将文件移得太远。

## 机器

合并后的数据保持归属于其来源机器。一个机器是 `machine` 表中的
一行（是 `process` 和 `thread` 的父级）；合并从多个来源填充它：

- **trace 中嵌入的 ID。**带有机器 ID 的数据包（通过
  traced_relay，或配置了 `TracingInitArgs::machine_id` 的 SDK
  producer）将其携带在 `TracePacket.machine_id` 中，每个不同的
  ID 成为一台机器。数据完全来自同一台机器的 trace 会被"领养"
  到主机行上，因此单机 trace 恰好有一台机器，而非空主机加一台
  远程机器。
- **Manifest 声明。**manifest 可以将整个文件归因到一台命名机器，
  或重命名多机文件中嵌入的 ID。命名机器获得以 2^32 开始的合成
  `raw_id` 值，超出 32 位嵌入 ID 空间；多个文件使用相同名称即
  表示一台共享机器。
- **`SystemInfo.machine_name`。**producer 可以在其 `SystemInfo`
  数据包中设置人类可读名称，该名称填充 `machine.name` 列。
  没有任何内容会自动设置此项；没有它（或 manifest 名称），
  UI 会回退到数字标签，如 "machine 2"。

NOTE: `machine.id`（表行 ID）在 Perfetto 版本之间不稳定。在查询
中使用 `machine.raw_id` 或 `machine.name` 来标识机器。

## 与实时多机录制的关系

合并是获得跨多机 trace 的三种方式之一；另外两种发生在录制时
（将 producer 中继到单个 `traced`，或为 SDK producer 预标记机器
ID）。这三种方法以及如何选择它们，在
[多机录制](/docs/learning-more/multi-machine-tracing.md) 中有介绍。
它们都产生上述相同的模型，事后合并也可以组合它们的输出，
例如合并来自不同主机的两个 relay 录制的 trace。

## 限制

- 本身包含多个 trace 的归档文件不能嵌套在另一个合并中：不支持
  递归同步。直接合并叶子文件。
- 将合并后的多机 trace 导出为传统 JSON 仅会导出主机的第一个
  trace。
- UI 将合并输入构建为内存中的 TAR，这限制了单个文件大小为长度
  以 12 个八进制数字编码的范围（约 8 GB），成员名称限制为 99 个
  字符。

## 后续步骤

- [Trace manifest 格式](/docs/reference/perfetto-manifest.md)：
  手动合并配置的完整参考。
- [使用 Trace Processor 合并 trace](/docs/analysis/merging-traces.md)：
  构建合并归档文件并查询结果。
- [时钟同步](/docs/concepts/clock-sync.md)：此构建所基于的
  单 trace 时钟模型。
