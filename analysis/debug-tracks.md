# Debug Tracks

Debug Tracks 是一种将 PerfettoSQL 查询的表格结果显示为"debug" track 的方式。具体来说，如果结果表可以以 slice 格式可视化（例如 [`slice`](sql-tables.autogen#slice) 表）或 counter 格式（例如 [`counter`](sql-tables.autogen#counter) 表），则可以从中创建 debug track。

要可视化结果表，它应该包含：

1. name（slice 的名称）列
1. 非空 timestamp（slice 开始时的时间戳，以纳秒为单位）列
1. （对于 `slice` tracks）duration（slice 的持续时间，以纳秒为单位）列
1. （可选）要透视的列的名称

 注意：透视允许你为所选"pivot"列中的每个不同值创建一个 debug track。

## 创建 Debug `slice` Tracks

要创建 `slice` tracks：

1. 运行 SQL 查询，并确保其结果是 `slice` 类型的（如上所述）。
 ![Query for debug slice track](/docs/images/debug-tracks/slice-track-query.png)
1. 导航到"Show Timeline"视图，然后点击"Show debug track"来设置新的 debug track。从 Track 类型下拉菜单中选择"slice"。

 注意：结果表中的列名不一定必须是 `name`、`ts` 或 `dur`。可以从下拉选择器中选择语义匹配但名称不同的列。

 ![Create a new debug slice track](/docs/images/debug-tracks/slice-track-create.png)

1. debug slice track 显示为 Timeline 视图顶部附近的固定 track，其中包含从中创建 track 的表中的 slice（注意：没有持续时间的 slice 将显示为即时事件）。Debug tracks 可以手动取消固定，并显示在其他未固定 tracks 的顶部。
 ![Resultant debug track](/docs/images/debug-tracks/slice-track-result.png)

1. （可选）通过从"pivot"列中选择值来创建透视 `slice` tracks。

 注意：你可以通过输入 `:` 进入 SQL 模式，直接在搜索框中输入查询。

 ![Creating pivoted debug slice tracks](/docs/images/debug-tracks/pivot-slice-tracks-create.png)

 这将为每个不同的 pivot 值创建一个 debug slice track。

 ![Resultant pivoted debug slice tracks](/docs/images/debug-tracks/pivot-slice-tracks-results.png)

## 创建 Debug `counter` Tracks

你可以按照与上述类似的步骤创建新的 debug `counter` tracks：

1. 运行 SQL 查询，并确保其结果是 `counter` 类型的（如上所述）。

 ![Query for debug counter track](/docs/images/debug-tracks/counter-tracks-query.png)
1. 导航到 Timeline 视图，然后点击"Show debug track"来设置新的 debug track。从 Track 类型下拉菜单中选择"counter"，并选择语义匹配的感兴趣列名。

 ![Create a new debug counter track](/docs/images/debug-tracks/counter-tracks-create.png)

1. counter track 将显示为 Timeline 视图顶部附近的固定 track。

 ![Resultant pivoted debug counter track](/docs/images/debug-tracks/counter-tracks-results.png)

1. （可选）通过从"pivot"列中选择值来创建透视 `counter` tracks。

 ![Create a new debug counter track](/docs/images/debug-tracks/pivot-counter-tracks-create.png)

 这将为每个不同的 pivot 值创建一个 debug counter track。

 ![Resultant pivoted debug counter track](/docs/images/debug-tracks/pivot-counter-tracks-results.png)
