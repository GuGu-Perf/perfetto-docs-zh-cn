# PerfettoSQL pipe 语法入门指南

本页面是使用 PerfettoSQL pipe 语法查询 trace 的入门指南原型。

> **警告：**pipe 语法是**实验性的、不稳定的**。**不要**在仪表盘、脚本或生产查询中依赖它。任何内容都可能并且终将发生破坏，恕不另行通知。要在 Perfetto UI 或 `trace_processor_shell` 中运行本页的示例，请以 `PERFETTO PRAGMA pipelines = 1;` 作为查询的开头。

相关页面：

- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)

---

## pipeline 的工作方式

标准 SQL 查询的阅读顺序是从内向外：你先写 `SELECT` 列出最终想要的列，再写 `FROM` 说明数据来自哪里。每当需要多步转换时，就要嵌套子查询或 CTE。

而使用 pipe 语法时，查询按照数据被处理的顺序自上而下阅读：

1. 从一个**源**开始：`FROM <table>`、`FROM (<subquery>)` 或 `INTERVAL INTERSECTION OF (...)`。
2. 用 `|>` 串联一个或多个**pipe 阶段**，逐步对行进行转换、聚合或重塑。

```sql
PERFETTO PRAGMA pipelines = 1;

FROM slice
|> RENAME dur AS duration_ns
|> SELECT id, name, ts, duration_ns;
```

每个 `|>` 阶段都接收上一步产生的表，并为下一步输出一个新表。

### 将 pipeline 保存为表

你可以直接把一个 pipeline 当作查询来运行，也可以把它的输出保存到 `PERFETTO TABLE` 中，以便后续继续用 SQL 查询：

```sql
PERFETTO PRAGMA pipelines = 1;

CREATE PERFETTO TABLE named_slices AS
FROM (SELECT id, ts, dur, name FROM slice WHERE dur > 0)
|> RENAME dur AS duration_ns;

SELECT name, duration_ns
FROM named_slices
ORDER BY duration_ns DESC
LIMIT 10;
```

---

## 求时间区间的交集：`INTERVAL INTERSECTION OF`

许多 trace 分析问题都在问两个或多个时间区间集合 `[ts, ts + dur)` 在哪些地方重叠：

- 每个调度 slice 运行期间，各个 CPU 核心的频率是多少？
- 某个线程处于特定状态时，哪些 slice 是活跃的？
- 在 GPU 活跃区域期间，每个任务消耗了多少电量？

`INTERVAL INTERSECTION OF` 接受两个或多个区间源，并为它们共有的每个重叠时间区域输出一行：

```sql
PERFETTO PRAGMA pipelines = 1;

-- 1. 持续时间为正的调度 slice
CREATE PERFETTO TABLE running_sched AS
SELECT ts, dur, cpu, utid
FROM sched
WHERE dur > 0;

-- 2. 每个 CPU 的 CPU 频率区间
CREATE PERFETTO TABLE cpu_freq AS
SELECT
  c.ts,
  lead(c.ts) OVER (PARTITION BY t.cpu ORDER BY c.ts) - c.ts AS dur,
  t.cpu,
  c.value AS freq
FROM counter AS c
JOIN cpu_counter_track AS t ON c.track_id = t.id
WHERE t.name = 'cpufreq';

-- 3. 按 CPU 求调度 slice 与 CPU 频率的交集
CREATE PERFETTO TABLE sched_with_freq AS
INTERVAL INTERSECTION OF (running_sched AS s, cpu_freq AS f) PER cpu
|> SELECT ts, dur, cpu, s.utid, f.freq;
```

### 工作原理

```
running_sched (s):   [------- utid 10 -------)     [--- utid 20 ---)
cpu_freq (f):        [--- 1.8 GHz ---)[-------- 2.4 GHz --------)
                     -----------------------------------------------
Result regions:      [-- 10 @ 1.8G --)[- 10 -]     [-- 20 @ 2.4G --)
```

- **区域的 `ts` 和 `dur`：**输出中裸露的 `ts` 和 `dur` 是重叠区域的起点和时长，被裁剪到所有输入同时活跃的范围。
- **用 `PER` 分区：**添加 `PER cpu` 后，只有当区间出现在同一个 `cpu` 上时才会求交集。`cpu` 列可以直接通过其裸名称访问。
- **访问输入列：**每个输入都有一个别名，这里是 `AS s` 和 `AS f`。来自 `s` 和 `f` 的所有列都会被携带，并通过 `s.<col>` 和 `f.<col>` 访问。这包括每个输入原始的、未裁剪的 `s.ts` 和 `s.dur`。

---

## 在树上求和：`TREE ACCUMULATE`

trace 中经常包含树形结构，其中每一行都有一个 `id` 和一个 `parent_id`，并且根节点满足 `parent_id IS NULL`：

- `slice` 中嵌套的用户空间 slice
- 来自 CPU profiling、perf 和 native heap profile 的采样调用栈
- Java 堆图的最短路径树

`TREE ACCUMULATE` 在单个阶段中对由 `id` 和 `parent_id` 构成的树计算累计和，保留所有现有列并追加总计值：

- **`TREE ACCUMULATE UP`：**将每个节点的值与它的所有后代节点的值求和。
- **`TREE ACCUMULATE DOWN`：**将每个节点的值与从根节点到该节点的所有祖先节点的值求和。

```sql
PERFETTO PRAGMA pipelines = 1;

CREATE PERFETTO TABLE tree AS
SELECT 0 AS id, NULL AS parent_id, 'root' AS name, 10 AS self
UNION ALL SELECT 1, 0, 'a', 20
UNION ALL SELECT 2, 0, 'b', 30
UNION ALL SELECT 3, 1, 'c', 40;

CREATE PERFETTO TABLE tree_totals AS
FROM tree
|> TREE ACCUMULATE UP SUM(self) AS subtree_total
|> TREE ACCUMULATE DOWN SUM(self) AS path_total;

SELECT name, self, subtree_total, path_total
FROM tree_totals
ORDER BY id;
```

对于树 `root (10) -> a (20) -> c (40)` 和 `root (10) -> b (30)`：

| `name` | `self` | `subtree_total` | `path_total` |
| :--- | ---: | ---: | ---: |
| `root` | 10 | 100 | 10 |
| `a` | 20 | 60 | 30 |
| `b` | 30 | 30 | 40 |
| `c` | 40 | 40 | 70 |

---

## 重塑列

与其为了添加、删除或重命名列而把查询包裹在额外的外层 `SELECT` 中，不如使用列重塑阶段就地修改当前行：

- **`|> SELECT`：**选取、重排或重命名列。你还可以使用 `* EXCEPT (col1, col2)` 排除列，或使用 `* REPLACE (other_col AS col1)` 就地替换某个列：
  ```sql
  FROM slice
  |> SELECT * EXCEPT (arg_set_id, parent_id)
  ```
- **`|> EXTEND`：**在保留所有现有列的同时，向当前行的末尾追加新列：
  ```sql
  FROM slice AS s
  |> EXTEND s.dur AS original_dur
  ```
- **`|> DROP`：**按名称移除一个或多个列：
  ```sql
  FROM slice
  |> DROP category, track_id, arg_set_id
  ```
- **`|> RENAME`：**就地重命名列，无需逐一列出其他列：
  ```sql
  FROM slice
  |> RENAME ts AS start_ts, dur AS duration_ns
  ```
- **`|> SET`：**就地替换现有列的值：
  ```sql
  FROM tree AS t
  |> TREE ACCUMULATE UP SUM(self) AS total
  |> SET self = total
  |> DROP total
  ```

---

## 下一步

- [PerfettoSQL pipe 语法参考](/docs/analysis/perfetto-sql-pipe-syntax.md)
- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)
