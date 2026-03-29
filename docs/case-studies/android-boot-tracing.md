# 在 Android 启动时采集 trace

从 Android 13 (T) 开始，Perfetto 可以配置为在启动时自动开始采集 trace。这对于分析启动过程很有用。

## 步骤

- 创建一个包含所需 [trace 配置](/docs/concepts/config.md) 的文件，使用文本格式（而非二进制）。示例(更多示例参见 [/test/configs/](/test/configs/)):
 ```
 # 在中央 trace 二进制文件中分配一个缓冲区，供整个 trace 使用，
 # 由以下两个数据源共享。
 buffers {
 size_kb: 32768
 fill_policy: DISCARD
 }

 # 来自内核的 ftrace 数据,主要是进程调度事件。
 data_sources {
 config {
 name: "linux.ftrace"
 target_buffer: 0
 ftrace_config {
 ftrace_events: "sched_switch"
 ftrace_events: "sched_waking"
 ftrace_events: "sched_wakeup_new"

 ftrace_events: "task_newtask"
 ftrace_events: "task_rename"

 ftrace_events: "sched_process_exec"
 ftrace_events: "sched_process_exit"
 ftrace_events: "sched_process_fork"
 ftrace_events: "sched_process_free"
 ftrace_events: "sched_process_hang"
 ftrace_events: "sched_process_wait"
 }
 }
 }

# 解析进程命令行和父子关系，以更好地
  # 解释 ftrace 事件，这些事件基于 pid。
 data_sources {
 config {
 name: "linux.process_stats"
 target_buffer: 0
 }
 }

 # 10 秒 trace,但可以通过 `adb shell pkill -u perfetto` 提前停止。
 duration_ms: 10000
 ```
- 将文件放到设备上的 `/data/misc/perfetto-configs/boottrace.pbtxt`:
 ```
 adb push <yourfile> /data/misc/perfetto-configs/boottrace.pbtxt
 ```
- 启用 `perfetto_trace_on_boot` 服务：
 ```
 adb shell setprop persist.debug.perfetto.boottrace 1
 ```
 该属性在启动时重置。为了 trace 下一次启动，必须重新执行命令。
- 重启设备。
- 输出 trace 将写入到
 `/data/misc/perfetto-traces/boottrace.perfetto-trace`。该文件将在
 开始新 trace 之前被删除。
 ```
 adb pull /data/misc/perfetto-traces/boottrace.perfetto-trace
 ```
 **注意：**文件将在采集停止后出现（确保在配置中将
 `duration_ms` 设置为合理的值)或在第一个
 `flush_period_ms` 之后。
- 现在可以在 [ui.perfetto.dev](https://ui.perfetto.dev/) 中打开
 `boottrace.perfetto-trace`

## 实现细节
- trace 将仅在加载持久属性后开始，这发生在
 /data 挂载之后。
- 启动 trace 的命令实现为 oneshot init 服务。
