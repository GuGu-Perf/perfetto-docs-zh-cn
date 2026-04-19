# Android Aflags

_此数据源仅在 Android 上受支持。需要 `/system/bin/aflags` 工具，该工具在较新的 Android 版本中已预置。_

"android.aflags" 数据源采集 Android [aconfig flags](https://source.android.com/docs/setup/build/feature-flagging/declare-flag) 的快照，aconfig flags 是用于管理 Android 平台功能发布和行为的配置系统。

这使你能够记录任意一次 trace 中设备上激活了哪些 feature flag 及其值。当比较不同构建版本之间的 trace 时，或者行为变化只能通过正在进行的 flag 发布来解释时，这非常有用。

底层实现上，`traced_probes` 调用 `/system/bin/aflags list --format proto`，解码输出后每次轮询写入一个 `TracePacket`。周期性轮询可通过 `poll_ms` 启用（最小 1000ms）。

### UI

在 UI 层面，aflags 以 "Android Aflags" 表格形式展示在 trace 信息页面的 **Android** 标签下。如果 trace 包含多个快照（周期性轮询），表格上方有一个下拉框允许你在不同时间戳之间切换。

![](/docs/images/android_aflags.png "trace 信息页面 Android 标签下的 Android aflags")

### SQL

在 SQL 层面，aflags 数据通过 `android.aflags` 标准库模块暴露。`android_aflags` 视图中的每一行代表单个 flag 在特定时间戳下的状态（`ts` 列）。

以下是列出 flag 及其当前值的示例：

```sql
INCLUDE PERFETTO MODULE android.aflags;

select ts, package, name, value, permission
from android_aflags
order by package, name
```

ts | package | name | value | permission
---|---------|------|-------|-----------
12345 | perfetto.flags | buffer_clone_preserve_read_iter | enabled | read-only
12345 | perfetto.flags | save_all_traces_in_bugreport | enabled | read-write
12345 | perfetto.flags | track_event_incremental_state_clear_not_destroy | enabled | read-only
12345 | perfetto.flags | use_lockfree_taskrunner | enabled | read-write

以下是查找值被从默认值覆盖的 flag 的示例（有助于调试行为与干净构建不一致的原因）：

```sql
INCLUDE PERFETTO MODULE android.aflags;

select package, name, value, value_picked_from, storage_backend
from android_aflags
where value_picked_from != 'default'
```

package | name | value | value_picked_from | storage_backend
--------|------|-------|-------------------|----------------
perfetto.flags | save_all_traces_in_bugreport | enabled | server | device_config
perfetto.flags | use_lockfree_taskrunner | disabled | local | aconfigd

如果 `aflags` 工具在运行时失败，trace 级别的错误会记录在 `stats` 表中，名称为 `android_aflags_errors`：

```sql
select name, severity, source, value, description
from stats
where name = 'android_aflags_errors'
```

name | severity | source | value | description
-----|----------|--------|-------|------------
android_aflags_errors | error | trace | 1 | Errors occurred during the collection of Android aconfig flags by the android.aflags data source. This typically happens if the aflags tool fails or its output is malformed.

### TraceConfig

Android aflags 通过 trace config 的 [AndroidAflagsConfig](/docs/reference/trace-config-proto.autogen#AndroidAflagsConfig) 部分进行配置。

配置示例 — 在 trace 开始时采集单次快照：

```protobuf
data_sources: {
    config {
        name: "android.aflags"
    }
}
```

配置示例 — 周期性轮询（每次轮询约耗时 350ms；`poll_ms` 必须 >= 1000）：

```protobuf
data_sources: {
    config {
        name: "android.aflags"
        android_aflags_config {
            poll_ms: 5000
        }
    }
}
```
