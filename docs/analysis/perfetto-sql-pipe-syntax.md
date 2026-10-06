# PerfettoSQL pipe 语法参考

本页面是 PerfettoSQL pipeline 的语言语法与语义参考。

> **警告：**pipe 语法是**实验性的、不稳定的**。**不要**在仪表盘、脚本或生产查询中依赖它。任何内容都可能并且终将发生破坏，恕不另行通知。在 PerfettoSQL 标准库之外，需要通过 `PERFETTO PRAGMA pipelines = 1;` 在连接上启用它。

相关页面：

- [PerfettoSQL pipe 语法入门指南](/docs/analysis/perfetto-sql-pipe-getting-started.md)
- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)

---

## Pragma 与语句形式

### `PERFETTO PRAGMA pipelines`

控制在当前连接上（标准库之外）是否允许使用 pipe 语法：

```sql
PERFETTO PRAGMA pipelines = 1;  -- 启用 pipeline
PERFETTO PRAGMA pipelines = 0;  -- 禁用 pipeline
```

等号右侧必须求值为整数。未知的 pragma 名称会产生错误。

### 顶层形式

pipeline 在两种语句位置中有效：

```sql
-- 1. 独立查询
<pipeline>;

-- 2. 物化的 Perfetto 表
CREATE [OR REPLACE] PERFETTO TABLE <table_name> [(<schema>)] AS
<pipeline>;
```

一个 `<pipeline>` 由一个源（`FROM` 或 `INTERVAL INTERSECTION OF`）加上后续零个或多个 `|>` 阶段组成：

```sql
<source>
[|> <stage_1>]
[|> <stage_2>]
...
```

> **注意：**pipe 运算符 `|>` 的 `|` 和 `>` 之间必须连续书写、不能有空白。pipeline 关键字 `TREE`、`ACCUMULATE`、`UP`、`DOWN`、`INTERVAL`、`INTERSECTION`、`PER` 和 `EXTEND` 是非保留关键字，在标准 SQL 语句中仍然是有效的普通标识符。

---

## pipeline 源

### `FROM`

从单个关系开始一个 pipeline：

```sql
FROM [<schema>.]<table_name> [[AS] <alias>]
FROM (<select_stmt>) [[AS] <alias>]
```

- `<table_name>` 可以是任何表或视图，也可以是展开后为表或带括号子查询的宏调用。
- `(<select_stmt>)` 可以是任何括在圆括号内的有效 SQL `SELECT` 语句。
- **表限定符：**
  - 如果给定了 `<alias>`，源的列可以用 `<alias>.<col>` 来限定。当源是表名时，`<alias>` 会取代 `<table_name>` 成为限定符。
  - 如果源是未加别名的 `<table_name>`，列可以用 `<table_name>.<col>` 来限定。
  - 如果源是未加别名的 `(<select_stmt>)`，那么除非后续的 `|> AS <alias>` 阶段绑定了限定符，否则它的列没有表限定符。

### `INTERVAL INTERSECTION OF`

以两个或多个关系中相互重叠的时间区域作为 pipeline 的起点：

```sql
INTERVAL INTERSECTION OF (
  <source_1> [AS] <alias_1>,
  <source_2> [AS] <alias_2>
  [, <source_N> [AS] <alias_N> ...]
) [PER <col_1> [, <col_2> ...]]
```

#### 要求

1. 必须至少列出两个操作数源。
2. 每个操作数都必须有一个互不相同的别名。未加别名的表名本身即充当其别名；带括号的子查询必须指定 `[AS] <alias>`。
3. 每个操作数都必须包含 `ts` 和 `dur` 列，并且 `PER` 中列出的每一列都必须存在于每个操作数中。

#### 输出列与作用域

对于同一个匹配 `PER` 键分组内所有操作数共有的每个重叠区域 `[ts, ts + dur)`，都会产生一行，其中包含以下列：

1. `ts` 和 `dur`：保存交集区域起点和时长的 64 位整数列。它们是非限定列查找唯一可见的 `ts` 和 `dur` 列。
2. 按操作数顺序排列的每个操作数的列：
   - 第一个操作数的 `PER` 键列既可以非限定访问（如 `cpu`），也可以限定访问（如 `<alias_1>.cpu`）。
   - 所有其他操作数列都只能限定访问。这包括每个操作数原始的 `ts` 和 `dur`，以及后续操作数中 `PER` 列的副本。它们只能通过 `<alias_i>.<col>` 引用，或通过 `*` 或 `<alias_i>.*` 展开。

#### 区间语义

- **半开边界：**每个区间都是 `[ts, ts + dur)`。两个在端点处相接的区间（例如 `[0, 10)` 和 `[10, 20)`）不相交。
- **零时长的点：**`dur = 0` 的行是 `ts` 时刻上的一个点。当 `a <= ts < b` 时，它与区间 `[a, b)` 相交；当两个点位于同一时刻 `ts` 时，它们彼此相交，产生一个 `dur = 0` 的区域。
- **缺失边界：**`ts IS NULL` 或 `dur IS NULL` 的行不覆盖任何时间，会被跳过。
- **负边界：**`ts < 0` 或 `dur < 0` 的行会失败并报错 `ts or dur is below zero`。
- **`PER` 列中的 `NULL`：**在某个 `PER` 列上均为 `NULL` 的两行在该列上视为一致，与 `GROUP BY` 语义相符。

### 源列命名规则

任何 pipeline 源的每一列都必须有一个匹配 `^[a-zA-Z_][a-zA-Z0-9_]*$` 的有效标识符名称，并且在该源内必须互不相同——即使后续阶段会删除该列：

- 未加别名的 SQL 表达式（如 `1 + 1` 或 `max(ts)`）会被拒绝，错误信息为：`expected every column to have a valid name, but '<expr>' is not one: give it one with AS`。
- 源中重复的列名会被拒绝，错误信息为：`expected distinct column names, but there are two named '<name>'`。

---

## pipeline 阶段

### `TREE ACCUMULATE`

沿由 `id` 和 `parent_id` 定义的树向上或向下累计求和：

```sql
|> TREE ACCUMULATE UP|DOWN
  SUM([<qualifier>.]<col_1>) AS <out_1>
  [, SUM([<qualifier>.]<col_2>) AS <out_2> ...]
```

- **树结构列：**在当前行中解析裸的 `id` 和 `parent_id`。根节点满足 `parent_id IS NULL`。
- **方向：**
  - `UP`：自底向上折叠。每个节点的聚合值是其自身值与其所有后代节点值之和。输出行按子节点优先的顺序发出。
  - `DOWN`：自顶向下折叠。每个节点的聚合值是其自身值与其所有祖先节点值之和。输出行按父节点优先的顺序发出。
- **聚合表达式：**
  - 目前仅支持 `SUM(<column_ref>)`。`DISTINCT`、`FILTER`、`OVER`、`*`、非列表达式以及其他聚合函数都会被拒绝。
  - 目标列必须是整数类型：`ID`、`UINT32`、`INT32` 或 `LONG`。`NULL` 值按 `0` 计入。
  - 单个阶段中的所有聚合都针对该阶段之前的行解析各自的输入列。某个阶段不能引用同一阶段中定义的输出列。
- **输出：**保留输入行的所有列和现有的表别名，并追加 `<out_1>, <out_2>, ...` 作为 `LONG` 列。

---

### `SELECT`

用指定的各项替换当前行，并清除所有表别名：

```sql
|> SELECT <select_item> [, <select_item> ...]
```

每个 `<select_item>` 是以下形式之一：

- **列引用：**`[<qualifier>.]<col> [[AS] <alias>]`
- **星号展开：**
  `[<qualifier>.]* [EXCEPT (<col_1> [, <col_2> ...])] [REPLACE (<replace_item> [, ...])]`
  其中每个 `<replace_item>` 为 `[<qualifier>.]<source_col> AS <target_col>`。
  在 `REPLACE` 中 `AS` 是必需的。

星号展开规则：

1. `*` 从当前行的所有列开始，包括 `INTERVAL INTERSECTION OF` 之后仅可限定访问的操作数列。`<qualifier>.*` 从绑定 `<qualifier>` 时捕获的列开始。
2. `EXCEPT (<col>, ...)` 会移除与任何所列裸名称匹配的每一列（不区分大小写）。每个列出的名称都必须至少匹配一列，任何名称都不得重复列出，并且在 `EXCEPT` 之后必须至少保留一列。
3. `REPLACE (<source_col> AS <target_col>, ...)` 针对该阶段之前的输入行或别名解析 `<source_col>`，并在星号展开中替换 `<target_col>` 的值，同时保持 `<target_col>` 的位置和名称不变。`<target_col>` 必须恰好匹配 `EXCEPT` 之后星号展开中保留的一列。
4. 由 `*` 或 `<qualifier>.*` 产生的所有列在后续阶段中都可以不加限定符地引用。

---

### `EXTEND`

在保留所有现有列和别名的同时，向当前行的末尾追加列：

```sql
|> EXTEND <extend_item> [, <extend_item> ...]
```

- 接受与 `SELECT` 相同的各项，但不允许裸的 `*`。请使用 `<qualifier>.*` 追加某个表别名的所有列。
- `EXTEND` 中的所有项都针对该阶段之前的行解析，因此某一项不能引用同一个 `EXTEND` 阶段中添加的另一列。
- 由 `EXTEND` 添加的列不会添加到任何现有的表别名上。

---

### `DROP`

按裸名称从当前行中移除列：

```sql
|> DROP <col_1> [, <col_2> ...]
```

- 每个列出的名称都必须匹配当前行中至少一个可非限定访问的列，并且会从裸行中移除该名称的所有列。
- 任何名称都不得重复列出，并且在 `DROP` 之后行中必须至少保留一列。
- 现有的表别名会保留被删除的列，但名称与某个被删除列名相同的表别名会被移除。

---

### `RENAME`

就地重命名当前行中的列：

```sql
|> RENAME <old_1> [AS] <new_1> [, <old_2> [AS] <new_2> ...]
```

- `<old_i>` 必须是能在当前行中明确解析的裸列名，并且在同一个 `RENAME` 中不得重复列出。
- 单个阶段中的所有重命名同时生效，因此 `|> RENAME x AS y, y AS x` 会交换 `x` 和 `y`。
- 允许将列重命名为某个现有列的名称。这会在行中产生重复的列名，只有当后续阶段引用这个有歧义的名称时才会出错。
- 现有的表别名不受影响，并继续以旧名称暴露该列。

---

### `SET`

就地替换当前行中现有列的值：

```sql
|> SET <target_1> = [<qualifier>.]<source_1> [, <target_2> = [<qualifier>.]<source_2> ...]
```

- `<target_i>` 必须是能在当前行中明确解析的裸列名，并且在同一个 `SET` 中不得重复列出。
- 每个 `<source_i>` 都针对该阶段之前的行和别名解析，因此 `|> SET x = y, y = x` 会交换 `x` 和 `y` 的值。
- 现有的表别名保留 `SET` 之前的值，但名称与 `<target_i>` 相同的表别名会被移除。

---

### `AS`

用一个绑定到当前行快照的新别名替换所有现有的表别名：

```sql
|> AS <alias>
```

在 `|> AS u` 之后，先前的表别名不再处于作用域内，`u.<col>` 和 `u.*` 反映的是 `AS` 阶段时刻的行。

---

## 名称解析与歧义规则

- **不区分大小写：**列名和表别名在匹配时使用 ASCII 折叠、不区分大小写，同时在输出 schema 中保留定义该列或别名时的大小写。
- **重复列名：**允许某个阶段在行中创建重复的列名，例如在 `y` 已存在时执行 `|> EXTEND x` 或 `|> RENAME x AS y`。只有当后续阶段不加表限定符地引用这个有歧义的名称时，重复名称才会导致错误。你也可以通过 `DROP y` 或 `* EXCEPT (y)` 一次性删除或排除所有同名列。
- **带引号的标识符：**标识符可以用 `"..."`、`` `...` `` 或 `[...]` 括起来。在 `"..."` 和 `` `...` `` 内部，将引号字符双写即可转义字面引号，而 `""` 表示空列名。
