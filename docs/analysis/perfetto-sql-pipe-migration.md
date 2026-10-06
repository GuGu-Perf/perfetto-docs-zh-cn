# 迁移到 PerfettoSQL pipe 语法

本指南面向已经了解 PerfettoSQL 的读者，介绍我们为什么引入 pipe 语法、它与现有宏和虚拟表有何不同，以及如何迁移现有查询。

> **警告:** pipe 语法是**实验性的、不稳定的**。请**不要**在仪表盘、脚本或生产查询中依赖它。任何内容都可能且必将在毫无预兆的情况下损坏。在 PerfettoSQL 标准库之外，你必须在自己的连接上执行 `PERFETTO PRAGMA pipelines = 1;` 才能启用它。

相关页面：

- [PerfettoSQL pipe 语法入门指南](/docs/analysis/perfetto-sql-pipe-getting-started.md)
- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)

---

## 为什么需要 pipe 语法？

用标准 SQLite 编写 trace 分析查询时，会遇到几个反复出现的痛点：

1. **表宏与虚拟表不擅长组合。**区间交集与树遍历这类操作并不存在于 SQL 之中。Perfetto 通过 `SPAN_JOIN` 等 SQLite 虚拟表，或者用 `_interval_intersect!`、`_graph_aggregating_scan!`、`_callstacks_self_to_cumulative!` 等宏封装的 C++ 表函数来提供这些能力。把其中两三个串联起来，就需要深层嵌套的子查询，或者一串中间视图和中间表。
2. **手工搭建 `id` 通道与反向 JOIN。**`_interval_intersect!` 只返回 `ts`、`dur`、`id_0`、`id_1` 等列。要读取输入中的其他列，每个输入都必须有 `id` 列，或者包一层 `_ii_subquery!`，随后还要按 `id_0`、`id_1` 等对每个输入表各做一次 `JOIN`。
3. **为树手工建立索引和临时表。**要用 `_graph_aggregating_scan!` 沿调用栈或堆图向上求和，需要先物化一张原始表，在 `parent_id` 上创建 `PERFETTO INDEX`，以免查找叶子的 `NOT IN` 查询退化为平方复杂度，然后运行扫描，最后再按 `id` 把结果 JOIN 回原始表。
4. **难读的宏错误与 SQLite 虚拟表开销。**PerfettoSQL 宏是文本替换，因此参数里的一处错误会产生指向展开后宏体内部的 SQLite 错误。在运行时，SQLite 与自定义运算符之间传递行，会迫使每一行都经过 SQLite 逐行处理的虚拟表接口。

### pipe 带来了什么变化

PerfettoSQL pipe 语法使用线性的 `|>` 阶段，设计上参考了 [GoogleSQL pipe 语法](https://cloud.google.com/bigquery/docs/pipe-syntax)，并在列式批处理执行器上运行这些阶段：

- **`INTERVAL INTERSECTION OF` 和 `TREE ACCUMULATE` 是语言的一部分。**它们会自动携带输入列。不再需要 `id_0`/`id_1` 反向 JOIN、`_ii_subquery!` 或 `parent_id` 索引。
- **直接扫描 dataframe。**当 pipeline 读取 `slice` 或 `sched` 这类已定稿的 `PERFETTO TABLE` 时，会直接在 C++ 中读取该表的列式存储，而不经过 SQLite。
- **编译期列检查与裁剪。**编译器会提前检查列名和类型，出错时指向出错的 token，并在执行前丢弃未使用的列和未使用的树聚合。

---

## 启用 pipe 语法

在 `trace_processor_shell`、Perfetto UI、Python API 和 diff 测试中，可以在自己的连接上通过以下语句启用 pipe 语法：

```sql
PERFETTO PRAGMA pipelines = 1;
```

可以用 `PERFETTO PRAGMA pipelines = 0;` 再次关闭它。在 PerfettoSQL 标准库内部，无需该 pragma，pipeline 默认启用。

---

## 什么放在 SQL 里，什么放在 pipeline 里？

pipe 语法正在逐步构建中。目前，pipeline 支持两个 trace 运算符——`INTERVAL INTERSECTION OF` 和 `TREE ACCUMULATE`，以及六个列重塑阶段：`SELECT`、`EXTEND`、`DROP`、`RENAME`、`SET` 和 `AS`。

如今迁移查询时，请按以下方式在 SQL 与 pipeline 之间分工：

| 任务 | 目前应在哪里完成 |
| :--- | :--- |
| 过滤行、标准 `JOIN`、`GROUP BY`、窗口函数与计算表达式 | 放在 `FROM (SELECT ...)` 源子查询内，或者对得到的 `PERFETTO TABLE` 执行标准 SQL 查询。 |
| 对两张及以上的表求时间区间交集 | 在 pipeline 开头使用 `INTERVAL INTERSECTION OF (...) [PER ...]`。 |
| 沿父子树向上或向下求和 | 使用 `\|> TREE ACCUMULATE UP \| DOWN SUM(col) AS total` 阶段。 |
| 挑选、丢弃、重命名或调换列 | 使用 `\|> SELECT`、`\|> EXTEND`、`\|> DROP`、`\|> RENAME`、`\|> SET`、`\|> AS` 阶段。 |
| 对最终输出排序或限制行数 | 对 pipeline 创建的 `PERFETTO TABLE` 执行带 `ORDER BY` 或 `LIMIT` 的 `SELECT`。 |

> **注意:** pipeline 可以作为顶层语句运行，也可以作为 `CREATE [OR REPLACE] PERFETTO TABLE ... AS <pipeline>` 的主体。它尚不能用作 `CREATE PERFETTO VIEW`、`CREATE PERFETTO FUNCTION` 或 `WITH` CTE 的主体。

---

## 迁移区间交集

用 `INTERVAL INTERSECTION OF` 替换 `_interval_intersect!` 和 `SPAN_JOIN`。

### 迁移前：`_interval_intersect!`

```sql
INCLUDE PERFETTO MODULE intervals.intersect;

CREATE PERFETTO TABLE _estimates_w_tasks_attribution AS
SELECT ii.ts, ii.dur, ii.cpu, uw.estimated_mw, s.utid
FROM _interval_intersect!(
  (
    _ii_subquery!(_unioned_wattson_estimates_mw),
    _ii_subquery!(_wattson_task_slices)
  ),
  (cpu)
) AS ii
JOIN _unioned_wattson_estimates_mw AS uw
  ON uw._auto_id = id_0
JOIN _wattson_task_slices AS s
  ON s._auto_id = id_1;
```

### 迁移后：`INTERVAL INTERSECTION OF`

```sql
CREATE PERFETTO TABLE _estimates_w_tasks_attribution AS
INTERVAL INTERSECTION OF (
  _unioned_wattson_estimates_mw AS estimate,
  _wattson_task_slices AS task
) PER cpu
|> SELECT ts, dur, cpu, estimate.estimated_mw, task.utid;
```

### `INTERVAL INTERSECTION OF` 迁移检查清单

1. **去掉反向 JOIN 和 `_ii_subquery!` 包装。**`_interval_intersect!` 要求每个输入都有 `id` 列，好让你能把 `id_0` 和 `id_1` JOIN 回输入表。`INTERVAL INTERSECTION OF` 会自动携带操作数的列，只要求输入带有 `ts` 和 `dur`。只有当你确实需要在输出中以 `alias.id` 的形式暴露 SQLite 的 `_auto_id` 时，才保留 `_ii_subquery!`。
2. **给每个操作数一个互不相同的别名。**写成 `INTERVAL INTERSECTION OF (a AS x, b AS y)`。在子查询上省略 `AS <alias>`，或者在不同操作数之间复用同一别名，都是编译错误。
3. **用 `PER` 取代分区列列表或 `PARTITIONED`。**写成 `PER cpu` 或 `PER utid, track_id`。对于不分区的交集，直接省略 `PER` 即可。
4. **给操作数列加限定名，而区域的 `ts`、`dur` 和 `PER` 列保持裸名。**裸名 `ts` 和 `dur` 是相交区域的起点和时长，裸名 `cpu` 是匹配行共享的分区键。其余所有操作数列——包括每个操作数原始的、未经裁剪的 `x.ts` 和 `x.dur`——都必须用操作数的别名加以限定，例如 `x.utid` 或 `y.freq`。务必在 `INTERVAL INTERSECTION OF` 之后紧跟 `|> SELECT ...`；如果没有 `SELECT` 阶段，每个操作数的 `ts` 和 `dur` 都会留在输出行中，从而产生重复的列名。
5. **留意行为差异。**
   - **`dur IS NULL` 或 `ts IS NULL` 的行会被跳过。**如果输入表用 `lead(ts) OVER (...) - ts AS dur` 计算时长，其最后一行就会出现 `dur IS NULL`。`_interval_intersect!` 会把 `NULL` 时长强制转换为 `0`；`INTERVAL INTERSECTION OF` 则会跳过 `ts` 或 `dur` 为 `NULL` 的行。
   - **`ts` 或 `dur` 为负数会被视为错误。**`dur = -1` 的未完成 slice 会被拒绝，报错为 `ts or dur is below zero`。请在输入中用 `WHERE dur >= 0` 或 `WHERE dur > 0` 过滤。
   - **操作数内部区间重叠也没问题。**当区间在单张表内重叠时，`SPAN_JOIN` 会产生错误的结果，而 `INTERVAL INTERSECTION OF` 会自动处理重叠区间。

---

## 迁移树聚合

用 `TREE ACCUMULATE UP` 和 `TREE ACCUMULATE DOWN` 替换 `_graph_aggregating_scan!`、`_callstacks_self_to_cumulative!`，以及用递归 CTE 实现的子树和或路径和。

### 迁移前：`_graph_aggregating_scan!`

```sql
CREATE PERFETTO TABLE _heap_graph_class_tree_cumulatives AS
SELECT
  a.id,
  a.cumulative_count,
  a.cumulative_size
FROM _graph_aggregating_scan!(
  (
    SELECT id AS source_node_id, parent_id AS dest_node_id
    FROM _heap_graph_class_tree
    WHERE parent_id IS NOT NULL
  ),
  (
    SELECT
      id,
      self_count AS cumulative_count,
      self_size AS cumulative_size
    FROM _heap_graph_class_tree
    WHERE id NOT IN (
      SELECT parent_id FROM _heap_graph_class_tree WHERE parent_id IS NOT NULL
    )
  ),
  (cumulative_count, cumulative_size),
  (
    WITH agg AS (
      SELECT
        t.id,
        SUM(t.cumulative_count) AS child_count,
        SUM(t.cumulative_size) AS child_size
      FROM $table t
      GROUP BY t.id
    )
    SELECT
      a.id,
      a.child_count + r.self_count AS cumulative_count,
      a.child_size + r.self_size AS cumulative_size
    FROM agg a
    JOIN _heap_graph_class_tree r USING (id)
  )
) AS a;
```

### 迁移后：`TREE ACCUMULATE UP`

```sql
CREATE PERFETTO TABLE _heap_graph_class_tree_cumulatives AS
FROM _heap_graph_class_tree
|> TREE ACCUMULATE UP
  SUM(self_count) AS cumulative_count,
  SUM(self_size) AS cumulative_size;
```

### `TREE ACCUMULATE` 迁移检查清单

1. **删除中间原始表、`parent_id` 索引和反向 JOIN。**可以直接从宏或子查询接入 pipeline：
   ```sql
   CREATE PERFETTO TABLE _linux_perf_callstacks AS
   FROM _callstacks_for_callsites!((SELECT callsite_id FROM perf_sample))
   |> TREE ACCUMULATE UP SUM(self_count) AS cumulative_count;
   ```
   `TREE ACCUMULATE` 会保留输入行的所有列，并在末尾追加 `cumulative_count`。不需要把结果 `JOIN` 回输入表，也不需要在 `parent_id` 上创建 `PERFETTO INDEX`。
2. **确保数据源具有 `id` 和 `parent_id` 列。**`TREE ACCUMULATE` 会在当前行中查找裸名 `id` 和 `parent_id`。根节点必须满足 `parent_id IS NULL`。
3. **总计总是包含节点自身。**`TREE ACCUMULATE UP SUM(x) AS total` 把节点自身的 `x` 与其全部后代的 `x` 相加；`TREE ACCUMULATE DOWN SUM(x) AS path` 把节点自身的 `x` 与其全部祖先的 `x` 相加。迁移手写的 `_graph_aggregating_scan!` 查询时，请检查旧的步骤查询是否忘记为非叶节点加上 `r.self_*`。
4. **如有需要，在公开表上保留 `ORDER BY id`。**`TREE ACCUMULATE UP` 按子节点在前的顺序产出行，`DOWN` 按父节点在前的顺序产出行。如果某个公开的标准库表或测试期望行按 `id` 排序，请用 `SELECT ... ORDER BY id` 查询生成的表。

---

## 常见陷阱

### 1. 每个源列都需要有效且互不相同的名称

当 pipeline 从 SQL 子查询读取数据时，编译器会在列裁剪运行之前检查该子查询返回的每一列，包括后续阶段会丢弃的列：

- **未加别名的表达式会失败：**
  ```sql
  -- ERROR: expected every column to have a valid name, but '1 + 1' is not one:
  -- give it one with AS
  FROM (SELECT id, parent_id, 1 + 1 FROM tree)
  |> TREE ACCUMULATE UP SUM(id) AS total
  |> SELECT id, total;
  ```
- **子查询中出现重复列名会失败：**SQLite 会把 `SELECT 1 AS x, 2 AS x` 中的第二个 `x` 重命名为 `x:1`。pipeline 编译器会以如下信息拒绝：`expected distinct column names, but there are two named 'x', which SQLite renamed to 'x' and 'x:1'`。

### 2. 在 `FROM` 中把 `WHERE` 和 `JOIN` 括在圆括号里

pipeline 的 `FROM` 子句只接受表名或视图名，或者带圆括号的 `SELECT` 子查询：

```sql
-- ERROR:
FROM slice WHERE dur > 0 |> TREE ACCUMULATE UP SUM(dur) AS total;

-- OK:
FROM (SELECT id, parent_id, dur FROM slice WHERE dur > 0)
|> TREE ACCUMULATE UP SUM(dur) AS total;
```

### 3. 表别名会在绑定那一刻对行做快照

在 `DROP`、`RENAME`、`SET`、`EXTEND` 等 pipeline 阶段中，表别名会记住别名创建时行所具有的列：

- `FROM t |> DROP x |> SELECT t.x` 仍然有效，可以找回 `x`。
- `FROM t |> RENAME x AS y |> SELECT t.x` 仍以 `t.x` 访问该列，而裸名 `y` 以新名称访问它。
- `|> SELECT ...` 会构建一个新行并清除之前的所有别名。
- `|> AS u` 会用 `u` 替换之前的所有别名，并对当前行做快照。
