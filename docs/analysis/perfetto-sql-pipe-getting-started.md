# PerfettoSQL pipe 语法入门指南

> **警告：**pipe 语法是**实验性的、不稳定的**。**不要**在仪表盘、脚本或生产查询中依赖它。任何内容都可能并且终将发生破坏，恕不另行通知。要在 Perfetto UI 或 `trace_processor_shell` 中运行本页的示例，请以 `PERFETTO PRAGMA pipelines = 1;` 作为查询的开头。

相关页面：

- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)

---

## pipeline 的工作方式

SQL 查询的阅读顺序是从内向外：`SELECT` 写在最前却最后执行，每多一步都要再嵌套一层子查询或 CTE。而 pipeline 按照工作发生的顺序自上而下阅读：

1. 从一个**源**开始：`FROM <table>`、`FROM (<subquery>)` 或 `INTERVAL INTERSECTION OF (...)`。
2. 每个 `|>` **阶段**接收上一步的行，并把新的行传递给下一步。

```sql
PERFETTO PRAGMA pipelines = 1;

FROM slice
|> WHERE dur > 0
|> RENAME dur AS duration_ns
|> SELECT id, name, ts, duration_ns;
```

### 将 pipeline 保存为表

既可以独立运行一条 pipeline 作为查询，也可以把它保存为 `PERFETTO TABLE`，再用 SQL 查询它：

```sql
PERFETTO PRAGMA pipelines = 1;

CREATE PERFETTO TABLE named_slices AS
FROM slice
|> WHERE dur > 0
|> SELECT id, ts, dur AS duration_ns, name;

SELECT name, duration_ns
FROM named_slices
ORDER BY duration_ns DESC
LIMIT 10;
```

---

## 求时间区间的交集：`INTERVAL INTERSECTION OF`

关于 trace 的许多问题都在问两个或多个区间集合 `[ts, ts + dur)` 在哪些地方重叠：

- 每个调度 slice 运行期间，各个 CPU 核心的频率是多少？
- 某个线程处于特定状态时，哪些 slice 是活跃的？
- GPU 活跃期间，每个任务消耗了多少电量？

`INTERVAL INTERSECTION OF` 接受两个或多个区间源，并为所有输入重叠的每个区域输出一行：

```sql
PERFETTO PRAGMA pipelines = 1;

CREATE PERFETTO TABLE running_sched AS
SELECT ts, dur, cpu, utid
FROM sched
WHERE dur > 0;

CREATE PERFETTO TABLE cpu_freq AS
SELECT
  c.ts,
  lead(c.ts) OVER (PARTITION BY t.cpu ORDER BY c.ts) - c.ts AS dur,
  t.cpu,
  c.value AS freq
FROM counter AS c
JOIN cpu_counter_track AS t ON c.track_id = t.id
WHERE t.name = 'cpufreq';

CREATE PERFETTO TABLE sched_with_freq AS
INTERVAL INTERSECTION OF (running_sched AS s, cpu_freq AS f) PER cpu
|> SELECT ts, dur, cpu, utid, freq;
```

```
running_sched (s):   [------- utid 10 -------)     [--- utid 20 ---)
cpu_freq (f):        [--- 1.8 GHz ---)[-------- 2.4 GHz --------)
                     -----------------------------------------------
Result regions:      [-- 10 @ 1.8G --)[- 10 -]     [-- 20 @ 2.4G --)
```

- **`ts` 和 `dur`** 是重叠区域，被裁剪到每个输入都活跃的范围。
- **`PER cpu`** 只对同一个 `cpu` 上的行求交集。
- **输入列**会被携带下来。可以直接写裸名，如 `utid` 和 `freq`；也可以通过输入的别名访问，如 `s.utid`。如果两个输入有同名的列，就必须使用别名。
- **输入自身的边界**是未经裁剪的 `s.ts` 和 `s.dur`。

---

## 展平重叠区间：`INTERVAL FLATTEN` {#flattening-overlapping-intervals-interval-flatten}

`INTERVAL FLATTEN` 会把一组重叠区间切分成若干段，并对每段内活跃的行做聚合。可以用它统计并发活动，或在并发区间上对某个值求和。

两个任务分别在 `[0, 10)` 和 `[5, 15)` 期间运行，权重分别为 2 和 3：

```sql
PERFETTO PRAGMA pipelines = 1;

FROM (
  SELECT 0 AS ts, 10 AS dur, 2 AS weight
  UNION ALL
  SELECT 5 AS ts, 10 AS dur, 3 AS weight
)
|> INTERVAL FLATTEN AGGREGATE COUNT(*) AS active, SUM(weight) AS total_weight;
```

| ts | dur | active | total_weight |
| -- | --- | ------ | ------------ |
| 0 | 5 | 1 | 2 |
| 5 | 5 | 2 | 5 |
| 10 | 5 | 1 | 3 |

`PER` 会让每个组各自独立展平。要统计每条 track 上重叠的 slice：

```sql
FROM slice
|> WHERE dur > 0
|> INTERVAL FLATTEN PER track_id AGGREGATE COUNT(*) AS active;
```

结果包含 `ts`、`dur`、`track_id` 和 `active`，其余所有列都会被丢弃。没有活动的空隙不会产生行。

`SUM` 只是把活跃行的值相加，不会按区段时长加权。如果需要加权，请把 pipeline 保存为表，然后在 SQL 中对 `dur * total_weight` 求和。

关于零时长区间、`NULL` 以及支持的聚合函数，参见[语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md#interval-flatten)。

---

## 填补空隙：`INTERVAL FILL GAPS` {#filling-gaps-interval-fill-gaps}

`INTERVAL FILL GAPS` 保留输入的每一行，并为背景区间中未被任何输入覆盖的每一段补上一行。填充行的值取自背景，背景中没有的列则填 `NULL`。

要标记 0 到 10 之间每个 CPU 何时空闲：

```sql
PERFETTO PRAGMA pipelines = 1;

CREATE PERFETTO TABLE spans AS
SELECT 2 AS ts, 3 AS dur, 0 AS cpu, 'run' AS state
UNION ALL SELECT 6, 2, 0, 'run'
UNION ALL SELECT 1, 4, 1, 'run';

FROM spans
|> INTERVAL FILL GAPS WITH (SELECT 0 AS ts, 10 AS dur, 'idle' AS state) PER cpu
|> ORDER BY cpu, ts;
```

| ts | dur | cpu | state |
| -- | --- | --- | ----- |
| 0 | 2 | 0 | idle |
| 2 | 3 | 0 | run |
| 5 | 1 | 0 | idle |
| 6 | 2 | 0 | run |
| 8 | 2 | 0 | idle |
| 0 | 1 | 1 | idle |
| 1 | 4 | 1 | run |
| 5 | 5 | 1 | idle |

---

## 在树上求和：`TREE ACCUMULATE`

trace 中有许多树形结构，其中每一行都有 `id` 和 `parent_id`，并且根节点满足 `parent_id IS NULL`：

- `slice` 中嵌套的 slice。
- 来自 CPU profiling、perf 和 native heap profile 的调用栈。
- Java 堆图的最短路径树。

`TREE ACCUMULATE` 在单个阶段内对这样的树求和。它会保留所有列，并在末尾追加总计值：

- **`UP`** 将每个节点与它的所有后代求和。
- **`DOWN`** 将每个节点与它的所有祖先求和。

```sql
PERFETTO PRAGMA pipelines = 1;

CREATE PERFETTO TABLE tree AS
SELECT 0 AS id, NULL AS parent_id, 'root' AS name, 10 AS self
UNION ALL SELECT 1, 0, 'a', 20
UNION ALL SELECT 2, 0, 'b', 30
UNION ALL SELECT 3, 1, 'c', 40;

FROM tree
|> TREE ACCUMULATE UP SUM(self) AS subtree_total
|> TREE ACCUMULATE DOWN SUM(self) AS path_total
|> ORDER BY id
|> SELECT name, self, subtree_total, path_total;
```

对于树 `root (10) -> a (20) -> c (40)` 和 `root (10) -> b (30)`：

| `name` | `self` | `subtree_total` | `path_total` |
| :--- | ---: | ---: | ---: |
| `root` | 10 | 100 | 10 |
| `a` | 20 | 60 | 30 |
| `b` | 30 | 30 | 40 |
| `c` | 40 | 40 | 70 |

---

## 分组：`AGGREGATE`

`AGGREGATE` 把每一组行折叠为一行，作用与 SQL 中的 `GROUP BY` 相同：

```sql
FROM slice
|> WHERE dur > 0
|> AGGREGATE COUNT(*) AS slices, SUM(dur) AS total, MAX(dur) AS longest
   GROUP BY track_id;
```

结果包含 `track_id`、`slices`、`total` 和 `longest`。如果不带 `GROUP BY`，所有行都会归入同一个组。

---

## 过滤与排序行

- **`|> WHERE`** 保留匹配的行。目前它支持列与数值的比较，多个条件用 `AND` 连接：
  ```sql
  FROM slice
  |> WHERE dur > 0 AND depth = 0
  ```
- **`|> DISTINCT`** 丢弃重复的行：
  ```sql
  FROM slice
  |> SELECT track_id
  |> DISTINCT
  ```
- **`|> ORDER BY`** 按数值列排序：
  ```sql
  FROM slice
  |> ORDER BY dur DESC
  ```

---

## 重塑列

这些阶段会修改列，无需把查询包裹进另一层 `SELECT`：

- **`|> SELECT`** 选取、重排并重命名列。`* EXCEPT (...)` 会丢弃部分列，`* REPLACE (other_col AS col)` 会就地替换某个列：
  ```sql
  FROM slice
  |> SELECT * EXCEPT (arg_set_id, parent_id)
  ```
- **`|> EXTEND`** 在末尾追加列：
  ```sql
  FROM slice AS s
  |> EXTEND s.dur AS original_dur
  ```
- **`|> DROP`** 移除列：
  ```sql
  FROM slice
  |> DROP category, track_id, arg_set_id
  ```
- **`|> RENAME`** 就地重命名列：
  ```sql
  FROM slice
  |> RENAME ts AS start_ts, dur AS duration_ns
  ```
- **`|> SET`** 替换某个列的值：
  ```sql
  FROM tree
  |> TREE ACCUMULATE UP SUM(self) AS total
  |> SET self = total
  |> DROP total
  ```

`SELECT`、`EXTEND` 和 `SET` 也接受[表达式](/docs/analysis/perfetto-sql-pipe-syntax.md#expressions)，例如 `a + 1` 或 `'label'`。

---

## 下一步

- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)
