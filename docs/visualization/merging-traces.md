# 在 Perfetto UI 中合并 trace

Perfetto UI 可以同时打开多个 trace 文件并将其合并到一条
共享的时间线上：来自两个设备的 trace、应用 trace 与系统 trace、
或同场景的多次采集。合并对话框分析每个文件，让你配置它们如何
对齐以及每个文件属于哪台机器，并在打开前发出警告，如果某些事件
无法放在共享时间线上的话。

关于在脚本或 CI 中合并，参见
[使用 Trace Processor 合并 trace](/docs/analysis/merging-traces.md)。
关于底层模型，参见
[Trace 合并的工作原理](/docs/concepts/merging-traces.md)。

## 何时使用

对同时采集且应归属同一条时间线的 trace，使用"同时"合并。
典型场景：

- 同场景下录制的两个设备（手机和手表、两台手机、主机和 DUT）。
- 来自同一设备的应用 trace（例如 Chrome JSON）与系统 trace。
- 来自同一集群机器的多个独立采集的 trace。

对比不同时间点的运行（回归前/后）是另一回事；对话框的
"Trace Comparison" 选项卡尚未实现，并链接到跟踪的
[GitHub issue](https://github.com/google/perfetto/issues/2780)。

## 打开多个 trace

三种等效入口：

- 点击侧边栏中的 **Open multiple trace files**（位于 "Open trace
  file" 下方）并多选文件。
- 点击 **Open trace file** 并在选择器中多选。
- 从文件管理器拖放多个文件到 UI 上。

任意一种方式都会打开 **Open Multiple Traces** 对话框：

![合并对话框，包含两个已分析的 trace](/docs/images/merging-traces-dialog.png)

每个文件在后台被分析（其格式、时钟和机器使用一次性的浏览器内
Trace Processor 实例进行检测），并显示一张卡片，展示其大小和
格式。使用 **Add more traces** 扩大文件集，或使用垃圾桶图标
移除文件。

## 配置合并

对话框仅在存在真正选择时才显示控件；一组可自行对齐的 trace
只显示绿色状态和 **Open Traces** 按钮。

### Align to：共享时间线

**Align to:** 行选择其他所有内容对齐的参照：

- 对于携带真实时钟的 trace，这是一个时钟选择：**Automatic
  (recommended)** 让 Perfetto 自动选择；选择特定时钟（例如
  `REALTIME`）则将每个 trace 投影到该时钟上。
- 对于无时钟 trace 的集合（例如多个 JSON 文件），这是一个
  基线 trace：选中的文件保留自己的时间戳（"Baseline. Others
  align to this."），其余文件相对它来定位。

### 按文件对齐

携带自身 clock snapshot 的 trace 会自动放置并在卡片上显示。
对于其余文件，**Align:** 下拉菜单提供：

- **automatically**：使用其时钟对齐 trace。
- **by a fixed offset**：输入相对于基线 trace 的纳秒偏移量。
  正值使 trace 向后移动。

### 机器

**Machine:** 下拉框将文件归属到一台设备。保留 **Default** 将
trace 合并到共享时间线上与主机数据并列，或使用 **+ Add
machine...** 创建命名机器（例如 "server"），使合并后的 trace
将该设备的 CPU、进程和线程保持独立分组。为多个文件选择同一台
机器可将它们全部放在该设备上。

![将 trace 分配到命名机器](/docs/images/merging-traces-machines.png)

本身是多机 trace 的文件（通过
[traced_relay](/docs/learning-more/multi-machine-tracing.md) 录制）
则显示 **Machines (N):** 表格，用于命名每个嵌入的机器 ID；
名称在所有 ID 都命名后生效。

## 状态面板

在配置过程中，对话框会重新运行一次试运行合并（在浏览器中，
带防抖），并报告结果：

- 绿色："All traces line up on the shared timeline."
- 警告："N events would be dropped: they cannot be placed on the shared
  timeline, either because their trace shares no clock with it or because an
  offset moves them before its start. Adjust the alignment, or check the
  manifest."

![一个会丢弃事件的固定偏移量](/docs/images/merging-traces-dropped-warning.png)

阻塞性错误（重复文件名、分析失败的文件、非整数偏移量）会禁用
**Open Traces** 按钮，直到修复为止。两个同名文件无法合并；
先在磁盘上重命名其中一个。

## 打开并查看结果

**Open Traces** 加载合并后的 trace。来自命名机器的 Track 会
携带机器名作为后缀，例如 `quote_service 4321 (server)`；
来自默认机器的 Track 则不带后缀。下图中，手机应用的
`RPC: GetQuote` slice 与后端在不同机器上录制的
`HandleGetQuote` 工作对齐在一条时间线上：

![合并后的 trace：手机应用和后端服务器在同一条时间线上](/docs/images/merging-traces-merged-timeline.png)

时间线覆盖所有 trace 录制窗口的并集，因此间隔几分钟录制
的两个 trace 会合理地产出一条较长的时间线，两端各有活动簇。

Trace Info 页面（侧边栏中的 info 图标）按输入 trace 和机器
分别显示统计信息、导入错误和数据丢失。

## 在 UI 之外复用合并

该对话框专为一次性、交互式合并而设计。如果你正在构建一个
每次运行生成多个 trace 的工具或系统（性能测试框架同时跟踪
客户端和服务器、多设备测试平台），你可能不希望用户每次采集
都重新配置此对话框。相反，让工具将其 trace 和
[trace manifest](/docs/reference/perfetto-manifest.md) 打包成
一个归档文件：该归档文件可直接在 UI 或 `trace_processor` 中
打开，合并已预先配置好。

对话框的页脚有助于快速启动：

- **Copy manifest** 将当前合并配置复制为 manifest JSON。
  将其视为模板：文件名、偏移量和机器名通常因每次采集而异，
  因此你的工具通常需要按每次运行以编程方式生成 manifest，
  并与 trace 文件一起打包成 tar/zip，而不是原样使用复制的 JSON。
- **Download .tar** 下载一个独立的归档文件（trace 加 manifest），
  可在任何地方重现这次合并后的 trace：
  `trace_processor merged-trace.tar`，或之后在 UI 中重新打开。

## 后续步骤

- [使用 Trace Processor 合并 trace](/docs/analysis/merging-traces.md)：
  从命令行、脚本和 CI 进行相同的合并。
- [Trace manifest 格式](/docs/reference/perfetto-manifest.md)：
  "Copy manifest" 产生的内容，逐字段说明。
- [Trace 合并的工作原理](/docs/concepts/merging-traces.md)：
  对话框背后的时钟、机器和放置规则。
