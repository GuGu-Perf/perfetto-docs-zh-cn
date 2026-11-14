# PerfettoSQL pipe 运算符实现说明

本页面描述 pipeline 如何被编译与执行，以及每个阶段是如何实现的。

> **警告:** pipe 语法及其实现是**实验性的、不稳定的**。请**不要**依赖这里描述的任何内容。无论是语法还是执行行为，都可能且必将在毫无预兆的情况下发生变化。

相关页面：

- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 语法入门指南](/docs/analysis/perfetto-sql-pipe-getting-started.md)

---

## 从查询到行

代码：`/src/trace_processor/perfetto_sql/pipeline/`

1. **编译。** `Compiler` 把解析后的 pipeline 转换成一个 `LogicalPlan`：一棵由 `PlanNode` 组成的树，每个数据源或阶段对应一个节点，各持有一个 `PlanOperation`。名称解析与类型检查都在这一步完成，因此错误会指向出错的 token。
2. **裁剪。** `PruneColumns` 丢弃没有任何下游读取的内容（参见[列裁剪](#column-pruning)）。
3. **序列化。** `SelectPipelineSql` 把执行计划写成字节，并包装成一条调用 `__intrinsic_pipeline` 表函数的 SQL 语句。每个 SQL 数据源都变成一个由 `__intrinsic_dataframe_agg` 构造的参数（参见[`FROM`](#from)）。
4. **降级（lower）。** 当 SQLite 执行该语句时，执行计划会被读回（`DeserializePlan`），各 SQL 数据源被绑定为 dataframe（`BindDataframeArgs`），绑定后遍历（bound passes）会重写它（参见[绑定后遍历](#bound-passes)），最后由 `Lower` 把它转换为由执行器运算符组成的 `PhysicalPlan`。直接读取的表会被校验，确认它与执行计划编译时所依据的是同一张表。
5. **运行。** `RowCursor` 拉动各批次流过运算符，SQLite 再逐行读取它们。

每个 `PlanOperation` 说明三件事。`Needs` 是它对每个输入的行有什么要求，例如某个给定类型的列、按某些键分组并按 `ts` 排好序的行，或者一种树序。`Derive` 是它随后输出什么：有哪些列、各列的类型，以及行的排列方式（`OutputProperties`）。`Lower` 则加入自己的运算符。

所有做决策的工作都集中在对执行计划的一趟遍历（`RunBoundPasses`）中完成，方向自各输入向上。在每个节点上，它先让该操作重写执行计划（`Rewrite`）；然后比较每个输入提供的内容与该节点的需求，并算出需要采取的步骤：类型转换、排序、分组或树序，且只在行尚不处于该状态时才插入。它最后才推导节点的输出，这同时为其中的表达式确定了类型。执行计划的任何问题都在这里被发现。降级某个输入时会顺带执行这些步骤，因此降级本身不做任何决策，也不可能失败。顺序不再被任何下游读取的排序，会在被更晚的排序取代时从执行计划中移除。

拥有多个输入的运算符（例如 `INTERVAL INTERSECTION OF`）会通过侧 pipeline（`AddSidePipeline`）读取每个额外输入，侧 pipeline 的降级方式与主 pipeline 相同。

### 批次

运算符之间传递列式批次（`RowBatch`），每个批次最多 2048 行。每一列都是建立在一段平坦数组之上的视图，可选地附带一个用于 `NULL` 的位向量。每个批次只有一个 `Selection`（行选择集）：一组递增的行索引，指明哪些行是存活的。它只能丢弃行，因此过滤不会复制任何内容。重排行（如排序所做的）则会把行复制进新的缓冲区（`RowStore::Gather`）。

### 列裁剪 {#column-pruning}

降级之前，`PruneColumns` 从 pipeline 的输出回溯到各数据源，标记出会被读取的列：

- 数据源只读取存活的列。扫描总是至少读取一个列，因此它仍然知道共有多少行。
- `INTERVAL INTERSECTION OF` 只保留会被读取的操作数列。
- 没有任何人读取的聚合会从 `TREE ACCUMULATE`、`INTERVAL FLATTEN` 和 `AGGREGATE` 中丢弃。如果 `TREE ACCUMULATE` 的输出一列都没有被读取，整个阶段都会被移除。
- `INTERVAL FILL GAPS` 丢弃没有人读取的输出。
- `WHERE`、`ORDER BY` 和 `DISTINCT` 保留它们用于比较的列，`AGGREGATE` 保留其键。

### 绑定后遍历 {#bound-passes}

有些决策依赖绑定（binding）阶段发现的信息：一张表是如何排序或索引的，或者某个输入的行会以什么顺序到达。编译期做不了这些决策，因为它只能看到名称和形状；降级也做不了，因为它一次只为一个操作添加步骤，从不移动操作。

绑定阶段把发现的信息记录在执行计划旁的 `Bindings` 中，执行计划本身保持原样。随后 `RunBoundPasses` 依据这些事实运行若干趟处理，它们可以重排、合并或删除节点。每一趟都定义在它所重写的操作旁边。一趟自输入向上的扫描会运行这些重写并推导每个节点的输出，因此在某个节点上执行的重写，看到的是其下方的一切都已是最终形态，而其上方还没有任何内容被推导出来。

---

## `FROM` {#from}

代码：`operations/scan.cc`、`/src/trace_processor/core/exec/dataframe_scan.cc`

每个数据源都由 `DataframeScan` 以 dataframe 的形式读取。

### 表

当 `FROM` 指向一个已定稿的 dataframe（例如 `slice`、`sched` 或任何 `PERFETTO TABLE`）时，pipeline 会直接读取其存储：

- 只读取存活的列，并跳过隐藏列。
- 列缓冲区是被引用的，而不是被复制的。
- 已排序的列会被声明为已排序，因此在这些列上的 `ORDER BY` 没有开销。
- 以 `0, 1, 2, ...` 形式存储的 `id` 列能让 `TREE ACCUMULATE` 跳过其哈希表。

### 视图与子查询

视图、虚拟表或 `SELECT` 子查询的列名与类型在 pipeline 编译时由 `RelationAnalyzer` 推导得出。如果它只是选取并重命名某个已定稿表的列，该表就会像上面那样被直接读取。

否则 SQLite 会把它执行一次，由 `__intrinsic_dataframe_agg` 把返回的行收集成一个 dataframe，再交给 pipeline：

```sql
SELECT __intrinsic_dataframe_agg('<col_0>,<col_2>', "<col_0>", "<col_2>")
FROM <source>
```

这里只列出存活的列，因此 SQLite 可以跳过其余列的计算。

---

## `INTERVAL INTERSECTION OF`

代码：`/src/trace_processor/core/exec/interval_intersect.cc`

`INTERVAL INTERSECTION OF` 会读完全部操作数，然后才产出任何输出。

### 1. 读取操作数

每个操作数都是一个侧 pipeline：

- `ts` 和 `dur` 会被转换为 64 位整数。各 `PER` 列会被统一转换成一个类型；允许字符串。
- 如果行尚未处于该状态，则会按 `PER` 列分组，并在每组内按 `ts` 排序。
- `ts` 或 `dur` 为 `NULL` 的行会被跳过。负的边界值，或者发生溢出的 `ts + dur`，都属于错误。
- 只保留会被下游读取的操作数列。

所有操作数都在一个共享的 `GroupTable` 中为各自的 `PER` 键编号，因此同一个键在所有地方都持有相同编号。不存在于任何更早操作数中的键不可能产生区域，因此其行在读取时即被丢弃。读取某个 lane 的过程中，运算符会记录该 lane 内是否有任何两个区间相互重叠。

### 2. 对每个键求交

只有键数最少的那个操作数中的键才可能开启一个区域，因此运算符只遍历这些键，并跳过任何其他操作数缺失的键。对每个键：

- **无重叠：**如果任何操作数的区间都不相互重叠，一趟扫描会同时推进所有操作数，把区域直接写入输出。
- **有重叠：**否则由各操作数逐一收窄区域，最小的最先。每一步都使用 `IntervalIntersector`，它会依据操作数本身以及剩余区域的数量，在线性扫描、二分查找或区间树之间做出选择。

区域存储为存放边界和操作数行的平坦数组，因此没有任何区域需要单独分配内存。

### 3. 输出

区域按每批最多 2048 个输出。每个批次先放区域的 `ts` 和 `dur`，然后是各操作数被保留的列，其值复制自区域所来自的行。

### 名称

编译器把区域的 `ts` 和 `dur` 放在行的最前面，然后是所有操作数列。当某个操作数列只应通过其别名才能找到时，它会被标记为 `qualified_only`：包括操作数自身的 `ts` 和 `dur`，以及除第一个外各操作数的 `PER` 列。其余所有列同样能通过裸名称找到。

---

## `INTERVAL FLATTEN`

代码：`/src/trace_processor/core/exec/interval_flatten.cc`

输入按 `PER` 键分组，并在每组内按 `ts` 排序；只有在需要时才会插入排序。随后 `IntervalFlatten` 流式地扫过排序后的行。

一个最小堆跟踪各活跃区间的结束时刻。每个区间把它所在行的聚合状态保存在一个槽位中；一批 segment 的聚合结果由各 segment 中存活的槽位共同聚合而成，因此单个 segment 不必重新扫描全部活跃区间。只要输入中尚未出现 `NULL`，支持移除值的聚合函数（计数与求和都属于此类）就会在每个区间首个 segment 处加入其槽位，在其结束处移除，并维护运行中的总计；否则（例如 `MIN` 和 `MAX`），每个槽位会被合并进一棵覆盖该批次全部 segment 的树。求和会记录自己是否加入过任何值，因此仅对 `NULL` 值求和的结果仍为 `NULL`。

位于同一时刻的各个点会被收集起来，等到所有以该时刻为起点的行都读完后一起输出。它们的总计包含在该时刻活跃的区间，但不会延续到下一个 segment。

segment 以大小有界的批次输出；内存中只保留活跃区间。端点与求和运算都带溢出检查。

未使用的聚合会被裁剪，但即使一个不剩该阶段也会保留，因为它仍然决定输出的行。

---

## `INTERVAL FILL GAPS`

代码：`/src/trace_processor/core/exec/interval_fill_gaps.cc`

背景是一个侧 pipeline，会在输入之前被完整读取。背景与输入都按 `PER` 键分组并按 `ts` 排序，两者共有的列会被转换成同一类型。

`IntervalFillGaps` 流式地扫过输入，原样输出每一行，并为背景中没有被同一 lane 内任何输入行覆盖的每一段添加一个填充行。它按以下两种方式之一运行：

- **背景带有 `PER` 列，或者双方都没有。**每个背景行属于一个 lane。没有任何输入的 lane 会被整体填充。
- **背景没有 `PER` 列而输入有。**每个输入 lane 都对照整个背景进行填充。

填充行的每个列取自背景中同名的列；若没有，则取该 lane 的 `PER` 值；再没有则为 `NULL`。输入的 `dur` 为 `-1` 表示永久持续。填充行的时长永不为零，输出行也没有特定顺序。

---

## `TREE ACCUMULATE`

代码：
- `/src/trace_processor/core/exec/tree_number_nodes.cc`
- `/src/trace_processor/core/exec/tree_order.cc`
- `/src/trace_processor/core/exec/tree_accumulate.cc`

一个 `TREE ACCUMULATE` 阶段会被降级为三个步骤：节点编号、行排序和累加。

### 1. 节点编号：`TreeNumberNodes`

树运算符需要按节点保存状态。`id` 可以是任意的 64 位整数或字符串，因此直接以它为下标的数组可能会极其庞大，或者根本无法建立。

`TreeNumberNodes` 向每个批次追加两个稠密的 `Uint32` 列：一个是该行的节点编号，按首次见到的顺序依次赋为 `0, 1, 2, ...`；另一个是其父节点的编号，根节点则为 `kNoNode`。后续运算符只读取这两列，因此所有按节点分配的数组长度都与输入行数相同。

它有三条路径：

1. **`Id` 列：**当读取的 dataframe 未经过滤、其 `id` 以 `Id` 类型存储、`parent_id` 为 `Uint32`，且每个父节点都先于其子节点出现时，编号直接从这些列复制而来。
2. **稠密整数：**只要见到的 `id` 仍是 `0, 1, 2, ...` 且每个父节点都已被见过，每个 `id` 本身就是自己的编号，不做任何哈希。
3. **哈希表：**从第一个打破上述条件的 `id` 或任何字符串 `id` 开始，由一个 `FlatHashMap` 把 id 映射为编号。此前见过的 id 会先被加入其中。

### 2. 行排序：`TreeChildFirst` 与 `TreeParentFirst`

行到达的顺序必须保证一个节点所依赖的值在它之前已处理完毕。这并不要求严格的深度优先顺序：子树之间可以交错，因为累加器为每个节点各自维护一个总计值。

#### `UP`：`TreeChildFirst`

`UP` 要求每个子节点先于其父节点出现。某一行的子节点可能直到最后才到达，因此 `TreeChildFirst` 会读完全部行之后才开始输出：

- 它会记录输入是否已经是子节点在前，或者已经是父节点在前。
- **子节点在前：**按原到达顺序输出各行。
- **父节点在前：**按相反顺序输出。
- **两者都不是：**基于节点编号构建子节点列表，从根出发遍历得到父节点在前的顺序，校验每一行都被访问到（这能捕获环），最后把结果反转。

#### `DOWN`：`TreeParentFirst`

`DOWN` 要求每个父节点先于其子节点出现。某一行只要其父节点已经输出就可以立即输出，因此 `TreeParentFirst` 是流式的：

- 一个位向量标记已经输出的节点。
- 根行，以及父节点已输出的行，会直接通过。如果批次中的每一行都能通过，该批次会被原样转发，不进行复制。
- 先于父节点到达的行会被复制到一旁，挂到其父节点的等待列表上。当父节点被输出后，它等待中的子节点以及这些子节点各自等待中的后代会随之输出。
- 只有先于父节点到达的行才会消耗内存或引发复制。

### 3. 累加：`TreeAccumulateUp` 与 `TreeAccumulateDown`

阶段中的所有聚合由同一个流式运算符计算，它使用执行器共享的聚合函数（`/src/trace_processor/core/exec/aggregate_function.h`），与 `INTERVAL FLATTEN` 和 `AGGREGATE` 所用的相同：

- 被聚合的列会被转换为平坦的 `Int64`。求和会跳过 `NULL` 并记录自己是否加入过任何值，因此未加入任何值的求和结果为 `NULL`。溢出会被作为错误报告。
- 每个节点的聚合状态存放在同一个按节点编号索引的向量中。对每个批次，先把每一行加入其节点的状态，然后按行序沿批次的边界合并各状态：
  - **向上：**子节点先到，因此当一个节点到达时，它的所有后代都已合并进它。随后它被合并进其父节点。
  - **向下：**父节点先到，因此当一个节点到达时，它的父节点已覆盖所有祖先。父节点被合并进它。

### 4. 多个 `TREE ACCUMULATE` 阶段

- 只要 `id` 和 `parent_id` 仍是相同的列，后续阶段就会复用第一个阶段的节点编号。
- 连续两个 `UP` 阶段或连续两个 `DOWN` 阶段，会复用第一个阶段的行顺序。
- 在 `UP` 与 `DOWN` 之间切换时，编号保留，行重新排序。
- 两个方向相反的阶段，如果后一个不读取前一个所计算的任何内容，就会按行当前遍历树的既有顺序运行，因此其中只有一个需要重排行（`ReorderTreeFold`）。`GRAPH ... TREE` 以父节点在前的顺序输出行，因此在它上面，写在 `UP` 之后的 `DOWN` 会先运行。

---

## `GRAPH ... TREE`

代码：
- `/src/trace_processor/core/exec/graph_tree.cc`
- `/src/trace_processor/util/graph.cc`

`NODES`、`EDGES` 和 `FROM` 各是一个侧 pipeline，其中的 id 都会被转换为 `Int64`。`GraphTree` 会读完全部三者之后才开始输出：

- 节点行保存在 `RowStore` 中，每个节点按其所在行编号。接近稠密的 id 通过数组查找，其余的通过 `FlatHashMap` 查找。
- 边按源节点分组，并保持到达顺序。
- 搜索树或支配树在这些编号上运行，从各种子（seed）出发，顺序与其到达顺序一致。支配树会从一个额外的节点生长出来，该节点到每个种子都有一条边，而它本身不会出现在输出中。

种子和边的顺序决定了在同样优秀的父节点之间如何挑选，因此降级过程不会添加任何会重排这些输入的操作。

输出时父节点在前，汇集每个节点的行，并附上其父节点的 `id` 以及 `TreeNumberNodes` 本会追加的那两个 `Uint32` 列。降级过程把这记录为 `id` 和 `parent_id` 的一次 `DOWN` 遍历，因此其后的 `TREE ACCUMULATE DOWN` 不再需要其他运算符，而 `UP` 只需把行反转。

---

## `AGGREGATE`

代码：`/src/trace_processor/core/exec/hash_aggregate.cc`

`AGGREGATE` 被降级为一个 `HashAggregate`，它会读完全部输入之后才开始输出。`GroupTable` 对每一行的键做哈希以找到所属分组，并按首次见到的顺序为分组编号。任意宽度的整数键按值判等，字符串按其驻留（intern）id 判等，各 `NULL` 彼此相等。每个分组的聚合状态紧挨着其键存放，每读入一行就立即加入对应状态，因此内存随分组数而非行数增长。最后，分组按首次被见到的顺序输出。如果输入本身已按键排序，输出也会被声明为已排序。

没有 `GROUP BY` 时只有一个分组，即使输入没有任何行，这个分组也会被输出。

未使用的聚合会被裁剪，但阶段本身总会保留，因为它决定输出的行。

编译器会把行替换为各键、随后是各聚合，并清空所有别名。

---

## `WHERE`

代码：`operations/where.cc`、`/src/trace_processor/core/exec/filter.cc`

`WHERE` 被降级为一个流式的 `Filter`。每个比较的字面量或 `IN` 列表会在降级期间一次性转换为其所属列的类型，并与执行计划存放在一起（`PhysicalPlan::filter_values()`）。字符串会被转换为它在字符串池中的 id，因此 `=` 和 `!=` 比较的是 id，而没有任何行持有的字符串将匹配不到任何行。在降级期间做转换是安全的，因为执行计划是在各输入绑定之后、针对每个游标各自降级的，此时它们持有的所有字符串都已在池中。类型未知的列会先被转换为字面量的类型；只要有一个字面量是字符串，就转换为字符串。`IS [NOT] NULL` 可以读取任何列，包括逐行携带类型的列。`BETWEEN` 是两个比较。`Filter` 使用与 dataframe 自身过滤器相同的比较内核，并收窄每个批次的行选择集，因此不复制任何内容。

一趟绑定后遍历（`SearchScans`）会把 `WHERE` 直接读取的每个扫描中可借助搜索回答的条件移入该扫描，其选择方式与 dataframe 自身的规划器一致（`SortedFilterStrategy`、`GetBestIndexForFilterSpecs`）：

- 如果某个条件不可能匹配任何行（例如字符串池中不存在的字符串），扫描会变成一个 `EmptySource`。
- 否则，作用在无 null 的已排序列上的条件会变成 `SortedScan`：二分查找，或 SetId 与小值查找，它们把行收窄到一个仍保持表序的范围内。
- 否则，作用在索引前导列上的等值条件会变成 `IndexScan`，它按索引顺序读取行，因此在其之后不再假定任何表序。表的索引在执行计划加载时被发现，与其列的发现方式相同，因此在 pipeline 编写之后才创建的索引依然会被使用。

扫描之后的 `Filter` 负责测试其余条件，而一个没有任何条件可测的 `WHERE` 会被丢弃。只有作用在按表原始存储方式读取的列上的条件才会走搜索；而作用在需要先做转换的列上的条件则留给 `Filter`。

---

## `DISTINCT`

代码：`operations/distinct.cc`、`/src/trace_processor/core/exec/distinct.cc`

`DISTINCT` 被降级为一个流式的 `Distinct`。一个 `GroupTable` 保存目前保留的行的键；键已存在的行会通过收窄行选择集被丢弃。内存随互异行数增长，行保持原有顺序。一行最多可以有 64 列。

---

## `ORDER BY`

代码：`/src/trace_processor/core/exec/sort.cc`

`Sort` 会读完全部行之后才开始输出。它把每一行的键编码成一条可按字节比较的定宽记录，依据这些记录对行索引排序，然后按该顺序把行复制出来。

字符串键会被编码为它在所有行的字符串中的排名，因此比较依据是内容，而不是它在字符串池中的 id。排名只有等到所有行都到齐后才能确定，因此字符串键在排序前一刻才被编码。类型未知的来自 SQLite 的键会被转换为整数。

降级过程会跟踪行当前所处的顺序。单个升序键如果表本身已按其排好序（例如 `slice` 上的 `ts`），就不需要 `Sort`。如果一个 `Sort` 的顺序没有任何下游读取（因为更晚的阶段会先排序、分组或遍历树），它会被移除。排序之后树序会被遗忘，因此其后的 `TREE ACCUMULATE` 会重排行，但保留节点编号。

---

## `LIMIT`

代码：`operations/limit.cc`、`/src/trace_processor/core/exec/limit.cc`

`LIMIT` 被降级为一个流式的 `Limit`，它收窄每个批次的行选择集。它会关闭其前面任何未完成的 `Sort`，因此 `ORDER BY` 永远不会从 `LIMIT` 之前被移除。一旦保留了 `count` 行，它就不再接受输入，因此位于它之前的任何运算符都不会读到超出所需范围的行。保留下来的行保持原有顺序，因此一切已知的排列方式都能保留下来。

---

## `SELECT`、`EXTEND`、`DROP`、`RENAME`、`SET` 和 `AS`

代码：`/src/trace_processor/perfetto_sql/pipeline/operations/projection.cc`

这些阶段只在 pipeline 编译期间存在。它们不添加任何运算符，也不复制任何数据。

编译器把当前行维护为一个 `RowColumn` 列表：一个名称、持有其值的 `ColumnId`，以及它是否为 `qualified_only`（意为只有别名才能找到它）。旁边是一份别名列表，每个别名都是该行在被设置那一刻的副本。

- `DROP` 移除裸名称能找到的该名称的列，以及该名称的任何别名。
- `RENAME` 修改某个列的名称。
- `SET` 让某个列指向另一个 `ColumnId`，并移除该名称的任何别名。
- `EXTEND` 在末尾追加列。裸 `*` 会被拒绝。
- `AS` 从行中丢弃 `qualified_only` 的列，并把所有别名替换为针对剩余行的别名。
- `SELECT` 用列出的列替换行，并清空所有别名。裸 `*` 只取不是 `qualified_only` 的列。它列出的每一个列（包括来自 `<alias>.*` 的列）之后都可以通过裸名称找到。

`AGGREGATE`、`INTERVAL FLATTEN` 和 `INTERVAL FILL GAPS` 也会重建行与别名。

编译结束时，行中不是 `qualified_only` 的列成为 pipeline 的输出。裁剪从这些列出发，降级过程把每一列映射到最终批次的某个列。重排、复制、重命名或删除列从不会复制数据。
