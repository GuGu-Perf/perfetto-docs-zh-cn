# 命令自动化参考

本文档记录了 Perfetto UI 的稳定 command surface，专门用于自动化用例。这些命令具有向后兼容性保证，可以安全地用于自动化工作流、启动配置、macros 和 deep linking。

## 概览

虽然 Perfetto UI 在内部使用 commands 进行所有用户交互，但本参考专门关注用于自动化目的的稳定命令子集。这些稳定的自动化命令专为以下用途设计：

- **Startup commands** - 加载 trace 时自动配置 UI
- **Macros** - 为复杂的分析任务创建可重用工作流
- **Deep linking** - 通过 URLs 或 postMessage 共享预配置视图

此自动化参考之外的命令是内部实现细节，没有向后兼容性保证，可能会在不警告的情况下更改。

## 向后兼容性保证

对于本参考中列出的自动化命令，Perfetto UI 保证：

- **Stable command IDs** - 命令标识符（例如，`dev.perfetto.RunQuery`）不会更改
- **Stable required arguments** - 现有的必需参数将继续以相同的语义工作
- **Consistent behavior** - 核心功能将在更新中保留
- **Advance notice of changes** - 任何重大更改将：
  - 在 CHANGELOG 中发布
  - 在更改生效前至少 6 个月宣布

可能会在不通知的情况下向命令添加可选参数，但不会影响现有用法。

## 命令参考

### Track 操作命令

这些命令控制 tracks 在 Timeline 视图中的显示方式。

#### `dev.perfetto.PinTracksByRegex`

将匹配正则表达式模式的 tracks 固定到 Timeline 顶部。

**参数：**

- `pattern` (string, required): 用于匹配 track 名称或路径的正则表达式
- `nameOrPath` (string, optional): 是匹配 track 名称 ("name") 还是 track 路径 ("path")。默认为 "name"

**Track 名称 vs 路径:**

- Track 名称: `"RenderThread"`
- Track 路径: `"com.example.app > RenderThread"`

**示例：**

```json
{
  "id": "dev.perfetto.PinTracksByRegex",
  "args": [".*surfaceflinger.*"]
}
```

**Example with track path filtering:**

```json
{
  "id": "dev.perfetto.PinTracksByRegex",
  "args": [".*com\\.example\\.app.*RenderThread.*", "path"]
}
```

**常见模式：**

- Pin CPU tracks: `".*CPU \\d+$"`
- Pin specific process: `".*com\\.example\\.app.*"`
- Pin multiple processes: `".*(system_server|surfaceflinger).*"`

---

#### `dev.perfetto.ExpandTracksByRegex`

展开匹配正则表达式模式的 track groups。

**参数：**

- `pattern` (string, required): 用于匹配 track group 名称或路径的正则表达式
- `nameOrPath` (string, optional): 是匹配 track 名称 ("name") 还是 track 路径 ("path")。默认为 "name"

**Track 名称 vs 路径:**

- Track 名称: `"RenderThread"`
- Track 路径: `"com.example.app > RenderThread"`

**示例：**

```json
{
  "id": "dev.perfetto.ExpandTracksByRegex",
  "args": [".*system_server.*"]
}
```

**Example with track path filtering:**

```json
{
  "id": "dev.perfetto.ExpandTracksByRegex",
  "args": [".*system_server.*RenderThread.*", "path"]
}
```

---

#### `dev.perfetto.CollapseTracksByRegex`

折叠匹配正则表达式模式的 track groups。

**参数：**

- `pattern` (string, required): 用于匹配 track group 名称或路径的正则表达式
- `nameOrPath` (string, optional): 是匹配 track 名称 ("name") 还是 track 路径 ("path")。默认为 "name"

**Track 名称 vs 路径:**

- Track 名称: `"RenderThread"`
- Track 路径: `"com.example.app > RenderThread"`

**示例：**

```json
{
  "id": "dev.perfetto.CollapseTracksByRegex",
  "args": ["CPU Scheduling"]
}
```

**Example with track path filtering:**

```json
{
  "id": "dev.perfetto.CollapseTracksByRegex",
  "args": [".*com\\.example\\.app.*", "path"]
}
```

**提示：** Use `".*"` 将所有 tracks 折叠作为专注分析的起点。

### Debug Track 命令

从 SQL 查询创建自定义可视化 tracks。Debug tracks 叠加在 Timeline 上，并在视图更改时自动更新。

**重要:** 如果你的查询使用 Perfetto 模块（例如，`android.screen_state`、`android.memory.lmk`），你必须首先执行带有模块 include 语句的 `RunQuery` 命令，然后才能创建 debug track。模块 include 必须位于命令序列中的第一位。

#### `dev.perfetto.AddDebugSliceTrack`

从返回时间间隔的 SQL 查询创建 slice track。

**参数：**

1. `query` (string, required): 必须返回以下内容的 SQL 查询：
    - `ts` (number): 时间戳（纳秒）
    - `dur` (number): 持续时间（纳秒）
    - `name` (string): 要显示的 slice 名称
2. `title` (string, required): track 的显示名称

**示例：**

```json
{
  "id": "dev.perfetto.AddDebugSliceTrack",
  "args": [
    "SELECT ts, dur, name FROM slice WHERE dur > 10000000 ORDER BY dur DESC LIMIT 100",
    "Long Slices (>10ms)"
  ]
}
```

---

#### `dev.perfetto.AddDebugSliceTrackWithPivot`

按 pivot 列分组创建多个 slice tracks。pivot 列中的每个唯一值都有自己的 track。

**参数：**

1. `query` (string, required): 必须返回以下内容的 SQL 查询：
    - `ts` (number): 时间戳（纳秒）
    - `dur` (number): 持续时间（纳秒）
    - `name` (string): Slice 名称以显示
    - 用于 pivoting 的附加列
2. `pivotColumn` (string, required): 用于分组 tracks 的列名
3. `title` (string, required): track group 的基本标题

**示例：**

```json
{
  "id": "dev.perfetto.AddDebugSliceTrackWithPivot",
  "args": [
    "SELECT ts, dur, name, IFNULL(category, '[NULL]') as category FROM slice WHERE dur > 1000000",
    "category",
    "Slices by Category"
  ]
}
```

**注意：** 使用 `IFNULL()` 处理 pivot 列中的 NULL 值，因为 NULL 会导致命令失败。

---

#### `dev.perfetto.AddDebugCounterTrack`

从返回时间序列数据的 SQL 查询创建 counter track。

**参数：**

1. `query` (string, required): 必须返回以下内容的 SQL 查询：
    - `ts` (number): 时间戳（纳秒）
    - `value` (number): Counter 值
2. `title` (string, required): track 的显示名称

**示例：**

```json
{
  "id": "dev.perfetto.AddDebugCounterTrack",
  "args": ["SELECT ts, value FROM counter WHERE track_id = 42", "Memory Usage"]
}
```

---

#### `dev.perfetto.AddDebugCounterTrackWithPivot`

按 pivot 列分组创建多个 counter tracks。

**参数：**

1. `query` (string, required): 必须返回以下内容的 SQL 查询：
    - `ts` (number): 时间戳（纳秒）
    - `value` (number): Counter 值
    - 用于 pivoting 的附加列
2. `pivotColumn` (string, required): 用于分组 tracks 的列名
3. `title` (string, required): track group 的基本标题

**示例：**

```json
{
  "id": "dev.perfetto.AddDebugCounterTrackWithPivot",
  "args": [
    "SELECT ts, value, name FROM counter JOIN counter_track ON counter.track_id = counter_track.id",
    "name",
    "System Counters"
  ]
}
```

### Workspace 命令

Workspaces 允许你通过将特定的 tracks 组织在一起来创建 trace 数据的自定义视图。

#### `dev.perfetto.CreateWorkspace`

创建一个新的空 workspace。

**参数：**

- `title` (string, required): 新 workspace 的名称

**示例：**

```json
{
  "id": "dev.perfetto.CreateWorkspace",
  "args": ["Memory Analysis"]
}
```

---

#### `dev.perfetto.SwitchWorkspace`

按名称切换到现有 workspace。

**参数：**

- `title` (string, required): 要切换到的 workspace 名称

**示例：**

```json
{
  "id": "dev.perfetto.SwitchWorkspace",
  "args": ["Memory Analysis"]
}
```

**注意：** 在切换到 workspace 之前，该 workspace 必须已经存在。

---

#### `dev.perfetto.CopyTracksToWorkspaceByRegex`

将匹配模式的 tracks 复制到 workspace。

**参数：**

1. `pattern` (string, required): 用于匹配 track 名称或路径的正则表达式
2. `workspaceTitle` (string, required): 目标 workspace 名称
3. `nameOrPath` (string, optional): 是匹配 track 名称 ("name") 还是 track 路径 ("path")。默认为 "name"

**Track 名称 vs 路径：**

- Track 名称: `"RenderThread"`
- Track 路径: `"com.example.app > RenderThread"`

**示例：**

```json
{
  "id": "dev.perfetto.CopyTracksToWorkspaceByRegex",
  "args": ["(Expected|Actual) Timeline", "Frame Analysis"]
}
```

**使用 track 路径过滤的示例：**

```json
{
  "id": "dev.perfetto.CopyTracksToWorkspaceByRegex",
  "args": [".*com\\.example\\.app.*RenderThread.*", "Frame Analysis", "path"]
}
```

---

#### `dev.perfetto.CopyTracksToWorkspaceByRegexWithAncestors`

将匹配模式的 tracks 复制到 workspace，包括其父 track 组以提供上下文。

**参数：**

1. `pattern` (string, required): 用于匹配 track 名称或路径的正则表达式
2. `workspaceTitle` (string, required): 目标 workspace 名称
3. `nameOrPath` (string, optional): 是匹配 track 名称 ("name") 还是 track 路径 ("path")。默认为 "name"

**Track 名称 vs 路径：**

- Track 名称: `"RenderThread"`
- Track 路径: `"com.example.app > RenderThread"`

**示例：**

```json
{
  "id": "dev.perfetto.CopyTracksToWorkspaceByRegexWithAncestors",
  "args": ["RenderThread", "Rendering Analysis"]
}
```

**使用 track 路径过滤的示例：**

```json
{
  "id": "dev.perfetto.CopyTracksToWorkspaceByRegexWithAncestors",
  "args": [
    ".*com\\.example\\.app.*RenderThread.*",
    "Rendering Analysis",
    "path"
  ]
}
```

### 查询命令

#### `dev.perfetto.RunQuery`

执行 PerfettoSQL 查询而不显示结果。

**参数：**

- `query` (string, required): 要执行的 PerfettoSQL 查询

**示例：**

```json
{
  "id": "dev.perfetto.RunQuery",
  "args": [
    "CREATE PERFETTO FUNCTION my_func(x INT) RETURNS INT AS SELECT $x * 2"
  ]
}
```

---

#### `dev.perfetto.RunQueryAndShowTab`

执行 PerfettoSQL 查询并在新的查询标签页中显示结果。

**参数：**

1. `query` (string, required): 要执行的 PerfettoSQL 查询
2. `title` (string, optional): 查询标签页的标题

**示例：**

```json
{
  "id": "dev.perfetto.RunQueryAndShowTab",
  "args": ["SELECT ts, dur, name FROM slice LIMIT 50"]
}
```

**带标签页标题的示例：**

```json
{
  "id": "dev.perfetto.RunQueryAndShowTab",
  "args": ["SELECT ts, dur, name FROM slice LIMIT 50", "Top 50 Slices"]
}
```

### 笔记命令

#### `dev.perfetto.AddNoteAtTimestamp`

在 trace 时钟的给定时间戳添加具有特定文本的笔记。

**参数：**

1. `timestamp` (string, required): trace 时钟中的时间戳（纳秒）
2. `text` (string, required): 笔记的文本

**示例：**

```json
{
  "id": "dev.perfetto.AddNoteAtTimestamp",
  "args": [
    "1771711048774386000",
    "A specific event happened"
  ]
}
```

### 宏命令

宏是用户定义的按顺序执行的命令序列。它们提供了一种自动化复杂多步分析工作流的方式。

#### 用户定义的宏

宏可以通过 UI 设置（**设置 > 宏**）定义。每个宏都有一个你定义的唯一 ID，该 ID 成为用于调用它的命令 ID。

**命令模式：**

- `{macro.id}` - 执行具有指定 ID 的宏

**参数：**

无（宏命令和参数是预先配置的）

**示例：**

```json
{
  "id": "user.myteam.MyAnalysisWorkflow",
  "args": []
}
```

**注意：**

- 每个宏包含按顺序执行的命令序列
- 宏 ID 应使用反向域名风格的命名（例如，`user.myteam.MacroName`、`com.company.AnalysisWorkflow`）
- 当用作启动命令时，宏中的所有命令也必须在允许列表中
- 宏可以包含本参考中的任何稳定自动化命令
- 宏中的失败命令会被记录，但不会停止剩余命令的执行

> **注意（迁移）：** 宏的格式已从字典更改为数组结构。现有的宏已自动迁移，并使用格式为 `dev.perfetto.UserMacro.<old_name>` 的 ID。新宏应使用反向域名风格的 ID。

### 导航命令

#### `dev.perfetto.GoToTime`

导航到 trace 中的特定时间戳。

**参数：**

- `time` (number, required): 时间戳（纳秒）

**示例：**

```json
{
  "id": "dev.perfetto.GoToTime",
  "args": [1000000000]
}
```

---

#### `dev.perfetto.SelectArea`

选择特定的时间范围。

**参数：**

- `start` (number, required): 开始时间戳（纳秒）
- `end` (number, required): 结束时间戳（纳秒）

**示例：**

```json
{
  "id": "dev.perfetto.SelectArea",
  "args": [1000000000, 2000000000]
}
```

### 可视化命令

#### `dev.perfetto.ShowCurrentSelectionTab`

显示 "Current Selection" 标签页。

**参数：** 无

**示例：**

```json
{
  "id": "dev.perfetto.ShowCurrentSelectionTab"
}
```

---

#### `dev.perfetto.PinJankyFrameTracks`

固定所有 janky frame tracks。

**参数：** 无

**示例：**

```json
{
  "id": "dev.perfetto.PinJankyFrameTracks"
}
```

---

#### `dev.perfetto.ShowStackTrace`

显示所选事件的 stack trace。

**参数：** 无

**示例：**

```json
{
  "id": "dev.perfetto.ShowStackTrace"
}
```

---

## 使用命令进行自动化

这些稳定的自动化命令可以在多种上下文中使用：

- **启动命令** - 加载 trace 时自动运行。请参阅 UI 自动化指南中的[启动命令](/docs/visualization/ui-automation.md#commands-system-overview)。
- **宏** - 用于按需执行的命名命令序列。请参阅 UI 自动化指南中的[宏](/docs/visualization/ui-automation.md#commands-system-overview)。
- **URL 深度链接** - 在 URL 或 postMessage 中嵌入命令。有关 URL 模式和 postMessage 集成，请参阅[深度链接](/docs/visualization/deep-linking-to-perfetto-ui.md#configuring-the-ui-with-startup-commands)。

有关实用的自动化示例和技巧，请参阅 [UI 自动化指南](/docs/visualization/ui-automation.md)。

## 请求新的稳定自动化命令

要请求将命令添加到稳定自动化界面：

1. 在 https://github.com/google/perfetto/issues 提交 issue
2. 包括：
   - 你需要稳定的命令 ID
   - 你的用例以及为什么稳定性很重要
   - 显示你计划如何使用它的示例用法

命令的优先级基于：

- 在自动化场景中的使用频率
- 对常见分析工作流的重要性
- 保持向后兼容性的可行性

## 另请参阅

- [UI 自动化指南](/docs/visualization/ui-automation.md) - 使用这些命令的实用技巧
- [Perfetto UI 指南](/docs/visualization/perfetto-ui.md) - 包括命令的一般 UI 文档
- [深度链接](/docs/visualization/deep-linking-to-perfetto-ui.md) - 使用预配置命令打开 traces

