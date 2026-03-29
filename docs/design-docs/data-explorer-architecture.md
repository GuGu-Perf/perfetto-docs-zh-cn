# Data Explorer 架构

本文档解释了 Perfetto 的 Data Explorer 的工作原理，从创建可视化查询图到执行 SQL 查询和显示结果。它涵盖了使 Data Explorer 能够提供用于 trace 分析的交互式基于节点的 SQL 查询构建器的关键组件、数据流和架构模式。

## 概述

Data Explorer 是一个可视化查询构建器，允许用户通过在有向无环图（DAG）中连接节点来构建复杂的 SQL 查询。每个节点代表数据源（表、Slice、自定义 SQL）或操作（过滤、聚合、连接等）。系统将此可视化图转换为结构化的 SQL 查询，通过 trace processor 执行它们，并在交互式数据网格中显示结果。

## 核心数据流

```
用户交互 → 节点图 → 结构化查询生成 →
查询分析(验证) → 查询物化 → 结果显示
```

## 节点图结构

**QueryNode** (`ui/src/plugins/dev.perfetto.DataExplorer/query_node.ts:128-161`)
- 所有节点类型的基础抽象
- 维护双向连接：`primaryInput`(上游)、`nextNodes`(下游)、`secondaryInputs`(侧连接)
- 通过 `getStructuredQuery()` 生成结构化查询 protobuf
- 验证配置并提供 UI 渲染方法

**节点连接** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/graph_utils.ts`)
- 主输入：垂直数据流(单个父节点)
- 次输入：水平数据流(带端口号的侧连接)
- 通过 `addConnection()`/`removeConnection()` 进行双向关系管理
- 基于端口的多输入操作路由

## 节点注册和创建

**NodeRegistry** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/node_registry.ts`)
- 所有节点类型的中央注册表
- 描述符指定：名称、图标、类型（源/修改/多源）、工厂函数
- 可选的 `preCreate()` 钩子用于交互式设置(例如，表选择模态框)
- 支持键盘快捷键以快速创建节点

**核心节点** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/core_nodes.ts`)
```typescript
registerCoreNodes() {
 nodeRegistry.register('table', {...});
 nodeRegistry.register('slice', {...});
 nodeRegistry.register('sql', {...});
 nodeRegistry.register('filter', {...});
 nodeRegistry.register('aggregation', {...});
 // ... 更多节点
}
```

## 节点类型

### 1. 源节点(数据源)
**TableSourceNode** - 查询特定的 SQL 表
**SlicesSourceNode** - 用于 trace Slice 的预配置查询
**SqlSourceNode** - 作为数据源的自定义 SQL 查询
**TimeRangeSourceNode** - 生成时间间隔

### 2. 单输入修改节点
**FilterNode** - 添加 WHERE 条件
**SortNode** - 添加 ORDER BY 子句
**AggregationNode** - 带聚合函数的 GROUP BY
**ModifyColumnsNode** - 重命名/删除列
**AddColumnsNode** - 通过 LEFT JOIN 和/或计算表达式从次源添加列
**LimitAndOffsetNode** - 分页

### 3. 多输入节点
**UnionNode** - 组合来自多个源的行
**JoinNode** - 通过 JOIN 条件组合列
**IntervalIntersectNode** - 查找重叠的时间间隔
**FilterDuringNode** - 使用次间隔输入进行过滤
**CreateSlicesNode** - 将来自两个次源的开始/结束事件配对到 Slice 中

## UI 组件

**Builder** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/builder.ts`)
- 协调所有子组件的主组件
- 使用可调整大小的侧边栏和分割面板管理布局
- 三个视图：信息、修改（特定于节点）、结果
- 处理节点选择、执行回调、撤销/重做
- 接收 `GraphCallbacks` 接口并将其直接传播到 Graph(无 prop drilling)

**Graph** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/graph/graph.ts`)
- 用于节点操作的可视化画布
- 具有持久化布局的拖放定位
- 通过可拖动端口进行连接管理
- 用于文档的标签注释
- 定义 `GraphCallbacks` 接口（14 个回调）和 `GraphAttrs extends GraphCallbacks`

**NodePanel** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/node_panel.ts`)
- 用于选定节点的侧边栏面板
- 显示节点信息、配置 UI 和 SQL 预览
- 在状态更改时触发查询分析
- 通过 QueryExecutionService 管理执行流程

**DataExplorer** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/data_explorer.ts`)
- 显示查询结果的底部抽屉
- 通过 SQLDataSource 进行服务器端分页
- 基于列的过滤和排序
- 导出到时间轴功能

## 查询执行模型

### 两阶段执行

**阶段 1：分析(验证)**
```
节点图 → 结构化查询 Protobuf → Engine.updateSummarizerSpec() + querySummarizer() →
查询 {sql, textproto, columns} | 错误
```
- 通过 `createSummarizer(summarizerId)` 创建 summarizer(每个会话一次)
- 通过 `updateSummarizerSpec(summarizerId, spec)` 向 TP 注册查询
- 通过 `querySummarizer(summarizerId, queryId)` 获取 SQL 和元数据(触发延迟物化)
- TP 在内部计算 proto 哈希以进行更改检测

**阶段 2：物化(执行)**
```
engine.querySummarizer(summarizerId, nodeId) → TP 创建/重用表 →
{tableName, rowCount, columns, durationMs} → SQLDataSource → DataGrid 显示
```
- TP 为服务器端分页创建持久化表(延迟，在第一次 querySummarizer 时)
- TP 在内部处理缓存(如果 proto 哈希未更改则重用表)
- querySummarizer 返回显示所需的所有元数据

### QueryExecutionService

**目的** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/query_execution_service.ts`)
- 通过 FIFO 执行队列防止快速用户交互期间的竞态条件
- 对快速请求进行去抖动以批量用户输入
- 与 Trace Processor 的物化 API 协调
- 执行前的查询分析(验证)

**Trace Processor 作为单一事实来源**

所有物化状态由 Trace Processor （TP）管理，而不是 UI:
- TP 跟踪哪些查询已物化(按 query_id)
- TP 在内部比较 SQL 哈希以检测更改
- TP 根据需要创建/删除表
- TP 存储表名和错误状态

UI 按需查询 TP 而不是缓存：
```typescript
// 需要从 TP 获取表名时（例如，用于"复制表名"或导出）
async getTableName(nodeId: string): Promise<string | undefined> {
 const result = await engine.querySummarizer(DATA_EXPLORER_SUMMARIZER_ID, nodeId);
 if (result.exists !== true || result.error) {
 return undefined;
 }
 return result.tableName;
}
```

这消除了 UI 和 TP 之间的状态同步错误。

**FIFO 执行队列**
- 串行执行(一次一个操作)
- 保留节点依赖关系(父节点在子节点之前物化)
- 每操作错误隔离(错误被记录，不抛出)

**快速节点点击处理** (`ui/src/base/async_limiter.ts`)

`AsyncLimiter` 确保在快速单击节点时只运行最新的排队任务：
```typescript
// AsyncLimiter 行为:
while ((task = taskQueue.shift())) {
 if (taskQueue.length > 0) {
 task.deferred.resolve(); // 跳过 - 更新的任务在等待
 } else {
 await task.work(); // 运行 - 这是最新的
 }
}
```

示例：在 A 处理时快速单击 A → B → C:
1. A 开始处理
2. B 排队，C 排队
3. A 完成
4. B 跳过（队列有 C）,C 运行

这确保处理当前选定的节点（C），跳过中间的单击（B）。

**通过 TP API 物化**
```typescript
// 与 TP 同步所有查询,然后获取目标节点的结果
async processNode(node: QueryNode): Promise<void> {
 // 1. 确保 summarizer 存在(每个会话创建一次)
 await engine.createSummarizer(DATA_EXPLORER_SUMMARIZER_ID);

 // 2. 向 TP 注册所有查询(处理更改检测)
 const spec = buildTraceSummarySpec(allNodes);
 await engine.updateSummarizerSpec(DATA_EXPLORER_SUMMARIZER_ID, spec);

 // 3. 获取结果 - 触发延迟物化
 const result = await engine.querySummarizer(DATA_EXPLORER_SUMMARIZER_ID, node.nodeId);
 // 返回:tableName, rowCount, columns, durationMs, sql, textproto
}
```

**自动执行逻辑** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/query_execution_service.ts`)

| autoExecute | manual | 行为 |
|-------------|--------|---------------------------------------|
| true | false | 自动分析 + 执行 |
| true | true | 分析 + 执行（强制） |
| false | false | 跳过 - 显示"运行查询"按钮 |
| false | true | 分析 + 执行（用户点击） |

自动执行禁用于：SqlSourceNode、IntervalIntersectNode、UnionNode、FilterDuringNode、CreateSlicesNode

### 状态管理

**DataExplorerState** (`ui/src/plugins/dev.perfetto.DataExplorer/data_explorer.ts`)
```typescript
interface DataExplorerState {
 rootNodes: QueryNode[]; // 没有父节点的节点(起点)
 selectedNodes: ReadonlySet<string>; // 选定节点 ID 的集合(多选)
 nodeLayouts: Map<string, {x, y}>; // 可视化位置
 labels: Array<{...}>; // 注释
 isExplorerCollapsed?: boolean;
 sidebarWidth?: number;
 loadGeneration?: number; // 内容加载时递增
 clipboardNodes?: ClipboardEntry[]; // 多节点复制/粘贴
 clipboardConnections?: ClipboardConnection[];
}
```

**查询状态管理** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/builder.ts:60-86`)

Builder 维护 `this.query` 作为查询状态的单一事实来源：
- 由自动分析（来自 NodePanel）和手动执行（来自 Builder）更新
- 作为 prop 传递给 NodePanel 用于渲染 SQL/Proto 选项卡
- 确保自动执行和自动执行节点的查询显示一致

查询状态流：
```
自动执行(autoExecute=true):
 NodePanel.updateQuery() → processNode({ manual: false })
 → onAnalysisComplete → 设置 NodePanel.currentQuery
 → onAnalysisComplete → 调用 onQueryAnalyzed 回调 → 设置 Builder.query
 → Builder 将 query 作为 prop 传递给 NodePanel
 → NodePanel.renderContent() 使用 attrs.query ?? this.currentQuery

手动执行(autoExecute=false):
 用户单击"运行查询" → Builder 调用 processNode({ manual: true })
 → onAnalysisComplete → 设置 Builder.query
 → onAnalysisComplete → 调用 onNodeQueryAnalyzed 回调 → 设置 Builder.query
 → Builder 将 query 作为 prop 传递给 NodePanel
 → NodePanel.renderContent() 使用 attrs.query(this.currentQuery 可能未定义)
```

这确保了 SQL/Proto 选项卡在自动和手动执行模式下都能正确显示。

**竞态条件预防** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/builder.ts:283-292`)

回调在创建时捕获选定节点以防止陈旧查询泄漏：
```typescript
const callbackNode = selectedNode;
this.onNodeQueryAnalyzed = (query) => {
 // 仅当仍在同一节点上时才更新
 if (callbackNode === this.previousSelectedNode) {
 this.query = query;
 }
};
```

没有此检查，快速节点切换可能会导致：
1. 用户选择节点 A → 异步分析开始
2. 用户快速切换到节点 B → 节点 A 的组件被销毁
3. 节点 A 的分析完成 → 回调使用节点 A 的查询触发
4. 节点 B 在 SQL/Proto 选项卡中错误地显示节点 A 的查询

验证确保切换后忽略来自旧节点的回调。

**HistoryManager** (`ui/src/plugins/dev.perfetto.DataExplorer/history_manager.ts`)
- 具有状态快照的撤销/重做堆栈
- 通过 `serializeState()` 为每个节点进行序列化
- 反序列化从 JSON 重建整个图

## 图操作

**节点创建** (`ui/src/plugins/dev.perfetto.DataExplorer/node_crud_operations.ts`)
```typescript
// 源节点
addSourceNode(deps, state, id) {
 const descriptor = nodeRegistry.get(id);
 const initialState = await descriptor.preCreate?.(); // 可选模态框
 const newNode = descriptor.factory(initialState);
 rootNodes.push(newNode);
}

// 操作节点
addOperationNode(deps, state, parentNode, id) {
 const newNode = descriptor.factory(initialState);
 if (singleNodeOperation(newNode.type)) {
 insertNodeBetween(parentNode, newNode); // A → C 变为 A → B → C
 } else {
 addConnection(parentNode, newNode); // 多输入:只需连接
 }
}
```

**节点删除** (`ui/src/plugins/dev.perfetto.DataExplorer/node_crud_operations.ts`)
```typescript
// 复杂的重连接逻辑保留数据流
deleteNode(deps, state, node) {
 1. await cleanupManager.cleanupNode(node); // 删除 SQL 表
 2. 捕获图结构(父节点、子节点、端口连接)
 3. disconnectNodeFromGraph(node)
 4. 将主父节点重新连接到子节点(绕过已删除的节点)
  - 仅主连接(portIndex === undefined)
  - 删除次连接(特定于已删除的节点)
 5. 更新根节点(添加孤立节点)
 6. 将布局转移到停靠的子节点
 7. 通过 onPrevNodesUpdated() 通知受影响的节点
}
```

**图遍历** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/graph_utils.ts`)
- `getAllNodes()`: BFS 遍历(向前和向后)
- `getAllDownstreamNodes()`：向前遍历(用于失效)
- `getAllUpstreamNodes()`：向后遍历(用于依赖检查)
- `insertNodeBetween()`：插入操作时重新连接连接

## 失效和缓存

**TP 管理的缓存**

查询哈希缓存和更改检测完全由 Trace Processor 处理：
- TP 为每个物化查询计算并存储 proto 哈希
- 调用 `updateSummarizerSpec()` 时，TP 将新哈希与存储的哈希进行比较
- 如果未更改，TP 返回现有表名而不重新执行
- 如果已更改，TP 删除旧表并创建新表

**延迟物化**

物化是延迟的 - TP 仅在为该特定查询调用 `querySummarizer()` 时才物化查询。调用 `updateSummarizerSpec()` 时，图中所有有效的查询都在 TP 中注册，但不执行 SQL。仅当调用 `querySummarizer(nodeId)` 时，TP 才实际物化该查询（及其依赖项）。这避免了用户尚未查看的节点的不必要工作。

**智能重新物化优化**

当通过 `updateSummarizerSpec()` 与 TP 同步查询时，TP 执行智能更改检测和依赖跟踪，以最大限度地减少冗余工作：

1. **基于 proto 的更改检测**：每个查询的结构化查询 proto 字节被哈希（而不是生成的 SQL）。这对于具有 `inner_query_id` 引用的查询可以正确工作，这些查询的 SQL 无法独立生成。

2. **依赖传播**：如果查询 B 通过 `inner_query_id` 依赖于查询 A，并且 A 的 proto 更改，则即使 B 的 proto 未更改（因为 B 的输出依赖于 A 的数据）,B 也必须重新物化。TP 通过整个依赖链传递传播此依赖关系。

3. **表源替换**：对于已经物化的未更改查询，TP 用引用物化表的简单表源结构化查询替换它们。为更改的查询生成 SQL 时，它们直接引用这些表，而不是重新展开完整的查询链。

示例：对于链 A → B → C → D，如果 C 更改：
- A、B：未更改，使用现有的物化表(`_exp_mat_0`、`_exp_mat_1`)
- C：已更改，重新物化(SQL 直接引用 B 的物化表)
- D：传递性更改（依赖于 C），重新物化(SQL 引用 C 的新表)

此优化通过避免冗余 SQL 生成和执行显著加速长查询链中的增量编辑。TP 端实现位于 `src/trace_processor/trace_summary/summarizer.cc`。

**按需状态查询**

UI 在需要时从 TP 查询物化状态：
```typescript
// 从 TP 获取当前状态(用于"复制表名"、导出等)
const result = await engine.querySummarizer(DATA_EXPLORER_SUMMARIZER_ID, nodeId);
// 返回:{ exists: boolean, tableName?: string, error?: string, ... }
```

此设计确保：
- 没有 UI 端状态可能变得陈旧或与 TP 不同步
- TP 是所有物化状态的权威来源
- 更简单的 UI 代码，没有缓存失效逻辑

**Trace Processor 重启处理**

如果 Trace Processor 重启或崩溃，所有 summarizer 状态（包括物化表）都会丢失。UI 可能仍然持有 TP 中不再存在的陈旧 `summarizerId`。当下一次 `querySummarizer()` 调用发生时，TP 将返回错误，指示 summarizer 不存在。UI 会优雅地处理此错误，将其视为需要在下一次执行尝试时重新创建 summarizer 并重新同步所有查询。用户可能会看到错误消息，但再次单击"运行查询"将恢复状态。

## 结构化查询生成

**查询构建** (`ui/src/plugins/dev.perfetto.DataExplorer/query_builder/query_builder_utils.ts`)
```typescript
getStructuredQueries(finalNode) {
 const queries: PerfettoSqlStructuredQuery[] = [];
 let currentNode = finalNode;

 // 从叶到根遍历图
 while (currentNode) {
 queries.push(currentNode.getStructuredQuery());
 currentNode = currentNode.primaryInput; // 遵循主输入链
 }

 return queries.reverse(); // 根 → 叶顺序
}

analyzeNode(node, engine) {
 const structuredQueries = getStructuredQueries(node);
 const spec = new TraceSummarySpec();
 spec.query = structuredQueries;
 await engine.createSummarizer(ANALYZE_NODE_SUMMARIZER_ID); // 确保 summarizer 存在
 await engine.updateSummarizerSpec(ANALYZE_NODE_SUMMARIZER_ID, spec); // 向 TP 注册
 const result = await engine.querySummarizer(ANALYZE_NODE_SUMMARIZER_ID, node.nodeId); // 获取结果
 return {sql: result.sql, textproto: result.textproto};
}
```

## 序列化和示例

**JSON 序列化** (`ui/src/plugins/dev.perfetto.DataExplorer/json_handler.ts`)
- `exportStateAsJson()`：将整个图状态序列化为 JSON 文件
- `deserializeState()`：从 JSON 重建图
- 每个节点实现 `serializeState()` 用于特定于节点的状态
- 用于：导入/导出、示例、撤销/重做快照

**示例系统** (`ui/src/plugins/dev.perfetto.DataExplorer/examples_modal.ts`)
- 预构建的图作为 JSON 存储在 `ui/src/assets/data_explorer/` 中
- 首次访问时自动加载基本页面状态
- 模态框允许用户加载策划的示例

## 关键架构模式

### 1. 基于节点的查询构建
所有查询通过可组合节点构建：
- 源提供初始数据(表、Slice、自定义 SQL)
- 操作转换数据(过滤、聚合、连接)
- 节点通过拖放可视化界面连接
- 图结构直接映射到 SQL 查询结构

### 2. 双向图连接
节点维护前向和后向链接：
- `primaryInput`：单个父节点(垂直数据流)
- `secondaryInputs`：端口 → 父节点的映射(侧连接)
- `nextNodes`：子节点数组(此节点输出的使用者)
- 图操作在所有链接上维护一致性

### 3. 两阶段执行与延迟物化
- 分析阶段：验证查询结构而不执行
- 执行阶段：物化到 PERFETTO 表以进行分页
- 延迟物化：仅物化选定节点及其上游依赖项
- TP 在内部处理表缓存(proto 哈希未更改时重用)
- 智能重新物化：未更改的父查询使用表源替换
- 通过 SQLDataSource 进行服务器端分页(无完整结果获取)

### 4. TP 管理状态的 FIFO 队列
- 防止快速用户输入期间的竞态条件
- 操作按顺序执行(保留节点依赖关系)
- 每操作错误隔离(一个失败不会阻塞队列)
- TP 在内部处理所有缓存/更改检测
- UI 按需查询 TP 以获取表名(无 UI 端缓存)

### 5. 结构化查询协议
- 节点生成 protobuf `PerfettoSqlStructuredQuery`
- Engine 通过 `updateSummarizerSpec()` + `querySummarizer()` 验证并转换为 SQL
- 基于哈希的更改检测(proto 字节由 TP 哈希)
- 允许查询分析而无需 SQL 字符串操作

### 6. 模块化纯函数架构
`data_explorer.ts` 将业务逻辑委托给专注于纯函数的模块：
- 每个模块定义 `Deps` 接口用于其所需的依赖项
- 函数显式接收依赖项(无类 `this` 访问)
- `data_explorer.ts` 构建依赖项对象并委托给模块函数
- 启用测试、重用和清晰的责任边界

模块：
- **node_crud_operations.ts** — 节点添加/删除/复制/连接/断开连接(`NodeCrudDeps`)
- **datagrid_node_creation.ts** — 从 DataGrid 交互触发的节点创建(`DatagridNodeCreationDeps`)
- **clipboard_operations.ts** — 多节点复制/粘贴
- **graph_io.ts** — 导入/导出、图加载、模板初始化(`GraphIODeps`)
- **node_actions.ts** — 用于节点→图交互的基于闭包的回调(`NodeActionHandlers`)

### 7. GraphCallbacks 接口(减少 Prop Drilling)
14 个回调从 `data_explorer.ts` 流向 `Builder` → `Graph`:
- `GraphCallbacks` 接口在 `graph.ts` 中定义，对所有 14 个回调进行分组
- `BuilderAttrs` 有一个 `graphCallbacks: GraphCallbacks` 字段
- Builder 将 `...attrs.graphCallbacks` 直接传播到 `Graph` 组件
- 消除了通过 Builder 手动转发每个回调的需要

## 文件路径参考

**核心基础设施**：
- `ui/src/plugins/dev.perfetto.DataExplorer/data_explorer.ts` - 主插件、状态管理、键盘处理、依赖项构建
- `ui/src/plugins/dev.perfetto.DataExplorer/query_node.ts` - 节点抽象和类型定义
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/builder.ts` - 主 UI 组件(接收 `GraphCallbacks`)
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/query_execution_service.ts` - 执行协调

**业务逻辑模块**(具有显式依赖注入的纯函数):
- `ui/src/plugins/dev.perfetto.DataExplorer/node_crud_operations.ts` - 节点添加/删除/复制/连接/断开连接
- `ui/src/plugins/dev.perfetto.DataExplorer/datagrid_node_creation.ts` - 从 DataGrid 交互触发的节点创建
- `ui/src/plugins/dev.perfetto.DataExplorer/clipboard_operations.ts` - 多节点复制/粘贴
- `ui/src/plugins/dev.perfetto.DataExplorer/graph_io.ts` - 导入/导出、图加载、模板初始化
- `ui/src/plugins/dev.perfetto.DataExplorer/node_actions.ts` - 用于节点→图交互的基于闭包的回调

**节点系统**：
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/node_registry.ts` - 节点注册
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/core_nodes.ts` - 核心节点注册
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/nodes/` - 单个节点实现

**UI 组件**：
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/graph/graph.ts` - 可视化图画布(定义 `GraphCallbacks`)
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/node_panel.ts` - 节点侧边栏
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/data_explorer.ts` - 结果抽屉

**工具**：
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/graph_utils.ts` - 图遍历和连接管理
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/query_builder_utils.ts` - 查询分析和工具
- `ui/src/plugins/dev.perfetto.DataExplorer/query_builder/cleanup_manager.ts` - 资源清理
- `ui/src/plugins/dev.perfetto.DataExplorer/history_manager.ts` - 撤销/重做管理
- `ui/src/plugins/dev.perfetto.DataExplorer/json_handler.ts` - 序列化

**Trace Processor (C++)**：
- `src/trace_processor/trace_summary/summarizer.cc` - 带有更改检测和依赖传播的智能重新物化
- `src/trace_processor/trace_summary/summarizer.h` - Summarizer 类定义和 QueryState
- `src/trace_processor/perfetto_sql/generator/structured_query_generator.cc` - 从结构化查询生成 SQL
