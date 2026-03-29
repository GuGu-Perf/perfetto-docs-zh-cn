# TRACED_PROBES(8)

## 名称

traced_probes - 系统和操作系统探针

## 描述

`traced_probes` 是一个专门的守护程序，充当 Perfetto
架构中特权化的 [Producer](/docs/concepts/service-model.md#producer)。虽然任何应用程序都可以作为生产者来贡献自己的 trace 数据，但 `traced_probes` 专门负责收集通常需要提升权限的系统和内核级别的数据。

## 与 `traced` 的关系

`traced_probes` 是 [`traced`](/docs/reference/traced.md)
服务的客户端。它连接到 `traced` 的生产者套接字并注册一组数据源。然后，`traced` 向 `traced_probes` 发送请求以启动或停止这些数据源，作为 Tracing Session 的一部分。

这种关注点分离是 Perfetto 设计的关键部分。`traced` 是中央管理器，而 `traced_probes` 是专门的数据提供者。这种解耦架构允许多个独立的生产者和消费者同时与 tracing 系统交互而不会相互干扰。

![traced_probes and traced](/docs/images/platform-tracing.png)

## 安全和权限

`traced_probes` 通常需要以提升的权限（例如，Android 上的 `root` 或 `system` 用户）运行以访问内核接口，如 `debugfs` 或 `/proc`。将这些高权限探针分离到自己的守护程序中是 Perfetto 安全模型的关键部分。它确保只有最少的代码以高权限运行，遵循最小权限原则。

## 配置

`traced_probes` 提供的数据源在发送到 `traced` 的主 trace 配置 protobuf 中配置。例如，要启用 ftrace，你将在 `linux.ftrace` 数据源的 `DataSourceConfig` 中包含一个 `FtraceConfig`。

## 数据源

`traced_probes` 提供广泛的数据源，收集系统和内核级别的数据。这些数据源的配置在整体 trace 配置的 `data_sources` 部分中指定。每个数据源在 `data_source_config` 块中都有自己的配置消息。

以下是总体结构的示例：

```protobuf
data_sources: {
    config {
        name: "linux.ftrace"
        ftrace_config {
            # ... ftrace 特定设置
        }
    }
}
data_sources: {
    config {
        name: "linux.process_stats"
        process_stats_config {
            # ... process_stats 特定设置
        }
    }
}
```

以下是 `traced_probes` 提供的主要数据源的详细列表，按平台分隔。

## Linux 数据源

这些数据源在基于 Linux 的系统上可用，包括 Android。

以下是启用几个 Linux 数据源的 trace 配置示例：
```protobuf
# 启用几个 Linux 数据源的 trace 配置示例。
data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "sched/sched_switch"
 ftrace_events: "power/cpu_idle"
 }
 }
}
data_sources: {
 config {
 name: "linux.process_stats"
 process_stats_config {
 scan_all_processes_on_start: true
 proc_stats_poll_ms: 1000
 }
 }
}
data_sources: {
 config {
 name: "linux.sys_stats"
 sys_stats_config {
 meminfo_period_ms: 1000
 vmstat_period_ms: 1000
 }
 }
}
```

### `linux.ftrace`(内核 tracing)

- **描述**：这是高频内核事件的主要数据源。它从 Linux 内核的 ftrace 接口启用和读取原始 ftrace 数据，提供对进程调度、系统调用、中断和其他内核活动的洞察。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "sched/sched_switch"
 ftrace_events: "power/cpu_idle"
 ftrace_events: "sched/sched_waking"
 }
 }
 }
 ```
- **配置**：通过 `DataSourceConfig` 中的 `FtraceConfig` 配置。主要选项包括：
  - `ftrace_events`：要启用的 ftrace 事件列表(例如，
 `sched/sched_switch`)。
  - `atrace_categories`, `atrace_apps`：对于 Android，启用用户空间
 Atrace 类别和应用程序。
  - `syscall_events`：要追踪的特定系统调用。
  - `enable_function_graph`：启用内核函数图 tracing。
  - `compact_sched`：启用调度器事件的紧凑编码。
  - `symbolize_ksyms`：启用内核符号化。
  - `print_filter`：根据内容过滤 `ftrace/print` 事件。

### `linux.process_stats`(进程和线程统计)

- **描述**：从 `/proc` 文件系统收集详细的进程和线程级别的统计信息。它提供进程树的快照和周期性内存/CPU Counters。
- **配置示例**：
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
- **配置**：通过 `ProcessStatsConfig` 配置。主要选项包括：
  - `record_thread_names`：记录线程名称。
  - `scan_all_processes_on_start`：在开始时转储整个进程树。
  - `resolve_process_fds`：解析文件描述符路径。
  - `scan_smaps_rollup`：读取 `/proc/[pid]/smaps_rollup`。
  - `record_process_age`：记录进程开始时间。
  - `record_process_runtime`：记录用户和内核模式 CPU 时间。
  - `record_process_dmabuf_rss`：记录 DMA 缓冲区 RSS。
  - `proc_stats_poll_ms`：周期性统计的轮询间隔。
  - `proc_stats_cache_ttl_ms`：缓存统计的生存时间。
  - `quirks`：特殊行为（例如，`DISABLE_ON_DEMAND`）。

### `linux.sys_stats`(系统范围统计)

- **描述**：通过定期轮询 `/proc` 和 `/sys` 中的各种文件来收集系统范围的统计信息。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "linux.sys_stats"
 sys_stats_config {
 meminfo_period_ms: 1000
 vmstat_period_ms: 1000
 stat_period_ms: 1000
 }
 }
 }
 ```
- **配置**：通过 `SysStatsConfig` 配置。允许对要收集的 Counters 及其轮询频率进行精细控制（例如，
 `meminfo_period_ms`、`vmstat_period_ms`、`stat_counters`)。

### `linux.sysfs_power`(电源和电池信息)

- **描述**：使用 Linux sysfs 接口收集电源和电池统计信息。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "linux.sysfs_power"
 }
 }
 ```
- **配置**：此数据源没有特定的配置 proto。

### `linux.inode_file_map`(Inode 到文件路径映射)

- **描述**：将 inode 编号映射到文件路径，这对于将 I/O 事件与正在访问的文件相关联很有用。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "linux.inode_file_map"
 inode_file_config {
 scan_interval_ms: 10000
 scan_delay_ms: 5000
 scan_batch_size: 1000
 }
 }
 }
 ```
- **配置**：`InodeFileConfig` 允许指定 `scan_mount_points`、`mount_point_mapping`（以重新映射扫描根）、`scan_interval_ms`、`scan_delay_ms`、`scan_batch_size` 和 `do_not_scan`。

### `metatrace`(Perfetto 自 tracing)

- **描述**： 自trace data源，记录 Perfetto 本身内的事件，用于调试和分析tracing system的性能。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "metatrace"
 }
 }
 ```
- **配置**： `DataSourceConfig` 中没有特定配置。

### `linux.system_info`(系统信息)

- **描述**：记录有关系统的一般信息，例如 CPU 详细信息和内核版本。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "linux.system_info"
 }
 }
 ```
- **配置**： `DataSourceConfig` 中没有特定配置。

## Android 数据源

这些数据源仅在 Android 上可用。

以下是启用几个 Android 数据源的 trace 配置示例：
```protobuf
# 启用几个 Android 数据源的 trace 配置示例。
data_sources: {
 config {
 name: "android.power"
 android_power_config {
 battery_poll_ms: 1000
 battery_counters: BATTERY_COUNTER_CHARGE
 collect_power_rails: true
 }
 }
}
data_sources: {
 config {
 name: "android.log"
 android_log_config {
 log_ids: LID_DEFAULT
 log_ids: LID_SYSTEM
 }
 }
}
data_sources: {
 config {
 name: "android.packages_list"
 }
}
```

### `android.power`(电源和电池信息)

- **描述**： 使用 Android 特定的 HAL 收集电源和电池统计信息。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.power"
 android_power_config {
 battery_poll_ms: 1000
 battery_counters: BATTERY_COUNTER_CHARGE
 battery_counters: BATTERY_COUNTER_CAPACITY_PERCENT
 collect_power_rails: true
 }
 }
 }
 ```
- **配置**：`AndroidPowerConfig` 允许启用特定的电池 Counters（`battery_counters`）、电源轨（`collect_power_rails`）、能量估算细分（`collect_energy_estimation_breakdown`）和实体状态驻留（`collect_entity_state_residency`）。

### `android.log`(Android Logcat)

- **描述**：将来自 Android 的 logcat 缓冲区的 Log message 流式传输到 trace 中。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.log"
 android_log_config {
 log_ids: LID_DEFAULT
 log_ids: LID_SYSTEM
 min_prio: PRIO_INFO
 filter_tags: "ActivityManager"
 }
 }
 }
 ```
- **配置**： `AndroidLogConfig` 允许按 Log ID
 (`log_ids`) 和标签（`filter_tags`）进行过滤，并设置最小优先级
 (`min_prio`)。

### `android.system_property`(Android 系统属性)

- **描述**：收集 Android 系统属性的状态。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.system_property"
 android_system_property_config {
 poll_ms: 1000
 property_name: "debug.tracing.screen_state"
 }
 }
 }
 ```
- **配置**： `AndroidSystemPropertyConfig` 允许指定
 要监视的 `property_name`s 和 `poll_ms` 间隔。

### `android.packages_list`(Android 包信息)

- **描述**： 转储有关 Android 上已安装包的信息。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.packages_list"
 packages_list_config {
 package_name_filter: "com.android.systemui"
 package_name_filter: "com.google.android.apps.nexuslauncher"
 }
 }
 }
 ```
- **配置**：`PackagesListConfig` 允许按 `package_name_filter` 进行过滤，并可以配置为 `only_write_on_cpu_use_every_ms`（轮询模式）或在开始时全部转储。

### `android.game_interventions`(Android 游戏干预列表)

- **描述**：从 Android 上的包管理器转储游戏干预列表。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.game_interventions"
 android_game_intervention_list_config {
 package_name_filter: "com.example.mygame"
 }
 }
 }
 ```
- **配置**： `AndroidGameInterventionListConfig` 允许按
 `package_name_filter` 进行过滤。

### `android.cpu.uid`(每 UID CPU 时间)

- **描述**： 从内核收集每 UID CPU 时间。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.cpu.uid"
 cpu_per_uid_config {
 poll_ms: 1000
 }
 }
 }
 ```
- **配置**： `CpuPerUidConfig` 允许设置 `poll_ms` 间隔。

### `android.kernel_wakelocks`(内核唤醒锁)

- **描述**：收集内核唤醒锁信息。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.kernel_wakelocks"
 kernel_wakelocks_config {
 poll_ms: 1000
 }
 }
 }
 ```
- **配置**：`KernelWakelocksConfig` 允许设置 `poll_ms` 间隔。

### `android.polled_state`(Android 初始显示状态)

- **描述**： 在 Android 上记录初始显示状态(例如，屏幕开/关，
 亮度)。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.polled_state"
 android_polled_state_config {
 poll_ms: 500
 }
 }
 }
 ```
- **配置**： `AndroidPolledStateConfig` 允许设置 `poll_ms`
 间隔。

### `android.statsd`(Android StatsD 原子)

- **描述**：从 Android 上的 binder 接口收集 StatsD 原子。
- **配置示例**：
 ```protobuf
 data_sources: {
 config {
 name: "android.statsd"
 statsd_tracing_config {
 pull_config {
 pull_atom_id: 10000 # 示例拉取原子
 pull_frequency_ms: 1000
 }
 push_atom_id: 10037 # 示例推送原子
 }
 }
 }
 ```
- **配置**：`StatsdTracingConfig` 允许指定 `pull_config`（对于具有频率和包的拉取原子）和 `push_atom_id`（对于推送原子）。