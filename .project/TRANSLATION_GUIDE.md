# Perfetto 文档翻译规范

## 一、基本原则

### 1.1 准确性优先
- 忠实于原文的技术含义，不随意增删内容
- 专业术语必须准确对应，不可意译
- 保持技术逻辑和结构的完整性


### 1.2 可读性
- 符合中文表达习惯，避免"翻译腔"
- 语句通顺流畅，避免冗长句式
- 保持原文的层级结构和信息密度

### 1.3 一致性
- 同一术语在全文中保持一致翻译
- 相同概念使用统一表述方式
- 遵循 Google 技术文档翻译规范和 Perfetto 既定翻译


## 二、术语翻译规范

### 2.1 术语翻译表

| 英文 | 中文翻译 | 是否翻译 | 说明 |
|------|-----------|----------|------|
| Perfetto | 性能追踪工具 | 否 | 系统名称 |
| Trace | 追踪数据 | 否 | 性能追踪记录 |
| Tracing | 追踪过程 | 否 | 采集追踪数据的动作 |
| TracePoint | 追踪点 | 否 | 代码中的追踪标记点 |
| Trace Buffer | 追踪缓冲区 | 否 | 存储追踪数据的内存区域 |
| DataSource | 数据源 | 否 | 数据来源组件 |
| Timeline | 时间线 | 否 | 可视化时间轴 |
| Session | 会话 | 否 | 一次追踪会话 |
| Packet | 数据包 | 否 | 追踪数据包 |
| Slice | 时间片 | 否 | 时间段切片 |
| Counter | 计数器 | 否 | 数值计数器 |
| Frame | 帧 | 否 | 渲染帧 |
| Profile | 性能分析数据 | 否 | 性能分析结果 |
| Heap Profile | 堆内存分析 | 否 | 堆内存性能分析 |
| Memory Profile | 内存分析 | 否 | 内存性能分析 |
| CPU Profile | CPU 分析 | 否 | CPU 性能分析 |
| Heap Snapshot | 堆快照 | 否 | 堆内存状态快照 |
| Metric | 指标 | 否 | 性能指标 |
| Log | 日志 | 否 | 系统日志 |
| Logging | 日志记录 | 否 | 记录日志的过程 |
| Track | 轨道 | 否 | 时间轴上的轨道 |
| Slice Group | 切片组 | 否 | 时间片分组 |
| UUID | 通用唯一标识符 | 否 | 唯一标识符 |
| ProtoBuf | 协议缓冲区 | 否 | Google 序列化协议 |
| Fuchsia | Fuchsia | 否 | Google 操作系统 |
| Android | 安卓 | 否 | 移动操作系统 |
| Chrome | Chrome | 否 | Google 浏览器 |
| Linux | Linux | 否 | 开源操作系统 |
| Windows | Windows | 否 | 微软操作系统 |
| macOS | macOS | 否 | 苹果操作系统 |
| Hook | 钩子 | 否 | 代码钩子机制 |
| Cookbook | 实战指南 | 否 | 实践教程集合 |
| Fork | 分叉 | 否 | 仓库分叉操作 |
| fork | 派生 | 否 | 进程派生操作 |
| Sideload | 侧载 | 否 | 旁加载安装 |
| Plugin | 插件 | 否 | UI 扩展组件 |
| Performance | 性能 | 是 | - |
| Latency | 延迟 | 是 | - |
| Throughput | 吞吐量 | 是 | - |
| Overhead | 开销 | 是 | - |
| Benchmark | 基准测试 | 是 | - |
| Instrumentation | 插桩/埋点 | 是 | 添加追踪代码 |
| Sampling | 采样 | 是 | - |
| Allocation | 分配 | 是 | 内存分配 |
| Deallocation | 释放 | 是 | 内存释放 |
| Retention | 保留 | 是 | 内存保留 |
| Leak | 泄漏 | 是 | 内存泄漏 |
| Garbage Collection | 垃圾回收 | 是 | GC |
| Compilation | 编译 | 是 | - |
| Optimization | 优化 | 是 | - |
| Scheduler | 调度器 | 是 | - |
| System Call | 系统调用 | 是 | - |
| Interrupt | 中断 | 是 | - |
| Context Switch | 上下文切换 | 是 | - |
| Stack Trace | 堆栈跟踪 | 是 | - |
| Call Tree | 调用树 | 是 | - |
| Flame Chart | 火焰图 | 是 | - |
| Waterfall | 瀑布图 | 是 | - |
| Dashboard | 仪表盘 | 是 | - |
| Visualizer | 可视化工具 | 是 | - |
| Query | 查询 | 是 | - |
| Filter | 过滤器 | 是 | - |
| Aggregation | 聚合 | 是 | - |
| Histogram | 直方图 | 是 | - |
| Percentile | 百分位 | 是 | - |
| Mean | 平均值 | 是 | - |
| Median | 中位数 | 是 | - |
| Standard Deviation | 标准差 | 是 | - |
| Variance | 方差 | 是 | - |
| Outlier | 异常值 | 是 | - |
| Distribution | 分布 | 是 | - |
| Correlation | 相关性 | 是 | - |
| Regression | 裂化 | 是 | 性能裂化 |
| Benchmarking | 基准测试 | 是 | - |
| Latency-sensitive | 延迟敏感 | 是 | - |
| Real-time | 实时 | 是 | - |
| Near real-time | 近实时 | 是 | - |
| Offline | 离线 | 是 | - |
| Post-processing | 后处理 | 是 | - |
| Trace Summarization | Trace 汇总 | 是 | Trace 数据汇总功能 |

**重要说明**：
- "否" 表示保持英文不翻译，"是" 表示翻译为中文
- 表格中列出的是术语的基本形式，所有变种（单复数、大小写变化、组合词等）遵循同样的翻译规则
- 例如：`Track` 包括 `track`、`tracks`、`Track`、`Tracks`、`track event` 等所有变种都保持英文

**示例**：

| 原文 | 正确翻译 | 错误翻译 |
|------|---------|---------|
| track event | Track event | 轨道事件 |
| trace processor | Trace Processor | 追踪处理器 |
| Performance | 性能 | Performance |

**动词翻译说明**：
- `capture trace` / `record trace` → **采集 trace**（贴近实际工作语言）
- `to profile` → **进行 profile/profiling**（核心术语不翻译）
- 其他常用动词（start→开始, stop→停止等）按常规范翻译

---

## 三、语法和句式规范

### 5.1 换行处理

**原则：** 英文 Markdown 文档中的手动换行仅用于编辑便利，实际渲染后仍然是连贯的一句话。中文翻译应**保持渲染后的连贯效果**，而非机械模仿英文原文的换行位置。

**原文（英文）:**
```
Perfetto is a system-wide profiler that allows you
to collect and analyze performance data.
```

**渲染效果（连贯句）:**
```
Perfetto is a system-wide profiler that allows you to collect and analyze performance data.
```

**译文（中文）:**
```
Perfetto 是一个系统级性能分析工具，可用于收集和分析性能数据。
```

**说明：** 不需要模仿英文的两行格式，中文翻译为一行连贯句子即可。

---

### 5.2 句式结构

**原文：** "Perfetto is a system-wide profiler that allows you to collect and analyze performance data."

**译文：** "Perfetto 是一个系统级性能分析工具，可用于收集和分析性能数据。"

---

**原文：** "When a slice starts, it pushes the stack, and when it ends, it pops the stack."

**译文：** "当 Slice 开始时，它会压入堆栈；当结束时，它会弹出堆栈。"

### 5.3 长句拆分

**原文：** "The producer is responsible for writing data into the shared memory buffer, which is then read by the service and forwarded to the consumer."

**译文：** "Producer 负责将数据写入共享内存缓冲区，然后由 Service 读取并转发给 Consumer。"

### 5.4 被动语态转主动

**原文：** "The trace is captured by the perfetto daemon."

**译文：** "trace 由 perfetto 守护进程捕获。"

### 5.5 条件句式

**原文：** "If the buffer is full, the oldest data is discarded."

**译文：** "如果缓冲区已满，最旧的数据将被丢弃。"

### 5.6 列表项

**原文：**
```
- Create a tracing session
- Configure the data sources
- Start tracing
- Stop tracing
- Export the trace
```

**译文：**
```
- 创建 Tracing Session
- 配置 DataSource
- 开始 Tracing
- 停止 Tracing
- 导出 trace
```

### 5.7 特殊组合翻译

对于 "capture/record trace" 这类组合，使用贴近实际工作语言的翻译：

**原文：** "capture trace"
**译文：** "采集 trace"

**原文：** "record trace"
**译文：** "采集 trace"

**原文：** "start tracing"
**译文：** "开始 Tracing"

---

## 六、格式保持规范

### 6.1 格式一致性

**核心原则：** 中文 Markdown 文档的各种格式必须与英文文档完全一致，包括但不限于：

#### 6.1.1 文本格式

| 格式类型 | 英文示例 | 中文示例 |
|----------|----------|----------|
| 加粗 | `**bold text**` | `**粗体文本**` |
| 斜体 | `*italic text*` | `*斜体文本*` |
| 删除线 | `~~strikethrough~~` | `~~删除线~~` |
| 行内代码 | `` `code` `` | `` `代码` `` |
| 高亮（支持时） | `==highlighted==` | `==高亮文本==` |

**原文：**
```
Perfetto is a **system-wide** profiler with *low overhead*.
```

**译文：**
```
Perfetto 是一个 **系统级** 性能分析工具，具有 *低开销* 特性。
```

**注意:** 翻译后必须保留原文的所有加粗、斜体等格式标记。

**⚠️ 中文斜体特殊规则：**
- **保持原文的斜体符号不变**（`_` 或 `*`）
- 如果斜体标记前面有文字，需要在斜体标记**前加空格**以确保正确渲染
- 示例：
  - 原文：`_better_`（前面无文字）→ 译文：`_更好_`（保持不变）
  - 原文：`run _better_`（前面有空格）→ 译文：运行 _更好_（保持空格）
  - 原文：`text_better`（前面无空格）→ 译文：文本 _better_（斜体前加空格）
- 这是因为某些 Markdown 渲染器对 `文字_中文_` 的解析存在问题

#### 6.1.2 列表格式

- 保持原文的列表类型（有序/无序）
- 保持缩进层级一致
- 保持列表项数量一致

**原文：**
```markdown
1. First step
2. Second step
   - Sub-step 2.1
   - Sub-step 2.2
3. Third step
```

**译文：**
```markdown
1. 第一步
2. 第二步
   - 子步骤 2.1
   - 子步骤 2.2
3. 第三步
```

#### 6.1.3 标题格式

- 保持原文的标题层级（`#`、`##`、`###` 等）
- 保持标题数量和顺序
- 标题内容可翻译，但术语保持英文

**原文：**
```markdown
# Getting Started

## Recording a trace

### Configure the data sources
```

**译文：**
```markdown
# 快速入门

## 采集 trace

### 配置 DataSource
```

#### 6.1.4 引用格式

- 保持引用的层级和嵌套结构
- 保持引用标记（`>`）的数量

**原文：**
```markdown
> This is a quote.
>
> > This is a nested quote.
```

**译文：**
```markdown
> 这是一个引用。
>
> > 这是一个嵌套引用。
```

#### 6.1.5 分隔线格式

- 保持分隔线的样式（`---`、`***`）
- 保持分隔线数量和位置

**原文：**
```markdown
Section 1

---

Section 2
```

**译文：**
```markdown
第一部分

---

第二部分
```

#### 6.1.6 代码块格式

- 保持代码块的语言标记（```` ```bash ````、```` ```json ```` 等）
- 保持代码块内部的格式不变
- 代码块外的注释可以翻译

**原文：**
```bash
# Start the perfetto service
./traced &
```

**译文：**
```bash
# 启动 perfetto 服务
./traced &
```

#### 6.1.7 表格格式

- 保持表格的列数和行数
- 保持表格的对齐方式
- 表头可翻译，术语保持英文

**原文：**
```markdown
| Name | Description | Required |
|------|-------------|----------|
| id   | Unique ID   | Yes      |
| name | Display name| No       |
```

**译文：**
```markdown
| Name | Description | Required |
|------|-------------|----------|
| id   | 唯一标识符   | 是       |
| name | 显示名称    | 否       |
```

#### 6.1.8 链接格式

- 保持链接格式和 URL 不变
- 链接文本可以翻译

**原文：**
```markdown
See [the documentation](/docs/README.md) for details.
```

**译文：**
```markdown
详情请参见[文档](/docs/README.md)。
```

#### 6.1.9 图片格式

- 保持图片链接和 Alt 文本格式
- Alt 文本可以翻译

**原文：**
```markdown
![Perfetto UI screenshot](/docs/images/perfetto-ui.png)
```

**译文：**
```markdown
![Perfetto UI 截图](/docs/images/perfetto-ui.png)
```

### 6.2 格式检查清单

翻译完成后，请检查以下项目：

- [ ] 所有加粗（`**`）格式是否保留
- [ ] 所有斜体（`*`）格式是否保留
- [ ] 列表层级是否一致
- [ ] 标题层级（`#` 数量）是否正确
- [ ] 代码块语言标记是否正确
- [ ] 表格列数和行数是否一致
- [ ] 链接 URL 是否正确
- [ ] 图片链接是否正确
- [ ] 引用嵌套层级是否正确

---

## 五、标点符号规范
基本原则：翻译后的中文语句中，标点符号应该中文标点，除非是：公式、markdown 语法和本翻译规范中特殊说明的情形。
### 7.1 中英文混排

- 中英文之间加空格：`Perfetto 是一个系统级工具`
- 中文与数字之间加空格：`共 11473 个文件`
- 英文标点（如 `.` `,` `:`）在英文句子中使用
- 中文标点（如 `。` `，` `：`）在中文句子中使用

### 7.2 标题层级

- 使用 `#` `##` `###` 保持原文层级结构
- 标题中英文术语保持原文，不翻译

### 7.3 专用词汇标志（不翻译）

**⚠️ 重要说明：这是 Perfetto 文档特有的渲染约定！**

以下专用词汇标志用于编译成网页时识别为特定横幅，**不翻译**，保持原文：

- **这些标志是 Perfetto 文档站点（perfetto.dev）的特殊支持**
- 在其他 Markdown 编辑器或渲染工具中可能不会显示为带图标的提示框
- 迁移或导出文档时请注意此约定
- 标志必须在**段落开头**使用，格式为 `标志: 内容`

| 标志 | CSS 类 | 格式示例 | 图标 | 说明 |
|------|--------|----------|------|------|
| NOTE: | `note` | `NOTE: ...` | bookmark | 注意 |
| TIP: | `tip` | `TIP: ...` | star | 提示 |
| TODO: / FIXME: | `todo` | `TODO: ...` 或 `FIXME: ...` | error | 待办 |
| WARNING: | `warning` | `WARNING: ...` | warning | 警告 |
| Summary: | `summary` | `Summary: ...` | sms | 总结 |

**重要说明：**
- 这些标志会被渲染为带有特定颜色和图标的提示框
- 必须在段落开头使用，格式为：`标志: 内容`
- 标志名称必须保持英文大小写（如 `NOTE:` 而非 `note:`）
- 这些标志与 Markdown 引用块（`>`）不同，是直接在段落文本中使用

**渲染效果说明：**
- `NOTE:` - 蓝色背景，bookmark 图标
- `TIP:` - 绿色背景，star 图标
- `WARNING:` - 红色背景，warning 图标
- `Summary:` - 青色背景，sms 图标
- `TODO:` / `FIXME:` - 灰色背景，error 图标

**示例：**

原文：
```
NOTE: To record traces from Chrome on Android, follow the
[instructions for recording Android system traces](/docs/getting-started/system-tracing.md)
```

译文（保持标志不变）：
```
NOTE: 如需在 Android 上录制 Chrome 的 trace，请遵循
[录制 Android 系统 trace 的说明](/docs/getting-started/system-tracing.md)
```

原文：
```
WARNING: This operation cannot be undone and may result in data loss.
```

译文（保持标志不变）：
```
WARNING: 此操作无法撤销，可能会导致数据丢失。
```

原文：
```
TIP: Use the keyboard shortcuts to speed up your workflow.
```

译文（保持标志不变）：
```
TIP: 使用键盘快捷键可加快工作流程。
```

原文：
```
Summary: This section provides an overview of the Perfetto architecture.
```

译文（保持标志不变）：
```
Summary: 本节提供了 Perfetto 架构的概览。
```

原文：
```
TODO: Update this section when the new API is released.
```

译文（保持标志不变）：
```
TODO: 新 API 发布时更新此节。
```

### 7.4 链接和引用

- 保持原文链接格式
- `[文本](链接)` 中的文本可以翻译

---

## 六、格式详细规范

### 8.1 代码和命令

- 命令使用代码块格式
- 保持原命令不变，不翻译

```bash
perfetto -o trace.perfetto -c /data/local/tmp/config.cfg
```

### 8.2 配置文件

- 配置内容保持原样
- 注释可以翻译

```json
{
  "data_sources": [{
    "config": {
      "name": "linux.process_stats"
    }
  }]
}
```

### 8.3 表格

- 表头翻译
- 表格内容根据情况翻译，专业术语保持英文

### 8.4 路径和文件名

- 保持原路径和文件名
- 不翻译系统路径

```
/data/local/tmp/trace.perfetto
```

---

## 七、特殊处理

### 9.1 API 名称

- 保持原 API 名称
- 方法名、类名、变量名不翻译

```cpp
perfetto::TracedValue::WriteInt64(...)
```

### 9.2 命令行参数

- 保持原参数名称
- 说明文字可以翻译

```bash
-o, --output          输出文件路径
-c, --config          配置文件路径
```

### 9.3 快捷键和按键

- 保持原按键名称
- 如 `Ctrl+C` `Cmd+Enter`

### 9.4 版本号

- 保持原版本号格式
- 如 `v1.2.3` `Perfetto 35.0`

### 9.5 时间和日期

- 可以翻译为中文格式
- 如 `2026-03-19` 或 `2026年3月19日`

---

## 八、翻译流程

### 10.1 准备阶段

1. 通读原文，理解整体结构和技术内容
2. 查阅相关资料，确保术语理解准确
3. 准备术语表和参考翻译

### 10.2 翻译阶段

1. 逐段翻译，确保准确性
2. 保持原文格式和结构
3. 检查术语一致性

### 10.3 审校阶段

1. 通读译文，检查通顺性
2. 对比原文，确保无遗漏
3. 检查术语是否一致
4. 验证技术内容准确性

### 10.4 提交阶段

1. 格式检查（Markdown、代码块等）
2. 链接验证
3. 提交 Pull Request

---

## 九、常见问题

### 11.1 遇到不确定的术语

- 查阅 Perfetto 官方文档
- 参考 Android 开发者文档
- 搜索 GitHub 上的相关讨论
- 保持原文

### 11.2 原文有误

- 仅给出提示，不在翻译结果中添加标注或说明。

### 11.3 图表和截图

- 保留原文图表
- 如有文字需翻译，可添加说明

### 11.4 示例代码

- 保持代码不变
- 注释可翻译


---

## 十、参考资料

- [Perfetto 官方文档](https://perfetto.dev/docs/)
- [Google 翻译规范](https://developers.google.com/style)
- [Android 开发者术语表](https://developer.android.com/guide/glossary)
- [Google 技术写作规范](https://developers.google.com/tech-writing)

---

## 十一、版本信息

- 版本：1.11
- 最后更新：2026-03-20
- 维护者：Perfetto 中文文档项目组

### 更新记录

- **v1.11** (2026-03-20)
  - 添加 Plugin 及其变体作为术语，翻译为"插件"
- **v1.10** (2026-03-20)
  - 添加 sideload 及其变体作为核心术语，保持英文不翻译
- **v1.9** (2026-03-20)
  - 添加 Fork 和 fork 作为核心术语，保持英文不翻译
  - 区分 GitHub Fork 操作和进程 fork 操作
- **v1.8** (2026-03-20)
  - 明确 Instrumentation 翻译规范，应翻译为"插桩"或"埋点"
  - 修复文档中未翻译的 instrumentation 和 instrumented 术语
- **v1.7** (2026-03-20)
  - 添加 Hook 及其变体(hook、hooks、Hooks)作为核心术语，保持英文不翻译
  - 修正 memory profiling 术语名称，保持与文档中实际使用的一致
- **v1.6** (2026-03-20)
  - 明确 memory 单独存在时不是术语，应翻译为"内存"
  - 将 memory profiling 和 memory profiler 作为复合术语单独列出
  - 更新核心术语表以区分普通词汇和专有术语
- **v1.5** (2026-03-20)
  - 根据 `markdown_render.js` 源码更新专用词汇标志规范
  - 明确支持的标志类型：NOTE、TIP、TODO/FIXME、WARNING、Summary
  - 删除不支持的标志：CAUTION、IMPORTANT、DANGER、SECURITY、INFO
  - 添加各标志对应的 CSS 类和渲染效果说明
  - 添加完整的翻译示例
- **v1.4** (2026-03-19)
  - 新增"格式保持规范"章节
  - 明确加粗、斜体、缩进等格式必须与英文文档一致
  - 添加格式检查清单
- **v1.3** (2026-03-19)
  - 添加换行处理规范
  - 明确中文翻译应保持渲染后的连贯效果，而非机械模仿英文换行
- **v1.2** (2026-03-19)
  - 添加专用词汇标志翻译规范（NOTE、TIP、WARNING 等）
  - 明确标志不翻译，保持原文格式
- **v1.1** (2026-03-19)
  - Tracing 和 Trace 添加到核心术语（保持英文）
  - 添加 "capture/record trace" 特殊组合翻译规则
  - 明确"采集 trace"的翻译规范
- **v1.0** (2026-03-19)
  - 初始版本

---

**备注：** 本规范会根据翻译实践持续更新和完善。
