# PerfettoSQL pipe 语法参考

> **警告：**pipe 语法是**实验性的、不稳定的**。**不要**在仪表盘、脚本或生产查询中依赖它。任何内容都可能并且终将发生破坏，恕不另行通知。在 PerfettoSQL 标准库之外，需要通过 `PERFETTO PRAGMA pipelines = 1;` 在连接上启用它。

相关页面：

- [PerfettoSQL pipe 语法入门指南](/docs/analysis/perfetto-sql-pipe-getting-started.md)
- [迁移到 PerfettoSQL pipe 语法](/docs/analysis/perfetto-sql-pipe-migration.md)
- [PerfettoSQL pipe 运算符实现说明](/docs/design-docs/perfetto-sql-pipelines.md)

---

## Pragma 与语句形式

### `PERFETTO PRAGMA pipelines` {#perfetto-pragma-pipelines}

为当前连接开启或关闭 pipe 语法。标准库始终可以使用它。

```sql
PERFETTO PRAGMA pipelines = 1;  -- 开启
PERFETTO PRAGMA pipelines = 0;  -- 关闭
```

该值必须是非负整数字面量；任何非 `0` 的值都会开启 pipeline。该 pragma 名称区分大小写。

### 顶层形式

pipeline 可以是一条独立的语句，也可以作为 `PERFETTO TABLE` 的主体：

```sql
<pipeline>;

CREATE [OR REPLACE] PERFETTO TABLE <table_name> [(<schema>)] AS
<pipeline>;
```

它目前还不能作为视图、函数或 `WITH` 子句的主体，也不能出现在子查询内部。

一个 `<pipeline>` 由一个源加上任意数量的阶段组成：

```railroad pipeline
Diagram(
  NonTerminal('source-clause'),
  ZeroOrMore(Sequence(Terminal('|>'), NonTerminal('stage'))))
```

- `|>` 的 `|` 和 `>` 之间必须连续书写、不能有空格。
- `TREE`、`ACCUMULATE`、`UP`、`DOWN`、`INTERVAL`、`INTERSECTION`、`FLATTEN`、`FILL`、`GAPS`、`AGGREGATE`、`PER`、`EXTEND`、`GRAPH`、`BFS`、`DFS`、`DOMINATOR`、`NODES` 和 `EDGES` 不是保留字，因此仍可在 SQL 中用作名称。
- 别名始终需要 `AS`：应写 `FROM slice AS s`，而不是 `FROM slice s`。

`<source-clause>` 是 [`FROM`](#from)、[`INTERVAL INTERSECTION OF`](#interval-intersection-of) 或 [`GRAPH ... TREE`](#graph-tree)。`<stage>` 是以下之一：

```railroad stage
Diagram(Choice(0,
  Link(Terminal('WHERE'), '#where'),
  Link(Terminal('DISTINCT'), '#distinct'),
  Link(Terminal('ORDER BY'), '#order-by'),
  Link(Terminal('LIMIT'), '#limit'),
  Link(Terminal('INTERVAL FLATTEN'), '#interval-flatten'),
  Link(Terminal('INTERVAL FILL GAPS'), '#interval-fill-gaps'),
  Link(Terminal('TREE ACCUMULATE'), '#tree-accumulate'),
  Link(Terminal('AGGREGATE'), '#aggregate'),
  Link(Terminal('SELECT'), '#select'),
  Link(Terminal('EXTEND'), '#extend'),
  Link(Terminal('DROP'), '#drop'),
  Link(Terminal('RENAME'), '#rename'),
  Link(Terminal('SET'), '#set'),
  Link(Terminal('AS'), '#as')))
```

### 共享规则

`<source>` 是一个表或子查询，可带可选的别名：

```railroad source
Diagram(
  Choice(0,
    NonTerminal('table-name'),
    Sequence(Terminal('('), NonTerminal('select-stmt'), Terminal(')'))),
  Optional(Sequence(Terminal('AS'), NonTerminal('alias'))))
```

`<column>` 可以由别名限定：

```railroad column
Diagram(Optional(Sequence(NonTerminal('alias'), Terminal('.'))), NonTerminal('name'))
```

`<per-clause>` 列出用于将行划分为组的列：

```railroad per-clause
Diagram(Terminal('PER'), OneOrMore(NonTerminal('column'), Terminal(',')))
```

重复列出的列不会产生新的分组。

### 限制

- pipeline 最多输出 256 列。
- 源的每一列都必须有一个互不相同的名称，由字母、数字和 `_` 组成且不以数字开头。即使对于会被后续阶段删除的列也是如此：
  - 没有名称的列（如 `SELECT 1 + 1`）会失败并报错 `expected every column to have a name, but column <n> has none: give it one with AS`。
  - 不是有效标识符的名称会失败并报错 `expected every column to have a valid name, but '<name>' is not one: give it one with AS`。
  - 两个列共用一个名称会失败并报错 `expected distinct column names, but there are two named '<name>'`。

---

## 源

### `FROM` {#from}

```railroad
Diagram(Terminal('FROM'), NonTerminal('source'))
```

- `<table-name>` 是表、视图，或展开后为这两者之一的宏。不支持 `main.t` 这类带 schema 限定的名称。
- `<select-stmt>` 是任意 SQL `SELECT`。
- **限定符：**`FROM slice` 允许把列写成 `slice.<col>`；`FROM slice AS s` 则改为 `s.<col>`。未加别名的子查询没有限定符，直到后续的 `|> AS <alias>` 为止。

### `INTERVAL INTERSECTION OF` {#interval-intersection-of}

找出两个或多个源的区间相互重叠的位置：

```railroad
Diagram(
  Terminal('INTERVAL'), Terminal('INTERSECTION'), Terminal('OF'),
  Terminal('('), OneOrMore(NonTerminal('source'), Terminal(',')), Terminal(')'),
  Optional(NonTerminal('per-clause')))
```

#### 要求

- 至少两个源。
- 每个源都有自己的别名。表名本身就是自己的别名；子查询需要 `AS <alias>`。
- 每个源都有 `ts` 和 `dur`，以及每一个 `PER` 列。

#### 输出

对于在 `PER` 列上取值一致的行，每个源各有一行相互重叠的每个区域 `[ts, ts + dur)`，都会产生一行。

| 列 | 按裸名称可找到 | 通过别名可找到 |
| :--- | :--- | :--- |
| 区域 `ts`、`dur` | 是 | 否 |
| 每个源自己的 `ts`、`dur` | 否 | `<alias>.ts` |
| 第一个源的 `PER` 列 | 是 | 是 |
| 后续源的 `PER` 列 | 否 | 是 |
| 其余所有源列 | 是，仅当只有一个源拥有该列 | 是 |

被两个源共有的裸名称是有歧义的；当某处引用它时就会出错。

`*`、`|> AS <alias>` 以及在交集处结束的 pipeline 的结果，都持有按裸名称可找到的列：先是区域的 `ts` 和 `dur`，然后是按顺序排列的各源的列。当两个源共用一个列名时，两份副本都会出现在结果中，这样的结果便无法保存为表。请添加一个 `|> SELECT`，通过别名来命名这些列。

#### 区间规则

- **半开：**`[0, 10)` 与 `[10, 20)` 不重叠。
- **点：**`dur = 0` 的行是 `ts` 这一时刻。当 `a <= ts < b` 时，它与 `[a, b)` 重叠；它也与同一时刻的另一个点重叠。产生的区域 `dur = 0`。
- **`NULL` 边界：**`ts` 或 `dur` 为 `NULL` 的行会被跳过。
- **负边界：**`ts` 或 `dur` 为负会失败并报错 `ts or dur is below zero`。
- **溢出：**`ts + dur` 超出 64 位范围会失败并报错 `integer overflow`。
- **`PER` 列中的 `NULL`：**在某个 `PER` 列上为 `NULL` 的行在该列上视为一致，与 `GROUP BY` 的行为相同。

### `GRAPH ... TREE` {#graph-tree}

把图归约为一棵树，覆盖从一组种子出发可达的节点：

```railroad
Diagram(
  Terminal('GRAPH'), Choice(0, Terminal('BFS'), Terminal('DFS'),
    Terminal('DOMINATOR')),
  Terminal('TREE'),
  Terminal('NODES'), NonTerminal('source'),
  Terminal('EDGES'), NonTerminal('source'),
  Terminal('FROM'), NonTerminal('source'))
```

```sql
GRAPH DOMINATOR TREE
  NODES heap_graph_object
  EDGES (SELECT owner_id AS src, owned_id AS dst FROM heap_graph_reference)
  FROM (SELECT id FROM heap_graph_object WHERE root_type IS NOT NULL)
|> TREE ACCUMULATE UP SUM(self_size) AS retained_size
```

#### 要求

- `NODES` 有一个 `id` 列，`EDGES` 有 `src` 和 `dst` 列，`FROM` 有一个 `id` 列。它们都持有整数。
- 任何两个节点的 `id` 都不相同，且每个节点都有一个。

#### 输出

从种子可达的每个节点产生一行，包含 `NODES` 的所有列和 `parent_id`（即该节点在树中的父节点的 `id`）。根节点的 `parent_id` 为 `NULL`。名为 `parent_id` 的 `NODES` 列不会被携带。父节点排在其子节点之前。`NODES` 可以指定别名，用于限定它的列。

| 类型 | 根 | 节点的父节点 |
| :--- | :--- | :--- |
| `BFS` | 每个种子 | 搜索到的第一个有边指向它的节点 |
| `DFS` | 未被更早的种子到达的每个种子 | 到达它时所来自的节点 |
| `DOMINATOR` | 每个种子 | 它的直接支配节点 |

#### 图规则

- **顺序：**种子按其行到达的顺序被搜索，每个节点的边也按同样的顺序被跟随。当一个节点可以从多个同等合适的父节点到达时，由该顺序决定选哪一个，因此可以对 `FROM` 或 `EDGES` 排序来控制选择。
- **缺失节点：**`id` 不是任何节点或为 `NULL` 的边或种子会被忽略。`NODES` 可以是 `EDGES` 所描述的图的子集。
- **支配节点：**一个节点的支配节点，是从种子到它的每条路径都会经过的节点，就好像还有一个额外的节点向每个种子连了一条边。

---

## 聚合

`INTERVAL FLATTEN`、`TREE ACCUMULATE` 和 `AGGREGATE` 接受一个 `<aggregate-list>`，并以相同的方式处理每个聚合：

```railroad aggregate-list
Diagram(OneOrMore(
  Sequence(NonTerminal('aggregate'), Terminal('AS'), NonTerminal('name')),
  Terminal(',')))
```

```railroad aggregate
Diagram(Choice(0,
  Sequence(Terminal('COUNT'), Terminal('('), Terminal('*'), Terminal(')')),
  Sequence(
    Choice(0, Terminal('SUM'), Terminal('MIN'), Terminal('MAX')),
    Terminal('('), NonTerminal('column'), Terminal(')'))))
```

- **形式：**每个聚合都需要一个 `AS` 名称。表达式、`DISTINCT`、`FILTER`、`OVER` 和其他函数都会被拒绝。
- **`COUNT(*)`** 对行计数。
- **`SUM`、`MIN` 和 `MAX`** 接受一个整数列。它们会跳过 `NULL`，并在所有值都为 `NULL` 时返回 `NULL`。来自 SQL 源、类型无法预先确定的列，会在查询运行时检查。
- **结果**是 `LONG` 列。溢出会报错。
- **作用域：**每个聚合读取的都是该阶段之前的行，因此一个聚合不能读取另一个聚合。
- **名称：**聚合可以采用其他列已有的名称。该名称因此变得有歧义，后续阶段引用它时会出错。

---

## 表达式 {#expressions}

`SELECT`、`EXTEND` 和 `SET` 可以通过以下内容计算值：

- 列、`NULL`，以及数字和字符串字面量。
- 作用于数字的 `+`、`-`、`*`、`/` 和 `%`。任一操作数为 null 时结果为 null，除以零或对零取余的结果也为 null，与 SQLite 一致。整数溢出会导致查询失败，而 SQLite 在这种情况下会返回一个双精度浮点数。

- `=`、`==`、`!=`、`<>`、`<`、`<=`、`>` 和 `>=` 的结果为 0 或 1，任一侧为 null 时结果为 null。字符串按其字节比较。整数可以与浮点字面量比较，与 [`WHERE`](#where) 中一样。将整数与其他浮点值比较会出错，字符串与数字比较同样会出错。

- `<expr> GLOB <string>` 的结果为 0 或 1，`<expr>` 为 null 时结果为 null。模式必须是字符串字面量，且 `<expr>` 必须是字符串。
- `<expr> IS [NOT] NULL` 的结果为 0 或 1。

- `coalesce(<expr>, <expr>, ...)`、`ifnull(<expr>, <expr>)` 和 `iif(<condition>, <expr>, <expr>)`。它们的结果必须是单一类型：整数与双精度浮点数混用会直接报错而不是做加宽转换，因此应写 `1.0` 而不是 `1`。`NULL` 可与任何类型搭配。如果某个参数中的整数运算只被部分行用到，也会报错，因为它可能在 SQLite 根本不会为其执行计算的行上溢出。条件为非零数字时视为真。

其他任何形式（如 `AND` 或调用其他函数）尚不支持。

---

## 阶段

### `WHERE` {#where}

保留满足条件的行：

```railroad
Diagram(
  Terminal('WHERE'),
  OneOrMore(
    Sequence(
      NonTerminal('column'),
      Choice(0,
        Sequence(NonTerminal('op'), NonTerminal('literal')),
        Sequence(Terminal('GLOB'), NonTerminal('string')),
        Sequence(Terminal('REGEXP'), NonTerminal('string')),
        Sequence(Terminal('IN'), Terminal('('),
                 OneOrMore(NonTerminal('literal'), Terminal(',')),
                 Terminal(')')),
        Sequence(Terminal('BETWEEN'), NonTerminal('literal'), Terminal('AND'),
                 NonTerminal('literal')),
        Sequence(Terminal('IS'), Optional(Terminal('NOT')), Terminal('NULL')))),
    Terminal('AND')))
```

- `<op>` 是 `=`、`==`、`!=`、`<>`、`<`、`<=`、`>` 和 `>=` 之一。
- `<literal>` 是整数、浮点或字符串字面量。
- `GLOB` 和 `REGEXP` 只匹配字符串列。
- 除非模式自身带有锚定，`REGEXP` 匹配字符串的一部分，与 SQL 的 `REGEXP` 行为一致。无法编译的模式会报错。
- `NULL` 永远不会匹配比较、`GLOB`、`REGEXP` 或 `IN`。整数与小数的比较方式与 SQL 一致。
- 字符串永远不会被转换为数字，数字也不会被转换为字符串。数值列与字符串比较、或字符串列与数字比较都会报错：`dur = '5'` 会失败并报错 `expected a number to compare with a numeric column, but got a string`。对 Perfetto 表执行普通 SQL 在这里不会报错：只是匹配不到任何行。
- 保留所有列和别名。
- 尚不支持：`OR`、`NOT`、`NOT IN`、`NOT GLOB`、`NOT REGEXP`、`LIKE`、圆括号、函数、算术运算，以及字面量在左侧的形式。请改在源子查询中过滤。

### `DISTINCT` {#distinct}

移除重复的行：

```railroad
Diagram(Terminal('DISTINCT'))
```

- 当两行在所有按裸名称可找到的列上都一致时，它们相等。`NULL` 之间视为相等。
- 只有通过别名才能找到的列（如交集的 `x.ts`）不参与比较，并且会被丢弃，因为它们在每行上没有唯一的值。别名会保留，只持有参与过比较的列。
- 每组相等的行只保留第一行，保留下来的行维持原有顺序。
- 行最多可以有 64 列。

### `ORDER BY` {#order-by}

对行排序：

```railroad
Diagram(
  Terminal('ORDER'), Terminal('BY'),
  OneOrMore(
    Sequence(NonTerminal('column'),
      Optional(Choice(0, Terminal('ASC'), Terminal('DESC')))),
    Terminal(',')))
```

- 第一个键决定顺序，后续每个键用来消解前面键相同时的并列。每个键默认为 `ASC`。
- 键是一个列，可以带限定符。尚不支持表达式。
- 字符串按其字节排序，与 SQLite 默认的 `BINARY` 排序规则一致。
- 与 SQLite 一致，升序时 `NULL` 排在最前，降序时排在最后。
- 在所有键上都相等的行保持原有顺序。
- 保留所有列和别名。
- `INTERVAL FLATTEN`、`INTERVAL FILL GAPS`、`TREE ACCUMULATE` 和 `AGGREGATE` 会以自己的方式排列行，因此应把 `ORDER BY` 放在它们之后。

### `LIMIT` {#limit}

跳过一些行后，保留最前面的行：

```railroad
Diagram(
  Terminal('LIMIT'), NonTerminal('count'),
  Optional(Sequence(Terminal('OFFSET'), NonTerminal('skipped'))))
```

- 按到达顺序跳过 `<skipped>` 行，然后最多保留 `<count>` 行。要保留排序后最前面的行，请把它放在 [`ORDER BY`](#order-by) 之后。
- `<count>` 和 `<skipped>` 是整数字面量。与 SQL 一致，负的 count 保留所有行，负的 offset 不跳过任何行。
- 保留所有列和别名。

### `INTERVAL FLATTEN` {#interval-flatten}

把重叠的区间切分成段，并对每段中处于活动状态的行做聚合：

```railroad
Diagram(
  Terminal('INTERVAL'), Terminal('FLATTEN'), Optional(NonTerminal('per-clause')),
  Terminal('AGGREGATE'), NonTerminal('aggregate-list'))
```

- **区间：**裸的 `ts` 和 `dur`，它们必须是整数列。输入不需要预先排序。
- **分组：**每种 `PER` 值的组合各自单独扁平化。没有 `PER` 时，所有行为一组。`NULL` 键归为一组。
- **聚合：**至少一个；参见[聚合](#aggregates)。每个聚合都在覆盖某个段的行上计算。
- **输出：**`ts`、`dur`、`PER` 列，然后是聚合列。其余所有列和所有别名都会被丢弃。列出两次的 `PER` 列会被输出两次，其名称因此变得有歧义。

区间规则：

- **段：**输出在每个输入的起点和终点处切分。没有行的间隙不产生输出。相邻的段即使值相同也不会合并。
- **点：**同一时刻上 `dur = 0` 的行会额外产生一个 `dur = 0` 的段。该段的聚合覆盖这些点以及在该时刻处于活动状态的区间：在该时刻开始的区间计入，在该时刻结束的区间不计入。点不计入其他段。
- **`NULL` 边界：**`ts` 或 `dur` 为 `NULL` 的行会被跳过。
- **负边界**会报错。请先过滤掉 `dur = -1` 的未完成 slice。
- **溢出**会报错。

示例参见[扁平化重叠区间](/docs/analysis/perfetto-sql-pipe-getting-started.md#flattening-overlapping-intervals-interval-flatten)。

### `INTERVAL FILL GAPS` {#interval-fill-gaps}

保留每一行，并为背景区间中没有任何行覆盖的每一段补一行：

```railroad
Diagram(
  Terminal('INTERVAL'), Terminal('FILL'), Terminal('GAPS'), Terminal('WITH'),
  NonTerminal('source'), Optional(NonTerminal('per-clause')))
```

`<source>` 持有背景区间。

- **区间：**裸的 `ts` 和 `dur`，输入和背景中都是如此。
- **泳道：**每种 `PER` 值的组合各自单独填充。背景要么拥有全部 `PER` 列，要么一个也没有：
  - 拥有时，它指明存在哪些泳道。没有输入的泳道会被整条填充，而背景中没有的泳道里的输入不会得到填充行。
  - 没有时，同一背景作用于输入中的每条泳道。
- **填充行**按名称取背景各列的值，取其所在泳道的 `PER` 值，其余所有列均为 `NULL`。背景的每一列也必须出现在输入中。
- **类型：**一个列在两个输入中只能有一种类型。一个输入中为字符串、另一个中为数字的列会报错。
- **输出：**输入的列。行以任意顺序输出。别名会保留。

区间规则：

- 相互重叠的输入行覆盖它们的并集。
- `dur = -1` 的输入行覆盖其 `ts` 之后的全部时间。
- `ts` 为 `NULL` 的输入行不覆盖任何时间，但仍然会被输出。
- 点不会分割填充行。
- 输入的 `ts` 为负会报错。
- 同一泳道内相互重叠的背景行会报错。

示例参见[填充间隙](/docs/analysis/perfetto-sql-pipe-getting-started.md#filling-gaps-interval-fill-gaps)。

### `TREE ACCUMULATE` {#tree-accumulate}

沿树向上或向下做聚合：

```railroad
Diagram(
  Terminal('TREE'), Terminal('ACCUMULATE'),
  Choice(0, Terminal('UP'), Terminal('DOWN')),
  NonTerminal('aggregate-list'))
```

- **树：**裸的 `id` 和 `parent_id`。根节点满足 `parent_id IS NULL`。
- **方向：**
  - `UP`：每个节点的聚合覆盖它自身及其所有后代。行按子节点在前的顺序输出。
  - `DOWN`：每个节点的聚合覆盖它自身及其所有祖先。行按父节点在前的顺序输出。
- **聚合：**参见[聚合](#aggregates)。沿 `DOWN` 方向的 `COUNT(*)` 即节点的深度，从 1 开始计。
- **输出：**所有输入列，然后是聚合列。别名会保留，但不包含新增的列。
- **错误：**两行共用一个 `id`、某行是它自己的父节点、`parent_id` 没有对应 `id` 的行。只有当后续阶段读取某个聚合时才会做这些检查；否则该阶段会被跳过。

### `AGGREGATE` {#aggregate}

把每一组行折叠为一行：

```railroad
Diagram(
  Terminal('AGGREGATE'), NonTerminal('aggregate-list'),
  Optional(NonTerminal('group-by')))
```

```railroad group-by
Diagram(
  Terminal('GROUP'), Terminal('BY'),
  OneOrMore(
    Sequence(NonTerminal('column'),
      Optional(Sequence(Terminal('AS'), NonTerminal('name')))),
    Terminal(',')))
```

- **分组：**在每个 `GROUP BY` 列上都一致的行构成一组。键可以是任何类型，也可以带限定符。`NULL` 键归为一组。没有 `GROUP BY` 时，所有行为一组，即使没有任何行也会产出一行。
- **聚合：**至少一个；参见[聚合](#aggregates)。
- **输出：**先输出各键，然后是聚合列。键以其 `AS` 名称命名，否则以其不带限定符的列名命名。其余所有列和所有别名都会被丢弃。重复列出的键（即使分别写作 `cpu` 和 `t.cpu`）只分组一次，但会被输出两次。
- **顺序：**分组按其第一行到达的顺序输出。

例如，计算每个 slice 的 CPU 时间：

```sql
INCLUDE PERFETTO MODULE slices.with_context;

INTERVAL INTERSECTION OF (
  (SELECT id, ts, dur, utid FROM thread_slice WHERE dur > 0) AS s,
  (SELECT ts, dur, utid FROM sched WHERE dur > 0) AS running
) PER utid
|> AGGREGATE SUM(dur) AS cpu_time GROUP BY s.id
|> ORDER BY id;
```

### `SELECT` {#select}

用列出的各项替换当前行，并清除所有别名：

```railroad
Diagram(Terminal('SELECT'), OneOrMore(NonTerminal('item'), Terminal(',')))
```

每个 `<item>` 是以下之一：

```railroad item
Diagram(Choice(0,
  Sequence(NonTerminal('column'),
    Optional(Sequence(Terminal('AS'), NonTerminal('name')))),
  NonTerminal('star')))
```

- **列。**不带 `AS` 时保留其名称。
- **表达式**（参见[表达式](#expressions)）需带 `AS` 和名称。
- **`<star>`：**

```railroad star
Diagram(
  Optional(Sequence(NonTerminal('alias'), Terminal('.'))), Terminal('*'),
  Optional(NonTerminal('except')), Optional(NonTerminal('replace')))
```

```railroad except
Diagram(
  Terminal('EXCEPT'), Terminal('('),
  OneOrMore(NonTerminal('name'), Terminal(',')), Terminal(')'))
```

```railroad replace
Diagram(
  Terminal('REPLACE'), Terminal('('),
  OneOrMore(
    Sequence(NonTerminal('column'), Terminal('AS'), NonTerminal('target')),
    Terminal(',')),
  Terminal(')'))
```

星号的工作方式如下：

1. `*` 即按裸名称可找到的列。在 `INTERVAL INTERSECTION OF` 之后，这不包括每个源自己的 `ts` 和 `dur`。`<alias>.*` 是该别名被设置时所持有的列。
2. `EXCEPT` 移除与所列名称对应的所有列。每个名称都必须至少匹配一列且只能列出一次，并且必须至少保留一列。
3. `REPLACE (<column> AS <target>)` 把 `<column>` 的值放入 `<target>`，并保持 `<target>` 的名称和位置。`<column>` 在该阶段之前的行中查找；`<target>` 必须是 `EXCEPT` 之后剩下的恰好一列。
4. 星号添加的每一列在后续阶段中都可以按裸名称引用。

### `EXTEND` {#extend}

在行的末尾添加列，保留所有列和别名：

```railroad
Diagram(Terminal('EXTEND'), OneOrMore(NonTerminal('item'), Terminal(',')))
```

- 各项与 `SELECT` 相同，但不允许裸的 `*`。请使用 `<alias>.*` 来添加某个别名的列。
- 各项读取的都是该阶段之前的行，因此某一项不能引用另一项。
- 别名不包含新增的列。

### `DROP` {#drop}

按名称移除列：

```railroad
Diagram(Terminal('DROP'), OneOrMore(NonTerminal('name'), Terminal(',')))
```

- 每个名称都必须匹配一个按裸名称可找到的列，并移除该名称的所有列。
- 每个名称只能列出一次，并且必须至少保留一列。
- 别名保留被删除的列。与被删除列同名的别名会被移除。

### `RENAME` {#rename}

就地重命名列：

```railroad
Diagram(
  Terminal('RENAME'),
  OneOrMore(
    Sequence(NonTerminal('old'), Terminal('AS'), NonTerminal('new')),
    Terminal(',')))
```

- 每个 `<old>` 必须是按裸名称可找到的恰好一列，且只能列出一次。
- 所有重命名同时生效，因此 `|> RENAME x AS y, y AS x` 会交换 `x` 和 `y`。
- 允许重命名为已存在的名称；该名称因此变得有歧义。
- 别名保留旧名称。

### `SET` {#set}

就地替换列的值：

```railroad
Diagram(
  Terminal('SET'),
  OneOrMore(
    Sequence(NonTerminal('target'), Terminal('='), NonTerminal('column')),
    Terminal(',')))
```

- 每个 `<target>` 必须是按裸名称可找到的恰好一列，且只能列出一次。
- 每个 `<column>` 都在该阶段之前的行中查找。因此 `|> SET x = y, y = x` 会交换 `x` 和 `y` 的值。它也可以是一个[表达式](#expressions)。
- 别名保留旧值。与某个目标同名的别名会被移除。

### `AS` {#as}

用一个绑定到当前行的别名替换所有别名：

```railroad
Diagram(Terminal('AS'), NonTerminal('alias'))
```

在 `|> AS u` 之后，先前的别名不复存在，`u.<col>` 和 `u.*` 即此刻按裸名称可找到的列。在 `INTERVAL INTERSECTION OF` 之后，`u.ts` 是区域的 `ts`，各源自己的 `ts` 和 `dur` 无法再被访问。

---

## 名称

- **大小写：**列名和别名的匹配不区分 ASCII 大小写。输出保留它们被定义时的大小写。
- **重复：**某个阶段可以让两列共用一个名称，例如在 `y` 已存在时执行 `|> RENAME x AS y`。只有当后续阶段不加限定符地引用该名称时才会出错。`DROP y` 或 `* EXCEPT (y)` 会移除所有副本。
- **引号：**名称可以用 `"..."`、`` `...` `` 或 `[...]` 括起来。在 `"..."` 和 `` `...` `` 内部，双写的引号表示字面引号。
