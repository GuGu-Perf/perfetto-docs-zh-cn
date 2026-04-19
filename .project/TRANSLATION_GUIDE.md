# Perfetto 文档翻译规范

## 一、基本原则

本规范基于 [Google Developer Documentation Style Guide](https://developers.google.com/style) 和 Microsoft 技术写作标准制定。当以下原则发生冲突时，按优先级从高到低处理。

### 1.1 技术正确性（最高优先级）

译文必须准确传达原文的技术含义。错误的好读不如正确的难读。

- 不确定时保留英文原文，不要猜测翻译
- 参数名、API 标识符、配置字段名**严禁翻译**
- 数值、单位、格式字符串保持原样

### 1.2 术语一致性

同一术语在全文中必须统一。首次出现时可括注英文，后续不再重复。

- 以本文档第二章术语表为唯一依据
- 上游 Perfetto 源码中的命名优先于通用翻译
- 变种形式遵循相同规则（如 Track 包含 track / tracks / TrackEvent 等）

### 1.3 中文通顺性（最低优先级）

在满足以上两条前提下，使译文符合中文表达习惯。

- 避免欧化长句，适当拆分或调整语序
- 中英文之间加空格（如 "使用 Trace 分析"）
- 使用中文标点（句末用 。 而非 .）

> **决策示例**：如果某个短语翻译后更通顺但与术语表冲突，**以术语表为准**。
> 如果某个句子调整语序后更通顺但可能引起歧义，**保持原文语序**。


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
| track event | track event | 轨道事件 |
| trace processor | trace processor | 追踪处理器 |
| Performance | 性能 | Performance |

**动词翻译说明**：
- `capture trace` / `record trace` → **采集 trace**（贴近实际工作语言）
- `to profile` → **进行 profile/profiling**（核心术语不翻译）
- 其他常用动词（start→开始, stop→停止等）按常规范翻译

---


## 三、语法和句式规范

- **换行**：英文手动换行仅为编辑便利，中文合并为连贯句子（除非有明显语义断点）
- **长句**：超过 50 字拆分为短句，用逗号或分号连接
- **被动语态**：优先转主动，但不强行转换导致歧义
- **条件句**：If → "如果...则..."，When → "当...时"
- **列表项**：保持原文数量和层级，术语按术语表处理
- **动词固定搭配**：capture/record trace → 采集 trace；to profile → 进行 profile

## 四、格式保持规范

**总则：Markdown 格式必须与原文 100% 一致。**

| 元素 | 规则 |
|------|------|
| 加粗/斜体/代码 | 保留标记，替换内容 |
| 列表 | 类型、层级、数量不变 |
| 标题 | 层数和数量不变 |
| 代码块 | 语言标记不变，块内不翻译 |
| 表格 | 行列数严格一致 |
| 链接 | URL 不变 |
| 图片 | 路径不变（绝对路径 /docs/images/） |

## 五、标点符号规范

- 句末使用中文句号 `。` 而非英文 `.`
- 中英文之间加空格：`使用 Trace 分析性能`、`共 11473 个文件`
- 省略号用 `……` 而非 `...`

### 专用标志不翻译

Perfetto 文档站点将以下标志渲染为带图标的提示框，**标志名必须保留英文**：

| 标志 | 说明 | 渲染效果 |
|------|------|----------|
| NOTE: | 注意 | 蓝色背景 |
| TIP: | 提示 | 绿色背景 |
| WARNING: | 警告 | 红色背景 |
| Summary: | 总结 | 青色背景 |
| TODO: / FIXME: | 待办 | 灰色背景 |

格式：段落开头 `标志: 内容`，标志名后正常翻译。

```
NOTE: The buffer size must be a power of two.
-> NOTE: 缓冲区大小必须是 2 的幂。

WARNING: This operation cannot be undone.
-> WARNING: 此操作无法撤销。
```

### 链接与引用

- 链接 URL 不变，链接文本可翻译
- 图片路径不变（绝对路径 /docs/images/xxx），alt 可翻译
## 六、特殊处理

- **API 名称**：不翻译方法名、类名、变量名
- **命令参数**：参数名不翻译，说明可翻译
- **快捷键**：Ctrl+C, Cmd+Enter 不翻译
- **版本号**：v1.2.3 不翻译
- **时间日期**：可译为中文格式

## 七、常见问题

- 不确定的术语 → 保留英文
- 原文有误 → 按原文翻译，不添加标注
- 图表截图 → 保留原图；示例代码 → 不变

## 八、LLM 翻译使用指南

将本文档全文提供给大模型作为翻译上下文（100% 规则覆盖），无需提炼为 prompt。

### 使用方式

**Web UI（ChatGPT/Claude）**：粘贴规范全文 + "请严格遵循此规范翻译。OK？" → 逐个发送 `.md` 文件

**API 调用**：规范放 `system` message，原文放 `user` message

**本地模型**：`cat 规范.md 原文.md | ollama run llama3 > 输出.md`

### 翻译后必做

```bash
bash .project/proofread.sh --file docs/你翻译的文件.md   # 校对术语和格式
bash .project/workwork.sh deploy-local                   # 本地预览
bash .project/workwork.sh sync-check                     # 检查上游变更
```

## 十、参考资料

- [Google Developer Documentation Style Guide](https://developers.google.com/style)
- [Microsoft Writing Style Guide](https://learn.microsoft.com/en-us/style-guide/)
- [Perfetto 官方文档](https://perfetto.dev/docs/)
