# AI Agent 的 Perfetto UI 开发

Perfetto UI 是一个使用 Mithril 框架用 TypeScript 编写的单页 Web 应用程序。它位于 `ui/` 中，并为 ui.perfetto.dev 提供动力。UI 通过 WebAssembly 嵌入 TraceProcessor。

## 一般原则

- **不要过度设计** - 解决手头的问题，而不是假设的未来问题。
- **优先选择更简单的方法** - 如果有简单解决方案和复杂解决方案，请选择简单解决方案。
- **创建之前先搜索** - 编写新实用程序之前，始终搜索现有实用程序。
- **保持一致** - 遵循周围代码中建立的模式。
- **优先选择具有不可变只读成员的接口** - 我们喜欢不可变性，使代码更容易调试。

## 目录结构

UI 代码库组织如下：

```text
ui/src/
├── base/ # 核心实用程序(时间、颜色、数组、记录、可处置对象)
├── widgets/ # 可重用的 UI 组件(Button、Menu、Modal、Popup 等)
├── components/ # 更高级别的组件(聚合面板、查询表)
├── core/ # 核心应用程序逻辑和管理器
├── public/ # 插件的公共 API 表面
├── plugins/ # 可选的第三方/外部插件
├── core_plugins/ # 必需的核心插件(无法禁用)
├── frontend/ # 主要前端渲染代码
├── trace_processor/# Engine communication layer (query results, SQL utilities)
├── test/ # Playwright 集成测试
└── assets/ # SCSS 样式表和静态资产
```

在可能的情况下（如果 API 表面允许），功能功能应封装在 src/plugins 中的插件内。
- `core_plugins/`（例如，`dev.perfetto.CoreCommands`、`dev.perfetto.Notes`）包含必需功能。用户无法禁用它们，并且它们始终处于活动状态。
- `plugins/`（例如，`dev.perfetto.Sched`、`com.android.AndroidStartup`）是可选的。用户可以通过功能标志启用/禁用它们。这些按反向 DNS 命名组织（例如，`com.android.*`、`dev.perfetto.*`、`org.chromium.*`）。
- 这种区别主要是历史性的。如今，在 90% 的情况下，事物可以（并且应该）仅放在 plugins/ 内部
- 查看 /docs/contributing/ui-plugins.md，因为它包含对插件作者额外的有用内容。

## 构建和运行 UI

要为开发构建和服务 UI:

```sh
# 从仓库根目录
ui/build    # 构建 UI
ui/build --typecheck # 运行 tsc --noEmit，不打包（更快）
ui/run-dev-server    # 启动具有实时重新加载的开发服务器
```

UI 使用：

- **TypeScript** 以实现类型安全
- **Mithril** 作为 UI 框架
- **Vite** 用于打包
- **pnpm** 用于包管理
- **ESLint** 用于 linting(基于 Google 风格)
- **Playwright** 用于集成测试

## 构建运行时进行类型检查

每个构建在工作时都会声明一个锁文件，除非传递了 --no-build 选项。如果你尝试运行构建但由于其中一个锁文件存在而遇到失败，你可以尝试仅使用以下命令检查类型，而不会干扰当前构建。

```sh
ui/build --typecheck --no-build
```

## 插件架构

插件是 UI 的主要扩展机制。它们遵循此结构：

```typescript
import {PerfettoPlugin} from '../../public/plugin';
import {Trace} from '../../public/trace';
import {App} from '../../public/app';

export default class MyPlugin implements PerfettoPlugin {
 // 唯一的反向 DNS 标识符
  static readonly id = 'com.example.MyPlugin';

 // 可选:可读描述
  static readonly description = 'Does something useful';

 // 可选:声明对其他插件的依赖
  static readonly dependencies = [OtherPlugin];

 // 当插件被激活时调用(在 trace 加载之前)
  static onActivate(app: App): void {
 // 注册不需要 trace 的命令、侧边栏项、页面
  }

 // 当加载 trace 时调用
  async onTraceLoad(trace: Trace): Promise<void> {
 // 注册需要 trace 数据的 Track、选项卡、命令
 // 查询 trace processor,将 Track 添加到工作区
  }
}
```

**插件生命周期：**

1. `onActivate()` - 当插件被启用时，在加载任何 trace 之前调用。用于注册全局命令、页面和侧边栏项。
2. `onTraceLoad()` - 当加载 trace 时调用。用于注册依赖于 trace 数据的 Track、选项卡和命令。
3. `trace.onTraceReady` 事件 - 在所有插件完成 `onTraceLoad()` 后触发。用于需要所有 Track 可用的自动化。

**插件可用的关键 API:**

- `trace.engine` - 针对 TraceProcessor 运行 SQL 查询
- `trace.tracks` - 注册和查找 Track
- `trace.selection` - 管理选择状态
- `trace.commands` - 注册命令
- `trace.tabs` - 在详细信息面板中注册选项卡
- `trace.timeline` - 访问时间轴状态
- `trace.workspaces`、`trace.currentWorkspace` - 管理 Track 树结构

## Mithril 模式和最佳实践

UI 使用 Mithril.js。遵循这些模式：

**组件结构：**
```typescript
import m from 'mithril';

interface MyComponentAttrs {
  readonly value: string;
  readonly onChange: (newValue: string) => void;
}

export class MyComponent implements m.ClassComponent<MyComponentAttrs> {
 // 本地状态
  private expanded = false;

  view({attrs}: m.CVnode<MyComponentAttrs>): m.Children {
    return m('.my-component',
      m(Button, {label: attrs.value, onclick: () => this.expanded = !this.expanded}),
      this.expanded && m('.details', 'Expanded content'),
    );
  }
}
```

**Mithril 规则：**

- 大多数时候不需要调用 `m.redraw()`。我们自动安排重新绘制：(1) 在 Mithril 的 DOM 事件处理程序中;(2) 在 trace processor 查询完成之后。但不在手动注册的 JS 事件处理程序之后。
- 如果不需要 DOM 访问，请使用 `constructor` 进行初始化，如果需要 DOM，则使用 `oncreate`。
- 优先使用现有小部件库（`ui/src/widgets/`）而不是创建新组件。
- 对 attrs 属性使用 `readonly` 以防止意外修改。我们喜欢事物是不可变的。

**保持状态的条件渲染：**
当需要条件显示/隐藏内容同时保持组件状态时，请使用 `Gate` 组件：

```typescript
import {Gate} from '../base/mithril_utils';

m(Gate, {open: this.isVisible}, m(ExpensiveComponent));
```

### 声明式数据加载（`AsyncMemo`）

Mithril 中的 UI 组件是同步渲染的，但通常依赖异步数据（例如 SQL 查询）。**绝不要在生命周期钩子（`oninit`/`onupdate`）中使用手动的 `loading` 布尔值、序列计数器（`fetchSeq`）或 `prevId` 跟踪来手工实现数据获取。**同样，**避免直接在 DOM 事件处理程序（`onclick`、`onkeydown` 等）内部发起数据获取**。加载应该是状态的声明式产物，它可能从许多不同的地方触发（例如键盘快捷键、外部选择、深层链接）。在事件处理程序中更新状态，让重新绘制机制自动处理数据加载。

#### 使用 `AsyncMemo`

`AsyncMemo<T>` 在 `view()` 内部直接提供声明式的、基于 key 的异步获取：

```typescript
import m from 'mithril';
import {AsyncMemo, TASK_CANCELLED} from '../base/async_memo';

export function MyComponent(): m.Component<MyComponentAttrs> {
  // 1. 每个组件实例化一次（闭包或类字段），绝不要在 view() 内部实例化，因为缓存存储在这里。
  const dataMemo = new AsyncMemo<MyData>();

  return {
    view({attrs}) {
      // 2. 通过 `key` 声明依赖。key 更改时 compute() 自动运行。
      const result = dataMemo.use({
        key: {traceId: attrs.trace.id, filter: attrs.filter},
        compute: async (signal) => {
          const summary = await querySummary(attrs.trace.engine, attrs.filter);

          // 可选：检查取消状态，以便在被取代或处置时提前退出。
          if (signal.isCancelled) return TASK_CANCELLED;

          const details = await queryDetails(attrs.trace.engine, attrs.filter);
          return {summary, details};
        },
        // 可选：当仅某些 key 更改时，在获取期间显示旧数据
        retainOn: ['filter'],
      });

      if (result.isPending) {
        return m(Spinner);
      }

      return m('.my-component', renderData(result.data));
    },
    onremove() {
      // 3. 可选：在卸载时处置 memo，以取消待处理任务或提前清理资源
      dataMemo.dispose();
    },
  };
}
```

**`AsyncMemo` 的关键行为：**
- **key 按值比较（结构相等）**：`key` 可以是任何 JSON 兼容的结构（原始类型、对象、数组、bigint）。key 通过 `stringifyJsonWithBigints` 序列化并按值而非对象引用比较，因此传递渲染期间创建的对象字面量（例如 `key: {traceId: attrs.trace.id, filter: attrs.filter}`）只会在其内容实际更改时才触发重新获取。当 key 更改时，任何待处理任务都会被取代（"最新者获胜"）。
- **自动重新绘制**：`AsyncMemo` 在 `compute` 完成时自动调用 `m.redraw()`。绝不要在 `compute` 内部手动调用 `m.redraw()`。
- **并发控制**：任务通过内部的 `AtomicTaskQueue` 串行执行，防止对共享资源（如临时表）的交错查询。如果需要，多个 memo 可以共享一个 `AtomicTaskQueue`。
- **取消**：`compute` 接收一个 `CancellationSignal`。长任务可以检查 `signal.isCancelled` 并返回 `TASK_CANCELLED`，以避免缓存过期的结果。
- **过期过渡（`retainOn`）**：如果你指定 `retainOn: ['pagination']`，更改分页将继续返回之前的 `result.data` 并带有 `result.isPending = true`，避免获取期间视觉闪烁。
- **自动资源处置（`AsyncDisposable`）**：如果返回的值是可处置的（实现了 `AsyncDisposable`），它会在不再需要时自动被处置——具体来说，当新值在 key 更改后替换它时、当调用 `memo.invalidate()` 时，或当 memo 本身在 `onremove()` 中被处置时。处置通过任务队列协调，因此与进行中的工作保持同步。
- **`compute` 函数应无副作用**：`compute` 函数应仅派生数据或管理缓存的 SQL 结构。不要在 `compute` 内部修改外部状态。唯一允许的副作用是临时 SQL 实体（表、视图、索引）——并且这些**必须在返回的 disposable（`AsyncDisposable`）中删除**，以便在驱逐或失效时自动清理。

#### 多步操作与 `AtomicTaskQueue`

当一个操作需要多个异步步骤（例如，创建临时表/视图、删除旧表，然后查询它们）时，标准 async/await 代码很容易出现竞态条件。如果输入在任务 A 执行到一半时更改，任务 B 可能会启动并删除或覆盖任务 A 仍在查询的临时表。

`AtomicTaskQueue` 一次运行一个任务直到完成，然后启动下一个任务。在多个 `AsyncMemo` 实例之间共享单个 `AtomicTaskQueue` 可确保它们的多步查询绝不会交错。

#### 链式 `AsyncMemo` 实例（多级缓存）

当某些状态不常更改（例如，创建临时 mipmap 表或准备视图），而其他派生状态频繁更改（例如，时间轴平移/缩放边界、分页或过滤器）时，将两个 `AsyncMemo` 实例链接在一起：

```typescript
import {AsyncMemo, AtomicTaskQueue} from '../base/async_memo';

class MyTrack {
  // 共享一个 AtomicTaskQueue，使表创建和表查询绝不会竞争
  private readonly queue = new AtomicTaskQueue();
  private readonly tableSlot = new AsyncMemo<MipmapTables>(this.queue);
  private readonly dataSlot = new AsyncMemo<Data>(this.queue);

  render(ctx: TrackRenderContext) {
    // 1. 慢速/不频繁步骤：创建临时表（仅在 track 配置更改时重新运行）
    const tableResult = this.tableSlot.use({
      key: {trackId: this.config.trackId},
      compute: () => this.createMipmapTables(),
    });

    // 如果依赖表尚未创建，返回加载指示器
    // （为简洁起见，这里我们只是提前返回 / 返回 undefined）。
    if (tableResult.data === undefined) return;

    // 2. 快速/频繁步骤：查询可见边界内的表
    const dataResult = this.dataSlot.use({
      key: {
        tableName: tableResult.data.tableName,
        start: ctx.bounds.start,
        end: ctx.bounds.end,
        resolution: ctx.bounds.resolution,
      },
      compute: async (signal) => {
        return this.fetchData(tableResult.data.tableName, ctx.bounds, signal);
      },
      retainOn: ['start', 'end', 'resolution'],
    });

    if (dataResult.data === undefined) return;
    this.renderData(ctx, dataResult.data);
  }

  private async fetchData(
    tableName: string,
    bounds: Bounds,
    signal: CancellationSignal,
  ): Promise<Data | typeof TASK_CANCELLED> {
    // 多步查询：先查询汇总统计信息，再查询详细 slice
    const summary = await this.engine.query(`SELECT ... FROM ${tableName} ...`);
    if (signal.isCancelled) return TASK_CANCELLED;

    const details = await this.engine.query(`SELECT ... FROM ${tableName} ...`);
    if (signal.isCancelled) return TASK_CANCELLED;

    return {summary, details};
  }

  dispose() {
    this.tableSlot.dispose();
    this.dataSlot.dispose();
  }
}
```

关键要点：
- **多级缓存**：当用户平移或缩放时，只有 `dataSlot` 重新运行；`tableSlot` 保持缓存，不会重新创建表。
- **保证不交错**：注意 `fetchData` 跨异步 `await` 点运行多个查询。由于 `tableSlot` 和 `dataSlot` 共享同一个 `AtomicTaskQueue`，**`createMipmapTables`（或此队列上的任何其他任务）绝不可能在 `fetchData` 中的两个查询之间运行**。队列确保所有任务以原子且串行的方式运行到完成。


### 小部件库

`ui/src/widgets/` 目录包含可重用组件。在创建新 UI 元素之前，始终先在此处检查：

- `Button`、`ButtonBar`、`ButtonGroup` - 各种按钮样式
- `PopupMenu`、`Menu`、`MenuItem`、`MenuDivider` - 下拉菜单
- `Popup` - 浮动弹出容器
- `Modal` - 模态对话框
- `TextInput`、`Select`、`Checkbox`、`Switch` - 表单控件
- `Tree` - 树视图组件
- `DataGrid` - 表格数据网格组件（位于 `ui/src/components/widgets/` 中）
- `Tabs` - 选项卡界面
- `Spinner` - 加载指示器
- `EmptyState` - 空状态占位符

**使用小部件：**

```typescript
import {Button, ButtonVariant} from '../widgets/button';
import {Popup} from '../widgets/popup';

m(Button, {
  label: 'Click me',
  icon: 'search',
  variant: ButtonVariant.Filled,
  onclick: () => { /* handle click */ },
});
```

## TypeScript 代码风格

遵循 TypeScript 代码的这些指南：

- **尽可能避免 `any`**：如果你真的需要它，请使用 `@typescript-eslint/no-explicit-any` 规则。在大多数情况下，使用 `unknown` 和类型保护就足够了。
- **未使用的变量**：使用下划线前缀（`_unused`）以满足 `@typescript-eslint/no-unused-vars`。
- **严格的布尔表达式**：不要在布尔上下文中隐式使用数字或字符串。
- **默认只读**：对接口属性和函数参数使用 `readonly`。
- **使用现有实用程序**：在编写自己的实用程序之前，请检查 `ui/src/base/`:
  - `time.ts` - 时间处理
  - `assert.ts` - `assertTrue()`、`assertExists()`、`assertFalse()`
  - `disposable_stack.ts` - 资源清理
  - `deferred.ts` - Promise 实用程序
  - `string_utils.ts` - 字符串操作
  - `array_utils.ts` - 数组助手

## 使用 TraceProcessor

插件通过 TraceProcessor 引擎使用 SQL 查询数据：

```typescript
async onTraceLoad(trace: Trace): Promise<void> {
  const result = await trace.engine.query(`
    SELECT ts, dur, name
    FROM slice
    WHERE name LIKE '%mySlice%'
    LIMIT 100
  `);

 // 使用类型化迭代
  const iter = result.iter({
    ts: LONG, // bigint
    dur: LONG, // bigint
    name: STR, // string
  });

  for (; iter.valid(); iter.next()) {
    console.log(iter.ts, iter.dur, iter.name);
  }
}
```

### 对 TraceProcessor ID 字段优先使用 `NUM`（number）而非 `LONG`（bigint）

提取 TraceProcessor 分配的 ID 列（例如 `track_id`、`upid`、`utid`、`slice.id`）时，请使用 `NUM`/`NUM_NULL` 和 `number`，而不是 `LONG`/`LONG_NULL` 和 `bigint`：

```typescript
const iter = result.iter({
  track_id: NUM,   // 好：number——ID 的首选
  // track_id: LONG, // 不好：bigint——ID 应避免使用
});
```

TraceProcessor ID 由引擎按顺序分配，因此它们是保证完全在 JS `number` 的 2^53 限制（最大安全整数）范围内的小整数。使用 `number` 可以避免 `bigint` 算术和比较的尴尬（`1n !== 1`）、在边界处（例如 track 标签、URL、JSON）进行 `Number()`/`BigInt()` 转换的需要，并避免 `bigint` 操作的性能损失——后者明显慢于 number 操作。

### 对时间戳和持续时间优先使用 `LONG`（bigint）而非 `NUM`（number）

纳秒形式的时间戳（`ts`）和持续时间（`dur`）应使用 `LONG`/`bigint`，因为它们确实可能超过 2^53——例如，一旦 trace 跨度达到约 104 天（2^53 纳秒），纳秒时间戳就会溢出，而纳秒值的算术运算（例如求和）可能在此之前就远超该限制。`bigint` 是这些值唯一安全的表示形式。

### 尽可能将时间和持续时间保持为 `Time`/`Duration`

UI 在 `ui/src/base/time.ts` 中为这些值提供了一等类型：branded 的 `time` 类型（通过 `Time` 类），以及 `duration`（`bigint` 的类型别名，通过 `Duration` 类）。从查询结果中提取 `ts`/`dur`（或任何纳秒时间戳/持续时间）时，请立即转换为这些类型，而不是到处传递原始 `bigint`：

```typescript
const iter = result.iter({
  ts: LONG,
  dur: LONG,
});

for (; iter.valid(); iter.next()) {
  const start = Time.fromRaw(iter.ts);      // time（branded bigint）
  const dur = Duration.fromRaw(iter.dur);   // duration
}
```

由于 `time` 是 branded 的，TypeScript 会拒绝在需要 `time` 的地方传递 `duration` 或普通 `bigint`（反之亦然），从而在编译时捕获时间/持续时间混淆。这两个类还提供算术和格式化助手（例如 `Time.add`/`Time.clamp`、`Duration.humanise`/`Duration.format`、`Timecode`）。仅在查询边界持有原始 `bigint`；一旦离开查询迭代，就立即转换为 `Time`/`Duration`。

## Track 创建

很少需要从头创建新 Track。
在大多数情况下，你可以使用 ui/src/components/tracks/ 中的更高级别组件，尤其是 SliceTrack(/docs/contributing/ui-plugins.md 中的示例)。
首先查看这些示例，并将通过 trace.tracks.registerTrack 创建 Track 作为最后手段。

## CSS/SCSS 约定

样式表位于 `ui/src/assets/` 中，以及组件旁边的组件特定 `.scss` 文件。

- 对所有 CSS 类使用 `pf-` 前缀(Perfetto 命名空间)
- 遵循 BEM 类似的命名：`.pf-component`、`.pf-component__element`、`.pf-component--modifier`
- 使用 `theme_provider.scss` 中定义的 CSS 自定义属性（变量）作为颜色
- 使用语义颜色变量同时支持浅色和深色主题

## 要避免的常见陷阱

1. **不检查现有小部件就创建新小部件** - 小部件库是全面的。
2. **尽可能使用 Trace 对象** - 在需要的地方通过层次结构传递 Trace 对象。
3. **不要在 `oninit`/`onupdate` 或 DOM 事件（`onclick`、`onkeydown`）中获取异步数据** - 加载应该是状态的声明式产物；更新状态并让 `view()` 中的 `AsyncMemo` 通过重新绘制机制处理获取。
4. **在 `onremove()` 中处置 `AsyncMemo` 实例是可选的** - 你可以调用 `.dispose()` 在组件卸载时取消待处理任务并及早清理缓存的可处置资源。
5. **绝不要在 `view()` 内部实例化 `AsyncMemo`** - 它必须在组件设置闭包或类构造函数/字段中创建，以便其缓存在渲染周期之间持久存在。

## 代码审查偏好和风格偏好

在代码审查期间一致地强制执行以下模式。遵循这些模式将显著加快审查过程。

> **参见：[UI 审查反模式](ui-review-antipatterns.md)** — 一份更深入、分类的反模式目录，来源于维护者对贡献者 PR 的真实审查反馈（Mithril/渲染、状态、分层、插件/API 设计、widget、CSS、类型、错误处理、性能、PR 范围）。在编写或审查 UI 更改时参考它，可预先避免常见错误。

### TypeScript/JavaScript 风格

**优先选择 `undefined` 而非 `null`:**

```typescript
// 不好
function getValue(): string | null { return null; }

// 好
function getValue(): string | undefined { return undefined; }
```

**对不应修改的数组使用 `readonly T[]`:**

```typescript
// 不好
function process(items: string[]): void { ... }

// 好
function process(items: readonly string[]): void { ... }
```

**使用 `classNames()` 实用程序构建 CSS 类字符串：**

```typescript
import {classNames} from '../base/classnames';

// 不好
const cls = 'pf-row' + (isSelected ? ' pf-row--selected' : '') + (isDisabled ? ' pf-row--disabled' : '');

// 好
const cls = classNames('pf-row', isSelected && 'pf-row--selected', isDisabled && 'pf-row--disabled');
```

**在 switch 默认情况下使用 `assertUnreachable()`:**

```typescript
import {assertUnreachable} from '../base/assert';

switch (value) {
  case 'a': return handleA();
  case 'b': return handleB();
  default:
    assertUnreachable(value); // 如果情况不详尽,TypeScript 将报错
}
```

**变量应为驼峰命名法：**

```typescript
// 不好
const trace_processor_id = 123;

// 好
const traceProcessorId = 123;
```

### CSS/SCSS 风格

**永远不要使用内联样式 - 使用样式表：**

```typescript
// 不好
m('div', {style: {color: 'red', padding: '10px'}}, 'content')

// 好
m('.pf-my-component', 'content') // 带有 .scss 文件中的样式
```

**所有 CSS 类必须具有 `pf-` 前缀：**

```scss
// 不好
.my-component { ... }
.row { ... }

// 好
.pf-my-component { ... }
.pf-my-component__row { ... }
```

**永远不要硬编码颜色 - 使用主题变量：**

```scss
// 不好
.pf-my-component {
  color: #333;
  background: white;
}

// 好
.pf-my-component {
  color: var(--pf-color-text);
  background: var(--pf-color-background);
}
```

### Mithril 特定规则

**不要为可以在 `view()` 中完成的事情使用 `oncreate`/生命周期钩子：**

```typescript
// 不好 - 在生命周期方法之间拆分代码会损害可读性。
oncreate() {
  this.computedValue = inexpensiveComputation();
}

// 好 - 在 view 中计算。如果昂贵，请在构造函数中初始化。
view() {
  const computedValue = inexpensiveComputation();
  return m('div', computedValue);
}
```

### 小部件使用

**对链接使用 `Anchor` 小部件：**

```typescript
import {Anchor} from '../widgets/anchor';
import {Icons} from '../base/semantic_icons';

// 不好
m('a', {href: 'https://example.com', target: '_blank'}, 'Link')

// 好
m(Anchor, {href: 'https://example.com', icon: Icons.ExternalLink}, 'Link')
```

### 命名约定

**设置/标志应使用反向 DNS 格式：**

```typescript
// 不好
const settingId = 'trackHeightMinPx';

// 好
const settingId = 'dev.perfetto.TrackHeightMinPx';
```

**命令 ID 应该是描述性的，但省略多余的插件名称：**

```typescript
// 不好(如果插件是 com.android.OrganizeNestedTracks)
const commandId = 'com.android.OrganizeNestedTracks#organizeNestedTracks';

// 好
const commandId = 'com.android.OrganizeNestedTracks';
```

**创建新文件时版权年份应该是当前的：**
但在编辑现有文件时不要触摸年份。

```typescript
// 不好(如果当前年份是 2025)
// Copyright (C) 2024 The Android Open Source Project

// 好
// Copyright (C) 2025 The Android Open Source Project
```

## 测试

**使用 Zod 解析未知类型的对象：**

```typescript
import {z} from 'zod';

// 不好 - 不安全的类型断言
const config = JSON.parse(data) as MyConfig;

// 好 - 验证解析
const ConfigSchema = z.object({
  name: z.string(),
  value: z.number(),
});
const config = ConfigSchema.parse(JSON.parse(data));
```

### UI 单元测试

单元测试运行使用：

```sh
ui/run-unittests
```

TypeScript 单元测试遵循 `*_unittest.ts` 模式并使用 Vitest。

### UI 集成测试

集成测试使用 Playwright:

```sh
ui/run-integrationtests
```
