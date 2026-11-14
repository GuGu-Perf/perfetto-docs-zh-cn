# 迁移到 PerfettoSQL pipe 语法

本指南面向已经了解 PerfettoSQL 的读者，介绍 pipe 语法为什么存在、它与所取代的宏和虚拟表有何不同，以及如何把查询迁移到 pipe 语法。

> **警告:** pipe 语法是**实验性的、不稳定的**。请**不要**在仪表盘、脚本或生产查询中依赖它。任何内容都可能且必将在毫无预兆的情况下损坏。在 PerfettoSQL 标准库之外，你必须在自己的连接上执行 `PERFETTO PRAGMA pipelines = 1;` 才能启用它。

相关页面：

- [PerfettoSQL pipe 语法入门指南](/docs/analysis/perfetto-sql-pipe-getting-started.md)
- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)

---

## 为什么需要 pipe 语法？

用标准 SQLite 编写 trace 分析查询时，会遇到几个反复出现的痛点：

1. **宏与虚拟表无法组合。**SQL 本身没有区间交集和树遍历，因此 Perfetto 通过 `SPAN_JOIN` 等 SQLite 虚拟表，或者用 `_interval_intersect!`、`_graph_aggregating_scan!` 等宏封装的 C++ 表函数来提供这些能力。把其中两三个串联起来，就需要深层嵌套的子查询，或者一连串中间表。
2. **`id` 上的反向 JOIN。**`_interval_intersect!` 只返回 `ts`、`dur`、分区列以及 `id_0`、`id_1` 等。要读取其他任何列，每个输入都必须有 `id` 列，或者包一层 `_ii_subquery!`，而且结果还需要 JOIN 回每个输入。
3. **为树建立索引和临时表。**要用 `_graph_aggregating_scan!` 沿调用栈或堆图向上求和，就得先保存一张表、在 `parent_id` 上建索引，让查找叶子的 `NOT IN` 查询不至于退化为平方复杂度，然后运行扫描，最后再按 `id` 把结果 JOIN 回去。
4. **难懂的报错与缓慢的逐行执行。**宏是文本替换，参数里的一处错误就会产生指向展开后宏体内部的 SQLite 错误。运行时，每一行都要逐个通过 SQLite 的虚拟表接口。

### pipe 带来了什么变化

pipe 语法把 `|>` 阶段串联起来，做法与 [GoogleSQL pipe 语法](https://cloud.google.com/bigquery/docs/pipe-syntax) 一致，并在 C++ 实现的列式执行器上运行这些阶段：

- **区间与树操作是语言的一部分。**`INTERVAL INTERSECTION OF` 和 `TREE ACCUMULATE` 等阶段会携带输入列，因此不需要 `id_0`/`id_1` 反向 JOIN、`_ii_subquery!` 包装或 `parent_id` 索引。
- **直接读取表。**pipeline 读取 `slice`、`sched` 或任意 `PERFETTO TABLE` 时，直接访问其列式存储，不经过 SQLite。
- **错误提前暴露。**列名和类型在任何代码运行之前就会得到检查，出错时会指向出错的 token。未使用的列和聚合会在执行前被丢弃。

---

## 启用 pipe 语法

在 `trace_processor_shell`、Perfetto UI、Python API 和 diff 测试中，通过以下语句启用 pipe 语法：

```sql
PERFETTO PRAGMA pipelines = 1;
```

用 `PERFETTO PRAGMA pipelines = 0;` 可以再次关闭它。标准库则始终可以使用 pipeline。

---

## 什么放在 SQL 里，什么放在 pipeline 里？

pipeline 目前尚不能覆盖 SQL 的全部能力。请按以下方式分工：

| 任务 | 目前应在哪里完成 |
| :--- | :--- |
| 用列与数值的比较（以 `AND` 连接）过滤行 | `\|> WHERE dur > 0 AND depth = 0` |
| 其他任何过滤、`JOIN`、窗口函数与计算表达式 | 放在 `FROM (SELECT ...)` 子查询内，或对 pipeline 保存的表执行 SQL。 |
| 对两张及以上的表求区间交集 | `INTERVAL INTERSECTION OF (...) [PER ...]` |
| 统计或求和一组区间内的并发活动 | `\|> INTERVAL FLATTEN [PER ...] AGGREGATE ...`；参见[示例](/docs/analysis/perfetto-sql-pipe-getting-started.md#flattening-overlapping-intervals-interval-flatten)。 |
| 填补区间之间的空隙 | `\|> INTERVAL FILL GAPS WITH <background> [PER ...]` |
| 沿树向上或向下聚合 | `\|> TREE ACCUMULATE UP \| DOWN ...` |
| 按组使用 `COUNT(*)`，以及对整数列使用 `SUM`、`MIN` 和 `MAX` | `\|> AGGREGATE ... [GROUP BY ...]` |
| 其他任何聚合 | 在 SQL 中完成。 |
| 去除重复行 | `\|> DISTINCT` |
| 挑选、丢弃、重命名或调换列 | `\|> SELECT`、`EXTEND`、`DROP`、`RENAME`、`SET` 和 `AS` |
| 按数值列排序 | `\|> ORDER BY col [DESC]` |
| 按字符串或表达式排序，或使用 `LIMIT` | 对 pipeline 保存的表执行 SQL。 |

pipeline 可以独立作为一条语句，也可以作为 `CREATE [OR REPLACE] PERFETTO TABLE` 的主体。它尚不能作为视图、函数或 `WITH` 子句的主体。

---

## 迁移区间交集

用 `INTERVAL INTERSECTION OF` 替换 `_interval_intersect!` 和 `SPAN_JOIN`。

### 迁移前：`_interval_intersect!`

```sql
INCLUDE PERFETTO MODULE intervals.intersect;
INCLUDE PERFETTO MODULE wattson.utils;

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

1. **去掉反向 JOIN 和 `_ii_subquery!` 包装。**输入只需要 `ts` 和 `dur`，其余所有列都会自动携带。
2. **给每个输入一个自己的别名：**写成 `INTERVAL INTERSECTION OF (a AS x, b AS y)`。子查询不带别名，或两个输入共用一个别名，都会报错。
3. **用 `PER` 指定分区：**写成 `PER cpu` 或 `PER utid, track_id`。省略 `PER` 则对所有内容求交集。
4. **裸名代表相交区域。**`ts` 和 `dur` 是重叠区域，`cpu` 是共享的 `PER` 值。输入自身的边界是 `x.ts` 和 `x.dur`。其他列可以用裸名书写，如 `utid`；但若两个输入有同名的列，就要写成 `x.utid`。如果两个输入的列名相同，请以一个为每个副本分别命名的 `|> SELECT` 结尾，否则结果无法保存为表。
5. **留意行为差异。**
   - **`NULL` 边界会被跳过。**用 `lead(ts) OVER (...) - ts` 计算的 `dur` 在最后一行是 `NULL`。`_interval_intersect!` 把它当作 `dur = 0` 处理，而 pipeline 会跳过该行。
   - **输入内部的区间可以重叠。**此时 `SPAN_JOIN` 会给出错误的结果，而 `INTERVAL INTERSECTION OF` 可以正常处理。
   - **负的边界会被视为错误**，这一点与 `_interval_intersect!` 相同。请用 `|> WHERE dur >= 0` 或在输入子查询中过滤掉 `dur = -1` 的未完成 slice。

---

## 迁移树聚合

用 `TREE ACCUMULATE UP` 和 `TREE ACCUMULATE DOWN` 替换 `_graph_aggregating_scan!`，以及对子树或路径求和的递归 CTE。

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

1. **删除中间表、`parent_id` 索引和反向 JOIN。**可以直接从宏或子查询接入 pipeline：
   ```sql
   CREATE PERFETTO TABLE _linux_perf_callstacks AS
   FROM _callstacks_for_callsites!((SELECT callsite_id FROM perf_sample))
   |> TREE ACCUMULATE UP SUM(self_count) AS cumulative_count;
   ```
   输入的列全部保留，`cumulative_count` 追加在末尾。
2. **数据源需要 `id` 和 `parent_id` 列**，且根节点满足 `parent_id IS NULL`。
3. **总计包含节点自身。**`UP SUM(x)` 把节点的 `x` 加到其后代的合计上；`DOWN SUM(x)` 把它加到其祖先的合计上。手写的 `_graph_aggregating_scan!` 步骤有时会忘记为有子节点的节点加上 `r.self_*`，迁移后请核对结果是否一致。
4. **如果顺序重要就排序。**`UP` 先输出子节点，`DOWN` 先输出父节点。如果某个表或测试期望行按 `id` 排列，请以 `|> ORDER BY id` 结尾。

---

## 常见陷阱

### 1. 每个源列都需要有效且互不相同的名称

源子查询的每一列都会被检查，包括后续阶段会丢弃的列：

- **表达式必须有名称：**
  ```sql
  -- ERROR: expected every column to have a name, but column 3 has none:
  -- give it one with AS
  FROM (SELECT id, parent_id, 1 + 1 FROM tree)
  |> TREE ACCUMULATE UP SUM(id) AS total
  |> SELECT id, total;
  ```
- **名称必须互不相同：**`FROM (SELECT 1 AS x, 2 AS x)` 会失败，报错为 `expected distinct column names, but there are two named 'x'`。

### 2. `FROM` 接受表、宏或子查询

`FROM` 不能自带 `WHERE` 或 `JOIN`。请用 `|> WHERE` 阶段过滤，或者把 SQL 放进子查询：

```sql
-- ERROR:
FROM slice WHERE dur > 0 |> TREE ACCUMULATE UP SUM(dur) AS total;

-- OK:
FROM slice
|> WHERE dur > 0
|> TREE ACCUMULATE UP SUM(dur) AS total;

-- OK, and needed for a JOIN or a filter WHERE does not support:
FROM (SELECT id, parent_id, dur FROM slice WHERE name GLOB 'Choreographer*')
|> TREE ACCUMULATE UP SUM(dur) AS total;
```

### 3. 别名记住的是它被设置那一刻的行

`DROP`、`RENAME`、`SET` 和 `EXTEND` 不会改变别名：

- `FROM t AS t |> DROP x |> SELECT t.x` 仍能找到 `x`。
- 在 `FROM t AS t |> RENAME x AS y` 之后，该列的裸名是 `y`，通过别名访问则仍是 `t.x`。
- `|> SELECT` 会清除所有别名。
- `|> AS u` 会把所有别名替换为 `u`，对应替换那一刻的行。
