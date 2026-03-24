# 内存 Counter 和事件

Perfetto 允许在 Android 和 Linux 上收集许多内存事件和 Counters。这些事件来自内核接口，包括 ftrace 和 /proc 接口，有两种类型：内核在 ftrace 缓冲区中推送的轮询 Counters 和事件。

## 每个进程轮询 Counter {#per-process-polled-counters}

进程统计数据源允许以用户定义的间隔轮询 `/proc/<pid>/status` 和 `/proc/<pid>/oom_score_adj`。

请参见 [`man 5 proc`][man-proc] 了解其语义。

### UI {#per-process-ui}

![](/docs/images/proc_stat.png '显示进程统计轮询器收集的 trace 数据的 UI')

### SQL {#per-process-sql}

WARNING: 我们强烈建议使用标准库中的表而不是直接查询此数据。请参见 Android trace 分析指南中的[内存使用部分](/docs/getting-started/android-trace-analysis#memory-metrics)。

```sql
select c.ts, c.value, t.name as counter_name, p.name as proc_name, p.pid
from counter as c left join process_counter_track as t on c.track_id = t.id
left join process as p using (upid)
where t.name like 'mem.%'
```

| ts | counter_name | value_kb | proc_name | pid |
| --------------- | ----------------- | -------- | ------------------- | ----- |
| 261187015027350 | mem.virt | 1326464 | com.android.vending | 28815 |
| 261187015027350 | mem.rss | 85592 | com.android.vending | 28815 |
| 261187015027350 | mem.rss.anon | 36948 | com.android.vending | 28815 |
| 261187015027350 | mem.rss.file | 46560 | com.android.vending | 28815 |
| 261187015027350 | mem.swap | 6908 | com.android.vending | 28815 |
| 261187015027350 | mem.rss.watermark | 102856 | com.android.vending | 28815 |
| 261187090251420 | mem.virt | 1326464 | com.android.vending | 28815 |

### TraceConfig {#per-process-traceconfig}

要每 X ms 收集进程统计 Counters，请在进程统计配置中设置 `proc_stats_poll_ms = X`。 X 必须大于 100ms 以避免过度的 CPU 使用。有关收集的特定 Counters 的详细信息可以在 [ProcessStats 参考](/docs/reference/trace-packet-proto.autogen#ProcessStats) 中找到。

```protobuf
data_sources: {
 config {
 name: "linux.process_stats"
 process_stats_config {
 scan_all_processes_on_start: true
 proc_stats_poll_ms: 1000
 }
 }
}
```

## 每个进程内存事件（ftrace） {#per-process-memory-events-ftrace}

### rss_stat

最近版本的 Linux 内核允许在驻留集大小（RSS）mm Counters 更改时报告 ftrace 事件。这与 `/proc/pid/status` 中作为 `VmRSS` 可用的 Counter 相同。此事件的主要优点是，作为事件驱动的推送事件，它允许检测非常短的内存使用突发，否则使用 /proc Counters 将无法检测到。

即使持续几毫秒，数百 MB 的内存使用峰值也会对 Android 产生极其负面的影响，因为它们可能导致大规模低内存终止以回收内存。

有关分析内存使用的示例，请参见 Android trace 分析指南中的[内存使用部分](/docs/getting-started/android-trace-analysis#memory-metrics)。

支持此功能的内核功能已在 Linux 内核中引入 [b3d1411b6] 并由 [e4dcad20] 改进。它们从 Linux v5.5-rc1 起在上游可用。此补丁已在运行 Android 10 （Q） 的几个 Google Pixel 内核中向后移植。

[b3d1411b6]:
 https://github.com/torvalds/linux/commit/b3d1411b6726ea6930222f8f12587d89762477c6
[e4dcad20]:
 https://github.com/torvalds/linux/commit/e4dcad204d3a281be6f8573e0a82648a4ad84e69

### mm_event

`mm_event` 是一个捕获关键内存事件统计信息的 ftrace 事件（`/proc/vmstat` 公开的那些事件的子集）。与 RSS-stat Counter 更新不同，mm 事件的量极高，单独跟踪它们是不可行的。`mm_event` 仅在 trace 中报告定期直方图，合理地减少开销。

`mm_event` 仅在运行 Android 10 （Q） 及更高版本的某些 Google Pixel 内核上可用。

启用 `mm_event` 时，将记录以下 mm 事件类型：

- mem.mm.min_flt：次要页面错误
- mem.mm.maj_flt：主要页面错误
- mem.mm.swp_flt：由交换缓存服务的页面错误
- mem.mm.read_io：由 I/O 支持的读取页面错误
- mem.mm..compaction：内存压缩事件
- mem.mm.reclaim：内存回收事件

对于每个事件类型，事件记录：

- count：自上一次事件以来事件发生的次数。
- min_lat：自上一次事件以来记录的最小延迟（mm 事件的持续时间）。
- max_lat：自上一次事件以来记录的最高延迟。

### UI {#ftrace-ui}

![rss_stat 和 mm_event](/docs/images/rss_stat_and_mm_event.png)

### SQL {#ftrace-sql}

WARNING: 我们强烈建议使用标准库中的表而不是直接查询此数据。请参见 Android trace 分析指南中的[内存使用部分](/docs/getting-started/android-trace-analysis#memory-metrics)。

在 SQL 级别，这些事件以与相应的轮询事件相同的方式导入和公开。这允许收集两种类型的事件（推送和轮询）并在查询和脚本中统一处理它们。

```sql
select c.ts, c.value, t.name as counter_name, p.name as proc_name, p.pid
from counter as c left join process_counter_track as t on c.track_id = t.id
left join process as p using (upid)
where t.name like 'mem.%'
```

| ts | value | counter_name | proc_name | pid |
| --------------- | -------- | ---------------------- | --------------------------------- | ----- |
| 777227867975055 | 18358272 | mem.rss.anon | com.google.android.apps.safetyhub | 31386 |
| 777227865995315 | 5 | mem.mm.min_flt.count | com.google.android.apps.safetyhub | 31386 |
| 777227865995315 | 8 | mem.mm.min_flt.max_lat | com.google.android.apps.safetyhub | 31386 |
| 777227865995315 | 4 | mem.mm.min_flt.avg_lat | com.google.android.apps.safetyhub | 31386 |
| 777227865998023 | 3 | mem.mm.swp_flt.count | com.google.android.apps.safetyhub | 31386 |

### TraceConfig {#ftrace-traceconfig}

```protobuf
data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "kmem/rss_stat"
 ftrace_events: "mm_event/mm_event_record"
 }
 }
}

# 这是获取线程<>进程关联和完整进程名称。
data_sources: {
 config {
 name: "linux.process_stats"
 }
}
```

## 系统范围的轮询 Counter

此数据源允许定期从以下轮询系统数据：

- `/proc/stat`
- `/proc/vmstat`
- `/proc/meminfo`

请参见 [`man 5 proc`][man-proc] 了解其语义。

### UI {#system-wide-ui}

![系统内存 Counter](/docs/images/sys_stat_counters.png 'UI 中系统内存 Counter的示例')

轮询周期和要包含在 trace 中的特定 Counters 可以在 trace 配置中设置。

### SQL {#system-wide-sql}

```sql
select c.ts, t.name, c.value / 1024 as value_kb from counters as c left join counter_track as t on c.track_id = t.id
```

| ts | name | value_kb |
| --------------- | -------------- | -------- |
| 775177736769834 | MemAvailable | 1708956 |
| 775177736769834 | Buffers | 6208 |
| 775177736769834 | Cached | 1352960 |
| 775177736769834 | SwapCached | 8232 |
| 775177736769834 | Active | 1021108 |
| 775177736769834 | Inactive(file) | 351496 |

### TraceConfig {#system-wide-traceconfig}

支持的 Counters 集可在 [TraceConfig 参考](/docs/reference/trace-config-proto.autogen#SysStatsConfig) 中找到。

```protobuf
data_sources: {
 config {
 name: "linux.sys_stats"
 sys_stats_config {
 meminfo_period_ms: 1000
 meminfo_counters: MEMINFO_MEM_TOTAL
 meminfo_counters: MEMINFO_MEM_FREE
 meminfo_counters: MEMINFO_MEM_AVAILABLE

 vmstat_period_ms: 1000
 vmstat_counters: VMSTAT_NR_FREE_PAGES
 vmstat_counters: VMSTAT_NR_ALLOC_BATCH
 vmstat_counters: VMSTAT_NR_INACTIVE_ANON
 vmstat_counters: VMSTAT_NR_ACTIVE_ANON

 stat_period_ms: 1000
 stat_counters: STAT_CPU_TIMES
 stat_counters: STAT_FORK_COUNT
 }
 }
}
```

## 低内存终止（LMK）

#### 背景

Android 框架会终止应用程序和服务，尤其是后台应用程序，以便在需要内存时为新打开的应用程序腾出空间。这些被称为低内存终止（LMK）。

请注意，LMK 并不总是性能问题的症状。经验法则是严重性（即用户感知的影响）与被终止应用程序的状态成正比。应用程序状态可以从 trace 中的 OOM 调整分数推导出来。

前台应用程序或服务的 LMK 通常是一个大问题。当用户正在使用的应用程序在其手指下消失，或者他们最喜欢的音乐播放器服务突然停止播放音乐时，就会发生这种情况。

相反，缓存应用程序或服务的 LMK 通常是例行公事，在大多数情况下，直到用户尝试返回应用程序时才会被最终用户注意到，然后应用程序将冷启动。

这些极端之间的情况更为微妙。如果缓存应用程序/服务的 LMK 在风暴中发生（即观察到大多数进程在短时间内被 LMK），则可能仍然有问题，并且通常是系统某些组件导致内存峰值症状。

### lowmemorykiller vs lmkd

#### 内核 lowmemorykiller 驱动程序

在 Android 中，LMK 以前由临时内核驱动程序处理，即 Linux 的 [drivers/staging/android/lowmemorykiller.c](https://github.com/torvalds/linux/blob/v3.8/drivers/staging/android/lowmemorykiller.c)。此驱动程序在 trace 中发出 ftrace 事件 `lowmemorykiller/lowmemory_kill`。

#### 用户空间 lmkd

Android 9 引入了一个用户空间本机守护程序，接管了 LMK 责任：`lmkd`。并非所有运行 Android 9 的设备都必须使用 `lmkd`，因为内核与用户空间的最终选择取决于手机制造商、其内核版本和内核配置。

在 Google Pixel 手机上，从运行 Android 9 的 Pixel 2 开始使用 `lmkd` 端终止。

有关详细信息，请参见 https://source.android.com/devices/tech/perf/lmkd。

`lmkd` 发出一个名为 `kill_one_process` 的用户空间 atrace Counter 事件。

#### Android LMK vs Linux oomkiller

Android 上的 LMK，无论是旧内核 `lowmemkiller` 还是较新的 `lmkd`，都使用与标准 [Linux 内核的 OOM Killer](https://linux-mm.org/OOM_Killer) 完全不同的机制。Perfetto 目前仅支持 Android LMK 事件（内核和用户空间），不支持跟踪 Linux 内核 OOM Killer 事件。Linux OOMKiller 事件理论上在 Android 上仍然可能发生，但极不可能发生。如果发生，它们很可能是配置错误的 BSP 的症状。

### UI {#lmk-ui}

较新的用户空间 LMK 在 UI 中的 `lmkd` track 下以 Counter 的形式可用。Counter 值是被终止进程的 PID（在下面的示例中，PID=27985）。

![用户空间 lmkd](/docs/images/lmk_lmkd.png '由 lmkd 导致的 LMK 示例')

### SQL {#lmk-sql}

较新的 lmkd 和传统内核驱动的 lowmemorykiller 事件在导入时被规范化，并在 `instants` 表的 `mem.lmk` 键下可用。

```sql
SELECT ts, process.name, process.pid
FROM instant
JOIN process_track ON instant.track_id = process_track.id
JOIN process USING (upid)
WHERE instant.name = 'mem.lmk'
```

| ts | name | pid |
| --------------- | ------------------------ | ----- |
| 442206415875043 | roid.apps.turbo | 27324 |
| 442206446142234 | android.process.acore | 27683 |
| 442206462090204 | com.google.process.gapps | 28198 |

### TraceConfig {#lmk-traceconfig}

要启用低内存终止跟踪，请将以下选项添加到 trace 配置：

```protobuf
data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 # 对于旧内核事件。
 ftrace_events: "lowmemorykiller/lowmemory_kill"

 # 对于新的用户空间 lmkds。
 atrace_apps: "lmkd"

 # 这不是严格要求的,但很有用,可以知道进程
 # 的状态（FG、缓存...）在它被终止之前。
 ftrace_events: "oom/oom_score_adj_update"
 }
 }
}
```

## {#oom-adj} 应用程序状态和 OOM 调整分数

Android 应用程序状态可以从 trace 中的进程 `oom_score_adj` 推断出来。映射不是 1:1，状态比 oom_score_adj 值组多，缓存进程的 `oom_score_adj` 范围从 900 到 1000。

映射可以从 [ActivityManager 的 ProcessList 源](https://cs.android.com/android/platform/superproject/+/android10-release:frameworks/base/services/core/java/com/android/server/am/ProcessList.java;l=126) 推断出来

```java
// 这是一个仅托管不可见活动的进程,
// 因此可以在没有任何中断的情况下将其终止。
static final int CACHED_APP_MAX_ADJ = 999;
static final int CACHED_APP_MIN_ADJ = 900;

// 这是我们允许首先死亡的 oom_adj 级别。这不能等于
// CACHED_APP_MAX_ADJ,除非进程正在主动分配 CACHED_APP_MAX_ADJ 的 oom_score_adj。
static final int CACHED_APP_LMK_FIRST_ADJ = 950;

// SERVICE_ADJ 的 B 列表 -- 这些是旧的和陈旧的
// 服务,不如 A 列表中的那些闪亮和有趣。
static final int SERVICE_B_ADJ = 800;

// 这是用户之前所在的应用程序的进程。
// 这个进程保持在其他东西之上,因为非常常见
// 切换回上一个应用程序。这对于最近任务切换很重要
// （在两个顶级最近的应用程序之间切换）以及正常的
// UI 流程,例如,在电子邮件应用程序中单击 URI 以在浏览器中查看,
// 然后按返回键返回电子邮件。
static final int PREVIOUS_APP_ADJ = 700;

// 这是一个持有主应用程序的进程 -- 我们想尝试
// 避免杀死它,即使它通常在后台,
// 因为用户与之交互很多。
static final int HOME_APP_ADJ = 600;

// 这是一个持有应用程序服务的进程 -- 杀死它
// 对用户来说不会有太大影响。
static final int SERVICE_ADJ = 500;

// 这是一个具有重量级应用程序的进程。它在后台,
// 但我们想尝试避免杀死它。值在启动时
// 在 system/rootdir/init.rc 中设置。
static final int HEAVY_WEIGHT_APP_ADJ = 400;

// 这是一个当前托管备份操作的进程。杀死它
// 并不完全致命,但通常是一个坏主意。
static final int BACKUP_APP_ADJ = 300;

// 这是一个由系统（或其他应用程序）绑定的进程,比服务更重要,
// 但如果被杀死,不会立即影响用户。
static final int PERCEPTIBLE_LOW_APP_ADJ = 250;

// 这是一个仅托管用户可感知组件的进程,
// 我们真的想避免杀死它们,但它们不是
// 立即可见。一个例子是后台音乐播放。
static final int PERCEPTIBLE_APP_ADJ = 200;

// 这是一个仅托管用户可见活动的进程,
// 所以我们更希望它们不会消失。
static final int VISIBLE_APP_ADJ = 100;

// 这是一个最近处于 TOP 并已移动到 FGS 的进程。继续
// 像前台应用程序一样对待它一段时间。
// @see TOP_TO_FGS_GRACE_PERIOD
static final int PERCEPTIBLE_RECENT_FOREGROUND_APP_ADJ = 50;

// 这是运行当前前台应用程序的进程。我们真的
// 不想杀死它!
static final int FOREGROUND_APP_ADJ = 0;

// 这是系统或持久进程绑定到的进程,
// 并表示它很重要。
static final int PERSISTENT_SERVICE_ADJ = -700;

// 这是一个系统持久进程,例如电话。绝对
// 不想杀死它,但这样做并非完全致命。
static final int PERSISTENT_PROC_ADJ = -800;

// 系统进程以默认调整运行。
static final int SYSTEM_ADJ = -900;

// 用于未被系统管理的本机进程的特殊代码(因此
// 系统没有分配 oom adj)。
static final int NATIVE_ADJ = -1000;
```

[man-proc]: https://manpages.debian.org/stretch/manpages/proc.5.en.html
