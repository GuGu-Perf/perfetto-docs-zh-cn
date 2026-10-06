# PerfettoSQL pipe 运算符实现说明

本页面描述每个 PerfettoSQL pipeline 数据源与运算符的实现方式、所使用的数据结构与快速路径，以及它们的内存与流式特性。

> **警告:** pipe 语法及其实现是**实验性的、不稳定的**。请**不要**依赖这里描述的任何内容。无论是语法还是执行行为，都可能且必将在毫无预兆的情况下发生变化。

相关页面：

- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 语法入门指南](/docs/analysis/perfetto-sql-pipe-getting-started.md)

---

## 概览：批次与裁剪

pipeline 在列式批次上执行，每个批次最多 8192 行。批次中的每一列都是建立于一段连续数组之上的视图，可选地附带一个用于 null 的有效性位向量，以及一个用于在不复制值的前提下过滤或重排行的行选择索引缓冲区。

在任何运算符运行之前，都会先执行一趟反向活跃性分析（liveness pass），从 pipeline 的最终输出列回溯到各数据源：

- 未使用的列会从表扫描和子查询扫描中丢弃。
- 经由 `INTERVAL INTERSECTION OF` 携带的未使用列，会在操作数被读入内存之前被丢弃。
- `TREE ACCUMULATE` 中未使用的 `SUM(...)` 聚合会被丢弃。如果某个 `TREE ACCUMULATE` 阶段的输出列在下游均未被读取，整个阶段会从执行计划中移除，从而跳过节点编号、树排序和累加。

## `FROM`

`FROM` 数据源如何被读取，取决于它指向什么。

### 已定稿的 `PERFETTO TABLE` 与内置表

当 `FROM` 指向由已定稿的 Trace Processor dataframe 支撑的无限定名表（例如 `slice`、`sched`，或任何用 `CREATE PERFETTO TABLE` 创建的表）时，pipeline 会直接在 C++ 中读取该 dataframe 的列式存储，而不打开 SQLite 游标：

- 只读取下游阶段所需的列。
- 字符串与整数缓冲区会被直接引用到每个批次中，而不是逐行复制。
- 如果表的 `id` 列以隐式的 `0, 1, 2, ...` 行索引序列存储，下游的 `TREE ACCUMULATE` 等运算符会检测到这种存储类型并跳过哈希表查找。

### 视图与 `SELECT` 子查询

当 `FROM` 指向视图、虚拟表或带圆括号的 `SELECT` 子查询时，Trace Processor 会在 SQLite 中准备并逐步执行该 SQL 查询，再把返回的值复制到列式批次中。

如果列裁剪发现 SQL 数据源的某些列在下游从未被读取，则会在 SQLite 中准备该查询之前把它包装成：

```sql
WITH __pipeline_source(c0, c1, c2, ...) AS (SELECT * FROM <source>)
SELECT c0 AS "<col_0>", c2 AS "<col_2>" FROM __pipeline_source
```

只投影所需的位置列，可以让 SQLite 的查询规划器在展平子查询时丢弃无用的表达式或 JOIN，并避免把未使用的列从 SQLite 中复制出来。

## `INTERVAL INTERSECTION OF`

实现：`/src/trace_processor/core/exec/interval_intersect.cc`

`INTERVAL INTERSECTION OF` 是一个阻塞式数据源：它会先完整读取所有操作数，然后才产出第一个输出批次。

### 1. 读取操作数并分区

每个操作数都作为独立的子 pipeline 执行，并被读入内存：

- `ts`、`dur` 以及所有 `PER` 列必须是 64 位整数。`ts` 或 `dur` 为 `NULL` 的行会被跳过；`ts < 0` 或 `dur < 0` 的行会以错误终止执行。
- 只有被下游引用的操作数列才会缓冲到该操作数的 `RowStore` 中；未被引用的列会随批次到达而被丢弃。
- 每个有效行的 `[ts, ts + dur)` 区间和行索引都会插入到以 `PER` 列为键、逐操作数维护的哈希表中。每个 `PER` 列为分区键贡献 1 个存在性字节和 8 个值字节，因此在某个 `PER` 列上为 `NULL` 的两行会落入同一分区。
- 某个操作数读取完成后，各分区中的区间会按起点、终点和行索引排序，然后再扫描一次，记录该分区内是否存在相互重叠的区间。

### 2. 各分区内求交

只有当一个分区的 `PER` 键在每一个操作数中都存在时，该分区才能产生输出。运算符会在 `PER` 互异键最少的那个操作数的键上迭代，并跳过任何在别的操作数中缺失的键。

对于在所有操作数中都存在的键，它会在两条路径之间做出选择：

- **全不相交快速路径：**如果每个操作数在该分区中的区间都互不重叠，就对所有操作数一次性执行一趟多路线性扫描，把区域直接产出到输出缓冲区，不进行任何中间区域分配。
- **逐对收窄路径：**如果至少一个操作数在该分区中存在重叠区间，则该键对应的各操作数按区间数量升序排序。区间数最少的操作数作为种子，初始化候选区域的运行集合；其余每个操作数依次使用 `IntervalIntersector` 收窄该集合。它会根据该操作数是否存在重叠以及当前活跃候选区域的数量，在线性扫描、二分查找或区间树之间做出选择。

候选区域与输出区域存储为两个存放边界的平坦数组和一个存放操作数行索引的平坦数组，避免逐区域的堆分配。

### 3. 供给输出批次

所有分区完成求交后，输出按每批最多 8192 个区域依次供给。每个批次把区域的 `ts` 和 `dur` 写入两个平坦的 `Int64` 列，并为保留的列附加指向各操作数已缓冲 `RowStore` 的行选择视图。

## `TREE ACCUMULATE`

实现：
- `/src/trace_processor/core/exec/tree_number_nodes.cc`
- `/src/trace_processor/core/exec/tree_order.cc`
- `/src/trace_processor/core/exec/tree_accumulate.cc`

一个 `TREE ACCUMULATE` 阶段会被分解（lower）为三个步骤：节点编号、树排序和累加。

### 1. 节点编号：`TreeNumberNodes`

树运算符需要逐节点的状态：已访问位向量、等待列表和运行总和。经过过滤的查询所产生的原始 `id` 值，可能是任意散布在很大范围内的 64 位整数或字符串，因此直接用 `id` 作为数组下标，要么行不通，要么会分配与原表中最大 `id` 成正比的内存。

`TreeNumberNodes` 通过在每个批次末尾追加两个稠密的 `Uint32` 列来解决这个问题：一个是该行的节点编号，按首次被看到的顺序依次赋为 `0, 1, 2, ...`；另一个是该行父节点的节点编号，对 `parent_id IS NULL` 的根节点使用 `kNoNode`。下游的树运算符只检查这两个稠密 `Uint32` 列，因此所有逐节点数组的大小都按输入行数分配。

`TreeNumberNodes` 有三个执行层级：

1. **Dataframe `Id` 快速路径：**当扫描的 dataframe 未经过过滤、其 `id` 列的存储类型为 `Id`、`parent_id` 列为 `Uint32`，且每一行的父节点都出现在更早的行时，节点编号通过复制 `parent_id` 并原地填充 `0, 1, 2, ...` 来分配，既不需要哈希表，也不需要逐单元格的类型分派。
2. **稠密整数快速路径：**当 `id` 或 `parent_id` 以一般整数列的形式来自 SQLite 子查询时，该运算符会持续跟踪目前见到的 ID 是否仍是 `0, 1, 2, ...`，且父节点引用的都是已见过的 ID。只要这一条件保持成立，每个 `id` 本身就是自己的节点编号，哈希表保持为空。
3. **哈希表路径：**一旦出现第一个非稠密整数或字符串类型的 `id`，该运算符会把此前见过的所有稠密 ID 回填进它的 `FlatHashMap`，此后所有 `id` 和 `parent_id` 值都经由该哈希表映射。

### 2. 树排序：`TreeChildFirst` 与 `TreeParentFirst`

沿树向上或向下累加，都要求对行排序，使一个节点被访问时它所依赖的值已经计算完毕。两个方向都不要求严格的深度优先遍历顺序。子树之间可以交错，因为累加器为每个节点保存运行总和，而不是只维护一个从根到叶的栈。

#### `UP`：`TreeChildFirst`

`TREE ACCUMULATE UP` 要求每个子节点都先于其父节点出现。由于流式运算符要到输入结束才能知道一个到达的节点是否有子节点，`TreeChildFirst` 是一个阻塞式运算符，它会读完所有输入行之后才开始产出：

- 随着行的到达，它会跟踪两个标志：输入是否已经是子节点在前（child-first），即没有任何行的父节点比该行自身更早出现；以及是否是父节点在前（parent-first），即每个非根行的父节点都已经被见过。
- **已是子节点在前：**按到达顺序产出缓冲的批次，不构建索引排列。
- **已是父节点在前：**按到达的相反顺序产出缓冲的行，因为把任何父节点在前的顺序反转，都能得到合法的子节点在前顺序。
- **无序：**基于节点编号构建平坦的压缩稀疏行（compressed-sparse-row）子节点列表，用显式栈从根出发遍历以产生父节点在前的顺序，校验所有行都被访问到以便捕获环，最后把结果反转。

#### `DOWN`：`TreeParentFirst`

`TREE ACCUMULATE DOWN` 要求每个父节点都先于其子节点出现。与 `UP` 不同，这并不会完全打断 pipeline：某一行只要其父节点已被产出，就可以立即产出。

- `TreeParentFirst` 维护一个位向量，记录已经产出的节点。
- 批次到达时，任何根行，以及父节点已被标记为产出的行，都会直接通过。如果批次中的每一行都能通过，该批次会被原样转发，不复制任何列。
- 只有先于父节点到达的行才会被复制到侧边缓冲区，并链入按父节点划分的等待列表。一旦该父行到达并被产出，它等待中的子节点，以及这些子节点各自等待中的后代，都会被释放并在该批次之后产出。
- 内存与复制开销与先于父节点到达的行数成正比。当输入已经是父节点在前时，不会缓冲或复制任何内容。

### 3. 累加：`TreeAccumulateUp` 与 `TreeAccumulateDown`

阶段中的每个 `SUM(col)` 都会在排序后的批次上运行一个流式的 `TreeAccumulateUp` 或 `TreeAccumulateDown` 运算符：

- 求和列会被校验或加宽为平坦的 `Int64`，`NULL` 值按 `0` 参与求和。加法使用带溢出检查的 64 位运算，因此整数溢出会作为错误报告，而不是静默回绕。
- 该运算符只维护一个按节点编号索引的 `std::vector<int64_t>`：
  - **`TreeAccumulateUp`：**当某个 `node` 的行到达时，它的所有后代都已被处理，并已把各自的子树和累加进 `by_node[node]`。运算符计算 `total = value + by_node[node]`，把 `total` 写入输出批次，并把 `total` 累加进 `by_node[parent]`。
  - **`TreeAccumulateDown`：**当某个 `node` 的行到达时，它的 `parent` 已被处理，并把它的路径和存入了 `by_node[parent]`。运算符计算 `total = value + by_node[parent]`，存入 `by_node[node] = total`，并把 `total` 写入输出批次。

### 4. 连续 `TREE ACCUMULATE` 阶段之间的复用

当 pipeline 串联多个 `TREE ACCUMULATE` 阶段时：

- 只要 `id` 和 `parent_id` 仍指向相同的底层列，连续的 `TREE ACCUMULATE` 阶段就会共享同一组 `TreeNumberNodes` 列。
- 两个连续的 `TREE ACCUMULATE UP` 阶段，或两个连续的 `DOWN` 阶段，会复用第一个阶段的树排序，并跳过插入第二个排序运算符。
- 在 `UP` 与 `DOWN` 之间切换时，会复用节点编号，并为新方向重新对行排序。

## `SELECT`、`EXTEND`、`DROP`、`RENAME`、`SET` 和 `AS`

实现：`/src/trace_processor/perfetto_sql/pipeline/compiler.cc`

列重塑阶段 `SELECT`、`EXTEND`、`DROP`、`RENAME`、`SET` 和 `AS` 没有运行时运算符，在批次执行期间不做任何工作。

编译期间，pipeline 编译器把当前行维护为一个由 `(column_name, ColumnId, qualified_only)` 条目组成的向量，同时维护一份活跃表别名列表。每个活跃别名都持有该向量在别名被绑定那一刻的快照：

- `DROP` 从编译期行向量中移除条目。
- `RENAME` 修改匹配条目上的 `column_name` 字符串。
- `SET` 把目标条目的 `ColumnId` 更新为指向源列的 `ColumnId`。
- `EXTEND` 向行向量追加新的 `(column_name, ColumnId)` 条目。
- `AS` 用当前行向量的副本替换活跃别名列表。
- `SELECT` 用选定的 `(column_name, ColumnId)` 条目替换行向量，并清空活跃别名列表。

编译结束时，只有最终行向量中出现的 `ColumnId` 才会被标记为存活以供列裁剪，并在向 SQLite 返回结果时映射到物理批次列索引。在 pipeline 阶段中重排、复制、重命名或删除列，从不在运行时复制列数据。
