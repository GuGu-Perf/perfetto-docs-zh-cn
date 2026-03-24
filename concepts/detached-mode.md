# 在分离模式下运行 perfetto

本文档描述了 `perfetto` 命令行客户端的 `--detach` 和 `--attach` 高级操作模式。

WARNING: 由于泄漏 trace 会话的风险，强烈不建议使用 `--detach` 和 `--attach`，并且可能会意外地将 trace 开启任意长的时间。

TIP: 如果你只是想在后台捕获 trace（例如，当 USB 电缆/adb 断开连接时），只需从 adb shell 使用 `--background`。

## 用例

默认情况下，trace 服务 `traced` 将 trace 会话的生命周期与启动它的 `perfetto` 命令行客户端的生命周期保持在一起。这意味着 `killall perfetto` 或 `kill $PID_OF_PERFETTO` 就足以保证 trace 会话停止。

在极少数情况下，这是不可取的；例如，这种操作模式是为 Traceur 应用程序设计的（Android 上的设备内 trace UI）。

当用户需要时，Traceur 需要在后台启用 trace，可能持续很长时间。因为 Traceur 不是持久服务（即使它是，它可能仍会被低内存终止），它不能只使用 `--background`；这是因为 Android 框架在拆除应用程序/服务时会杀死同一进程组中的任何其他进程，这包括杀死通过 `--background` 获得的 fork `perfetto` 客户端。

## 操作

`--detach=key` 将命令行客户端的生命周期与 trace 会话的生命周期解耦。

`key` 参数是客户端传递的任意字符串，用于稍后使用 `--attach=key` 重新标识会话。

一旦分离，命令行客户端将退出（不 fork 任何 bg 进程），并且 `traced` 服务将保持 trace 会话处于活动状态。由于退出，想要使用 `--detach` 的客户端需要在 trace 配置中设置 [`write_into_file`](config.md#long-traces) 选项，这将写入输出 trace 文件的责任转移给服务（参见 [示例](#examples) 部分）。

分离的会话将运行，直到：

- 会话稍后被重新附加并停止。
- 达到 trace 配置中的 `duration_ms` 参数指定的时间限制。

`--attach=key` 将新的命令行客户端调用的生命周期与由 `key` 标识的现有 trace 会话重新耦合。出于安全原因，服务仅当重新附加客户端的 Unix UID 与最初启动会话并分离的客户端的 UID 匹配时，才允许客户端重新附加到 trace 会话。

总体而言，`--attach=key` 使 `perfetto` 命令行客户端的行为就像它从未分离一样。这意味着：

- 向客户端发送 `SIGKILL`（或 Ctrl-C）将正常停止 trace 会话。
- 如果达到 `duration_ms` 时间限制，客户端将被服务通知并很快退出。

重新附加时，也可以指定进一步的 `--stop` 参数。`--stop` 将在重新附加后立即正常终止 trace 会话（这是为了避免在客户端有机会附加甚至注册信号处理程序之前过早发送 SIGKILL 的竞争条件）。

使用 `--attach` 时，除了 `--stop` 之外，不能传递任何其他命令行参数。

`--is_detached=key` 可用于检查分离的会话是否正在运行。命令行客户端将在调用后快速返回，并带有以下退出代码：

- 0 如果由 `key` 标识的会话存在并且可以重新附加。
- 1 如果出现一般错误（例如，错误的命令行，无法到达服务）。
- 2 如果未找到具有给定 `key` 的分离会话。

## 示例

### 在分离模式下捕获长 trace

```bash
echo '
write_into_file: true
# 长 trace 模式，定期将 trace 缓冲区刷新到 trace 文件中。
file_write_period_ms: 5000

buffers {
 # 此缓冲区需要足够大以仅容纳两个连续的
 # |file_write_period| 之间的数据（在此示例中为 5 秒）。
 size_kb: 16384
}

data_sources {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "sched_switch"
 }
 }
}
' | perfetto -c - --txt --detach=session1 -o /data/misc/perfetto-traces/trace

sleep 60

perfetto --attach=session1 --stop
# 此时 trace 文件已完全刷新到
# /data/misc/perfetto-traces/trace。
```

### 以分离的环形缓冲区模式启动。稍后停止并保存环形缓冲区

```bash
echo '
write_into_file: true

# 指定任意长的刷新周期。实际上这意味着：除非停止 trace，否则永远不刷新。
# TODO(primiano): 显式的 no_periodic_flushes 参数会更好。也许
# 我们可以重新利用 0 值?
file_write_period_ms: 1000000000

buffers {
 # 这将是最终 trace 的大小。
 size_kb: 16384
}

data_sources {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "sched_switch"
 }
 }
}
' | perfetto -c - --txt --detach=session2 -o /data/misc/perfetto-traces/trace

# 等待用户输入，或发生一些关键事件。

perfetto --attach=session2 --stop

# 此时 trace 文件已保存到
# /data/misc/perfetto-traces/trace。
```

### 启动具有时间限制的 trace。稍后重新附加并等待结束

```bash
echo '
duration_ms: 10000
write_into_file: true

buffers {
 size_kb: 16384
}

data_sources {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "sched_switch"
 }
 }
}
' | perfetto -c - --txt --detach=session3 -o /data/misc/perfetto-traces/trace

sleep 3
perfetto --attach=session3
# 命令行客户端将再保持 7 秒，然后终止。
```
