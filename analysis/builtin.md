# PerfettoSQL 内置函数

这些是内置在 C++ 中的函数，可以减少在 SQL 中编写的样板代码量。

## Profile 函数

### STACK_FROM_STACK_PROFILE_FRAME

`STACK_FROM_STACK_PROFILE_FRAME(frame_id)`

#### 描述

创建一个仅包含 `frame_id` 引用的 frame 的 stack（对 [stack_profile_frame](sql-tables.autogen#stack_profile_frame) 表的引用）

#### 返回类型

`BYTES`

#### 参数

参数 | 类型 | 描述
-------- | ---- | -----------
frame_id | StackProfileFrameTable::Id | 对 [stack_profile_frame](sql-tables.autogen#stack_profile_frame) 表的引用

### STACK_FROM_STACK_PROFILE_CALLSITE

`STACK_FROM_STACK_PROFILE_CALLSITE(callsite_id)`

#### 描述

通过获取 `callsite_id`（对 [stack_profile_callsite]](sql-tables.autogen#stack_profile_callsite) 表的引用）并生成 frame 列表（通过遍历 [stack_profile_callsite]](sql-tables.autogen#stack_profile_callsite) 表）来创建 stack

#### 返回类型

`BYTES`

#### 参数

参数 | 类型 | 描述
-------- | ---- | -----------
callsite_id | StackProfileCallsiteTable::Id | 对 [stack_profile_callsite]](sql-tables.autogen#stack_profile_callsite) 表的引用

### CAT_STACKS

`CAT_STACKS(([root [[,level_1 [, ...]], leaf]])`

#### 描述

通过连接其他 Stack 来创建 Stack。还接受 STRING 值，为其生成伪 Frame。Null 值将被忽略。

#### 返回类型

`BYTES`

#### 参数

参数 | 类型 | 描述
-------- | ---- | -----------
root | BYTES 或 STRING | Stack 或 STRING，为其生成伪 Frame
... | BYTES 或 STRING | Stack 或 STRING，为其生成伪 Frame
leaf | BYTES 或 STRING | Stack 或 STRING，为其生成伪 Frame

### EXPERIMENTAL_PROFILE

`EXPERIMENTAL_PROFILE(stack [,sample_type, sample_units, sample_value]*)`

#### 描述

聚合函数，从给定的 samples 生成 [pprof](https://github.com/google/pprof) 格式的 profile。

#### 返回类型

`BYTES`（[pprof](https://github.com/google/pprof) 数据）

#### 参数

参数 | 类型 | 描述
-------- | ---- | -----------
stack | BYTES | Stack 或字符串，为其生成伪 Frame
sample_type | STRING | sample 值的类型（例如 size、time）
sample_units | STRING | sample 值的单位（例如 bytes、count）
sample_value | LONG | sample 的值

可以指定多个 sample。

如果仅存在 `stack` 参数，则使用 `"samples"`、`"count"` 和 `1` 分别作为 `sample_type`、`sample_units` 和 `sample_value` 的默认值。

#### 示例

CPU profile

```sql
SELECT
 perf_session_id,
 EXPERIMENTAL_PROFILE(
 STACK_FROM_STACK_PROFILE_CALLSITE(callsite_id),
 'samples',
 'count',
  1) AS profile
FROM perf_sample
GROUP BY perf_session_id
```

Heap profile

```sql
SELECT
 EXPERIMENTAL_PROFILE(
 CAT_STACKS(heap_name, STACK_FROM_STACK_PROFILE_CALLSITE(callsite_id)),
 'count',
 'count',
 count,
 'size',
 'bytes',
 size) AS profile
FROM heap_profile_allocation
WHERE size >= 0 AND count >= 0
```
