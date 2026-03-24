# PerfettoSQL：向后兼容性

PerfettoSQL 尽最大努力减少向后不兼容的更改，但有时这些更改是不可避免的。在我们需要做出此类预期会产生重大影响的更改时，本文档记录了：
- **日期/版本**： 此更改的日期以及包含此更改的 Perfetto 首个发布版本
- **表现**： 如果你受此更改影响，你会看到意外行为或错误消息
- **背景**： 我们为什么要进行此更改，即为什么它必须向后不兼容
- **迁移**： 建议你对 PerfettoSQL 进行以下更改，以避免受此更改影响

## 从 slice 表中删除 `stack_id` 和 `parent_stack_id` 列

**日期/版本**

2025-11-21/v54.0

**表现**

- 类似于 `no such column: stack_id` 或 `no such column: parent_stack_id` 的错误消息
- 在对 slice 表执行 `SELECT *` 的查询输出中，`stack_id` 和 `parent_stack_id` 列消失
- 错误 `no such function: ancestor_slice_by_stack` 或 `no such function: descendant_slice_by_stack`(这些现在需要 `INCLUDE PERFETTO MODULE slices.stack`)
- 使用硬编码 stack_id 值的查询（例如 `WHERE stack_id = 123456`）不返回结果或返回错误结果

**背景**

`stack_id` 和 `parent_stack_id` 列基于 slice 名称计算哈希值。删除它们的原因如下：

1. 它们消耗大量内存，但功能实用性有限
2. 即使被使用，`parent_id` 通常是更好的选择

这些列已从 slice 表中删除，基于 stack 的表函数已移至 `slices.stack` stdlib 模块，该模块按需计算 stack 哈希值而不是存储它们。

**迁移**

**⚠️ 重要**： 迁移辅助工具使用不同的哈希算法（SQLite `hash()` 与 `MurmurHash`），并将产生与先前实现**不同的 stack_id 值**。这意味着：
- 查询或仪表板中的硬编码 stack_id 值将**无法工作**

**迁移辅助工具**： 为了与现有查询的 API 兼容，你可以使用 `slices.stack` 模块中的迁移辅助工具：

```sql
INCLUDE PERFETTO MODULE slices.stack;

-- 访问 stack_id 和 parent_stack_id 列 (使用新哈希算法按需计算)
SELECT * FROM slice_with_stack_id WHERE id = 123;

-- 使用基于 stack 的祖先/后代函数
SELECT * FROM ancestor_slice_by_stack((SELECT stack_id FROM slice_with_stack_id WHERE id = 123));
SELECT * FROM descendant_slice_by_stack((SELECT stack_id FROM slice_with_stack_id WHERE id = 123));
```

**注意**： 这些辅助工具按需计算 stack 哈希值，并且可能比先前的 C++ 实现慢。

**是否真的需要此功能？**

请考虑你是否真的需要基于 stack 的功能，还是打算使用父子关系：

- 使用 `parent_id` 遍历 slice 层次结构
- 使用 `ancestor_slice(id)` 表函数查找所有祖先
- 使用 `descendant_slice(id)` 表函数查找所有后代

例如，替换以下查询：

```sql
select * from ancestor_slice_by_stack((select stack_id from slice where id = 123))
```

你可以执行：

```sql
select * from ancestor_slice(123)
```

如果你需要查找具有相同命名模式的 slice，请使用显式名称匹配：

```sql
-- 查找具有相同类别和名称的 slice
select s2.* from slice s1
join slice s2 on s1.category = s2.category and s1.name = s2.name
where s1.id = 123
```

## track 表 `type` 列的语义更改

**日期/版本**

2024-12-18/v49.0

**表现**

- 查询 `*track` 表的查询输出中 `type` 列的值更改
- 如果你对 `type` 列有约束，则会缺少行。例如 `SELECT type from track where type = 'process_slice'` 现在将返回零行

**背景**

NOTE: 此更改与*从非 track 表中删除 `type` 列*更改密切相关，请参见下文。

`type` 列在 track 表中已存在很长时间，用于指示包含 track 的"最具体表"。随着时间的推移，随着 trace processor 表中表结构的变化（即更多地使用标准库，具有多个维度的 track），我们已经超越了使 `type` 列有意义的"面向对象表"概念。

不再只有少数可能的 `type` 值（例如 `process_track`、`thread_track`、`counter_track`），我们已将 `type` 列的语义切换为指示"track 中的数据类型"。例如，对于来自 `track_event` API 的全局作用域 slice track，`type` 列现在将是 `global_track_event`。对于进程作用域 track，它将是 `process_track_event` 等。

此更改与新列 `dimension_arg_set_id` 密切相关，后者还包含 `type` 特定上下文，用于区分相同 `type` 下的不同 track。

**迁移**

如果你正在执行形式如 `select * from track where type = 'process_track'` 的查询，这可以轻松替换为 `select * from process_track`。

相反，如果你尝试从 trace_processor 导出 `type` 的值，你可以通过对 track 进行多个 UNION 操作来恢复旧的 type 列。

例如，替换以下查询：

```sql
select name, type from track where name in ('process_track', 'thread_track')
```

你可以执行：

```sql
select name, 'process_track' as type from process_track
union all
select name, 'thread_track' as type from thread_track
```

最后，在此更改之前查找所有"全局作用域 track"的建议方法是：

```sql
select * from track where type = 'track'
```

这可以替换为：

```sql
select * from track where dimension_arg_set_id is null
```

## 从所有非 track 表中删除 `type` 列

**日期/版本**

2024-12-18/v49.0

**表现**

- 类似于 `no such column: type` 的错误消息
- 在执行 `SELECT *` 的查询输出中，`type` 列消失

**背景**

NOTE: 此更改与*`type` 列的语义更改*更改密切相关，请参见上文。

`type` 列在表中已存在很长时间，用于指示包含 track 的"最具体表"。随着时间的推移，随着 trace processor 表中表结构的变化（即更多地使用标准库，具有多个维度的 track），我们已经超越了使 `type` 列有意义的"面向对象表"概念。

实际上，对于任何非 track 表，type 列几乎总是等于表本身的名称，例如，如果你执行 `select type from slice`，type 列将是 `slice`。

鉴于此列的实用性非常有限，在大型 trace 上存储此信息会消耗相当数量的内存，并且它会污染列列表，我们已决定从所有非 track 表中删除此列。对于 track 表，此列的目的已更改，如上所述。

**迁移**

你对 `type` 列的依赖很可能是因为使用了 `select *` 而非主动选择列。在这种情况下，迁移应该很简单，只需删除对 `type` 列的引用（例如在对执行 `select *` 的查询输出的断言中）。

如果你的工作流程因这次更改而中断，我们很乐意帮助你解决此问题。请向 http://go/perfetto-bug（如果你是 Google 员工）或 https://github.com/google/perfetto/issues/new（否则）提交错误报告。
