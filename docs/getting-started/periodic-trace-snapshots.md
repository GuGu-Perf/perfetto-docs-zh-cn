# 指南：周期性 Trace 快照

在本指南中，你将学习如何：

- 在 Android 设备或 Linux 机器上运行持续性的环形缓冲区 trace。
- 使用 `--clone-by-name` 获取 trace 的周期性快照。
- 使用 Trace Processor 分析每个快照，以监控设备指标随时间的变化。

当你需要在迭代设备或系统配置时反复观察系统指标（CPU 频率、电源轨、温度等），而不必每次重新启动 Tracing 时，这个工作流非常有用。

## 使用场景

假设你正在调优设备或系统参数（例如写入 `/proc` 或 `/sys` 节点），并希望在几秒钟内看到对功耗、温度和 CPU 行为的影响。传统的"启动 Tracing、停止 Tracing、拉取、分析"工作流会带来不必要的摩擦。

使用**周期性 Trace 快照**，你只需启动一次环形缓冲区 trace，然后可以按需克隆任意次数。每次克隆都是该时刻环形缓冲区的独立快照；原始 trace 保持不受干扰地持续运行。

## 前提条件

<?tabs>

TAB: Android

- 运行 Android 14 (U) 或更高版本的 Android 设备（`--clone-by-name` 标志需要 Perfetto v49+ 客户端和服务）。
- 主机上 `PATH` 中有 `adb`，且设备通过 USB 连接。
- 主机上有 `trace_processor_shell`（用于分析）。下载预构建版本：

```bash
curl -LO https://get.perfetto.dev/trace_processor
chmod +x ./trace_processor
```

TAB: Linux

- 安装了 Perfetto v49+ 的 Linux 机器，或已下载 `tracebox` 二进制文件。`tracebox` 将 `traced`、`traced_probes` 和 `perfetto` 客户端打包为一个单独的静态链接可执行文件：

```bash
curl -LO https://get.perfetto.dev/tracebox
chmod +x tracebox
```

- `trace_processor_shell`（用于分析）。下载预构建版本：

```bash
curl -LO https://get.perfetto.dev/trace_processor
chmod +x ./trace_processor
```
- 需要访问 `tracefs` 以使用基于 ftrace 的数据源。你**不需要**以 root 身份运行；相反，将 tracefs 目录的所有权更改为你的用户：

```bash
sudo chown -R $USER /sys/kernel/tracing
```

</tabs?>

## 步骤 1：启动环形缓冲区 trace

<?tabs>

TAB: Android

在主机上创建一个 trace 配置文件 `snapshot_config.pbtxt`：

```protobuf
# 为此会话命名，以便后续按名称克隆。
unique_session_name: "my_snapshot"

# 使用环形缓冲区，使 trace 永不停止。
buffers {
  size_kb: 65536
  fill_policy: RING_BUFFER
}

# CPU 频率（事件驱动 + 轮询回退）。
data_sources {
  config {
    name: "linux.ftrace"
    ftrace_config {
      ftrace_events: "power/cpu_frequency"
      ftrace_events: "power/cpu_idle"
      ftrace_events: "power/suspend_resume"
      ftrace_events: "thermal/thermal_temperature"
      ftrace_events: "thermal/cdev_update"
    }
  }
}

# 周期性 CPU 频率轮询（在 ftrace 事件未发出的平台上很有用）。
data_sources {
  config {
    name: "linux.sys_stats"
    sys_stats_config {
      cpufreq_period_ms: 500
    }
  }
}

# 电池计数器和电源轨（Pixel 设备）。
data_sources {
  config {
    name: "android.power"
    android_power_config {
      battery_poll_ms: 1000
      battery_counters: BATTERY_COUNTER_CAPACITY_PERCENT
      battery_counters: BATTERY_COUNTER_CHARGE
      battery_counters: BATTERY_COUNTER_CURRENT
      collect_power_rails: true
    }
  }
}
```

推送配置并启动 Tracing：

```bash
adb push snapshot_config.pbtxt /data/misc/perfetto-configs/
adb shell perfetto -c /data/misc/perfetto-configs/snapshot_config.pbtxt --txt \
  --background -o /data/misc/perfetto-traces/snapshot_bg
```

`--background` 标志会立即返回；trace 在设备的环形缓冲区中持续运行。

TAB: Linux

创建一个 trace 配置文件 `snapshot_config.pbtxt`：

```protobuf
# 为此会话命名，以便后续按名称克隆。
unique_session_name: "my_snapshot"

# 使用环形缓冲区，使 trace 永不停止。
buffers {
  size_kb: 65536
  fill_policy: RING_BUFFER
}

# CPU 频率（事件驱动 + 轮询回退）。
data_sources {
  config {
    name: "linux.ftrace"
    ftrace_config {
      ftrace_events: "power/cpu_frequency"
      ftrace_events: "power/cpu_idle"
      ftrace_events: "power/suspend_resume"
      ftrace_events: "thermal/thermal_temperature"
      ftrace_events: "thermal/cdev_update"
    }
  }
}

# 周期性 CPU 频率轮询（在 ftrace 事件未发出的平台上很有用，例如 Intel CPU）。
data_sources {
  config {
    name: "linux.sys_stats"
    sys_stats_config {
      cpufreq_period_ms: 500
    }
  }
}

# 功耗监控（Chrome OS / Linux）。
data_sources {
  config {
    name: "linux.sysfs_power"
  }
}
```

启动 Tracing 服务并开始 Tracing。如果你使用的是 `tracebox`：

```bash
# tracebox 会自动启动 traced 和 traced_probes。
./tracebox -c snapshot_config.pbtxt --txt \
  --background -o /tmp/snapshot_bg
```

如果你分别安装了 `traced`、`traced_probes` 和 `perfetto`：

```bash
# 确保 traced 和 traced_probes 正在运行，然后：
perfetto -c snapshot_config.pbtxt --txt \
  --background -o /tmp/snapshot_bg
```

`--background` 标志会立即返回；trace 在环形缓冲区中持续运行。

</tabs?>

## 步骤 2：获取快照

每当你想捕获环形缓冲区的当前状态时，按名称克隆会话：

<?tabs>

TAB: Android

```bash
adb shell perfetto --clone-by-name my_snapshot \
  -o /data/misc/perfetto-traces/snapshot_1.pftrace
```

这会创建该时刻环形缓冲区内容的只读副本。原始 Tracing Session 继续运行。你可以根据需要重复此操作，每次为快照指定不同的输出文件名：

```bash
# 在修改了系统/设备参数之后...
adb shell perfetto --clone-by-name my_snapshot \
  -o /data/misc/perfetto-traces/snapshot_2.pftrace
```

TAB: Linux

```bash
perfetto --clone-by-name my_snapshot \
  -o /tmp/snapshot_1.pftrace
# 或使用 tracebox：
./tracebox --clone-by-name my_snapshot \
  -o /tmp/snapshot_1.pftrace
```

这会创建该时刻环形缓冲区内容的只读副本。原始 Tracing Session 继续运行。你可以根据需要重复此操作，每次为快照指定不同的输出文件名：

```bash
# 在修改了系统参数之后...
perfetto --clone-by-name my_snapshot \
  -o /tmp/snapshot_2.pftrace
```

</tabs?>

## 步骤 3：拉取并分析快照

<?tabs>

TAB: Android

将快照拉取到主机：

```bash
adb pull /data/misc/perfetto-traces/snapshot_1.pftrace /tmp/
```

TAB: Linux

快照已经在本地的 `/tmp/snapshot_1.pftrace`。

</tabs?>

你可以使用 `trace_processor_shell` 命令行、Python API，或在 [Perfetto UI](https://ui.perfetto.dev) 中打开快照进行分析。

### 使用 trace_processor_shell 查询

使用 `query` 子命令直接从命令行运行一次性查询：

```bash
trace_processor_shell query /tmp/snapshot_1.pftrace "
  INCLUDE PERFETTO MODULE linux.cpu.frequency;
  SELECT * FROM cpu_frequency_counters LIMIT 100;
"
```

或打开交互式 SQL shell 探索数据：

```bash
trace_processor_shell /tmp/snapshot_1.pftrace
```

以下是一些有用的查询：

#### CPU 频率

```sql
INCLUDE PERFETTO MODULE linux.cpu.frequency;

SELECT *
FROM cpu_frequency_counters
LIMIT 100;
```

#### 电源轨（Android，Pixel 设备）

```sql
INCLUDE PERFETTO MODULE android.power_rails;

SELECT *
FROM android_power_rails_counters
LIMIT 100;
```

#### 电池计数器（Android）

```sql
SELECT ts, t.name, value
FROM counter AS c
LEFT JOIN counter_track AS t ON c.track_id = t.id
WHERE t.name GLOB 'batt.*';
```

#### 热区温度

```sql
SELECT ts, t.name, value
FROM counter AS c
LEFT JOIN counter_track AS t ON c.track_id = t.id
WHERE t.name GLOB '*thermal*';
```

### 使用 Python API 查询

`perfetto` Python 包允许你以编程方式加载和查询 trace，这很方便用于构建自定义仪表板或使用 Pandas / Polars 进行数据后处理。安装方式：

```bash
pip install perfetto
```

示例：

```python
from perfetto.trace_processor import TraceProcessor

tp = TraceProcessor(trace='/tmp/snapshot_1.pftrace')

# 将 CPU 频率查询为 Pandas DataFrame。
qr = tp.query("""
  INCLUDE PERFETTO MODULE linux.cpu.frequency;
  SELECT cpu, ts, freq
  FROM cpu_frequency_counters
""")
df = qr.as_pandas_dataframe()
print(df.to_string())

# 绘制每个 CPU 的频率随时间变化图。
import matplotlib.pyplot as plt
for cpu, group in df.groupby('cpu'):
  plt.plot(group['ts'], group['freq'], label=f'cpu {cpu}')
plt.legend()
plt.xlabel('Timestamp (ns)')
plt.ylabel('Frequency (kHz)')
plt.show()
```

更多详细信息请参阅 [Trace Processor Python 文档](/docs/analysis/trace-processor-python.md)。

如果你想一起分析多个快照，[Batch Trace Processor](/docs/analysis/batch-trace-processor.md) 可以让你一次对一组 trace 运行单个查询。

## 自动化快照

一个简单的 shell 循环可以每隔 N 秒获取一次快照并对其运行查询：

<?tabs>

TAB: Android

```bash
for i in $(seq 1 10); do
  SNAP="/data/misc/perfetto-traces/snap_${i}.pftrace"
  adb shell perfetto --clone-by-name my_snapshot -o "$SNAP"
  adb pull "$SNAP" /tmp/
  echo "=== Snapshot $i ==="
  trace_processor_shell query /tmp/"snap_${i}.pftrace" "
    INCLUDE PERFETTO MODULE linux.cpu.frequency;
    SELECT cpu, avg(freq) AS avg_freq_khz
    FROM cpu_frequency_counters
    GROUP BY cpu;
  "
  sleep 5
done
```

TAB: Linux

```bash
for i in $(seq 1 10); do
  SNAP="/tmp/snap_${i}.pftrace"
  perfetto --clone-by-name my_snapshot -o "$SNAP"
  echo "=== Snapshot $i ==="
  trace_processor_shell query "$SNAP" "
    INCLUDE PERFETTO MODULE linux.cpu.frequency;
    SELECT cpu, avg(freq) AS avg_freq_khz
    FROM cpu_frequency_counters
    GROUP BY cpu;
  "
  sleep 5
done
```

</tabs?>

## 停止 trace

<?tabs>

TAB: Android

```bash
adb shell killall perfetto
```

TAB: Linux

```bash
killall perfetto
# 如果使用 tracebox：
killall tracebox
```

</tabs?>

## 限制和注意事项

- **数据源刷新间隔**：并非所有数据源都持续发送数据。例如，`android.power` 按配置的 `battery_poll_ms` 间隔进行轮询，某些数据源仅在 trace 启动或停止时写入数据。快照将包含截至该时刻已写入环形缓冲区的所有数据。
- **环形缓冲区覆盖**：如果缓冲区相对于数据速率太小，较旧的数据会在你获取快照之前被覆盖。如果发现数据间隙，请增大 `size_kb`。
- **Clone 可用性**：`--clone-by-name` 标志需要 Perfetto v49+。在 Android 上，这意味着 Android 14 (U) 或更高版本。在 Linux 上，请确保你使用的是较新的 `tracebox` 或 Perfetto 构建。
- **非实时流式传输**：每个快照都是缓冲区在某个时间点的副本，而非实时流。在最后写入的事件和你运行 clone 命令之间总会有一些延迟。
- **Linux ftrace 权限**：在 Linux 上，基于 ftrace 的数据源需要访问 `tracefs`。无需以 root 身份运行，将目录所有权更改为你的用户即可：`sudo chown -R $USER /sys/kernel/tracing`。
- **Intel CPU 频率**：在大多数现代 Intel CPU 上，`power/cpu_frequency` ftrace 事件不会发出，因为频率调节由 CPU 内部管理。请使用 `linux.sys_stats` 轮询数据源并设置 `cpufreq_period_ms` 作为回退方案。
