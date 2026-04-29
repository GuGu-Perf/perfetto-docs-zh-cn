# HEAP_PROFILE(1)

## 名称

heap_profile - 在 Android 或本地 Linux 上记录 heap profile

## 描述

`tools/heap_profile` 收集原生内存 profile。它提供两个子命令：

* `heap_profile android` - 通过 `adb` 对连接的 Android 设备上的进程进行 profile（之前的行为，未指定子命令时仍为默认）。
* `heap_profile host` - 通过 `LD_PRELOAD` 对本地 Linux 进程进行 profile。该脚本自动下载 `tracebox` 和 `libheapprofd_glibc_preload.so`，并在 Session 期间管理本地 `traced` 守护进程。

有关数据源的更多详细信息，请参阅[采集 traces](/docs/data-sources/native-heap-profiler.md)。

```
用法: heap_profile [-h] [common options] {android,host} ...

位置参数:
  {android,host}
    android   通过 adb 对连接的 Android 设备上的进程进行 profile
              （默认）。
    host      通过 LD_PRELOAD 对本地 Linux 进程进行 profile。
```

```
用法: heap_profile android [-h] [-i INTERVAL] [-d DURATION] [--no-start]
                            [-p PIDS] [-n NAMES] [-c CONTINUOUS_DUMP]
                            [--heaps HEAPS] [--all-heaps]
                            [--no-android-tree-symbolization]
                            [--disable-selinux] [--no-versions] [--no-running]
                            [--no-startup] [--shmem-size SHMEM_SIZE]
                            [--block-client]
                            [--block-client-timeout BLOCK_CLIENT_TIMEOUT]
                            [--no-block-client] [--idle-allocations]
                            [--dump-at-max] [--disable-fork-teardown]
                            [--simpleperf]
                            [--traceconv-binary TRACECONV_BINARY]
                            [--no-annotations] [--print-config] [-o DIRECTORY]
```

```
用法: heap_profile host [-h] [-i INTERVAL] [-d DURATION] [--no-start]
                         [-n NAMES] [-c CONTINUOUS_DUMP]
                         [--heaps HEAPS] [--all-heaps]
                         [--shmem-size SHMEM_SIZE] [--block-client]
                         [--block-client-timeout BLOCK_CLIENT_TIMEOUT]
                         [--no-block-client] [--idle-allocations]
                         [--dump-at-max] [--disable-fork-teardown]
                         [--traceconv-binary TRACECONV_BINARY]
                         [--no-annotations] [--print-config] [-o DIRECTORY]
                         [--preload-library PRELOAD_LIBRARY]
                         [--tracebox-binary TRACEBOX_BINARY]
                         -- COMMAND [ARGS...]
```

## COMMON OPTIONS

这些标志适用于 `android` 和 `host` 子命令。

`-n`, `--name` _NAMES_
::    要 profile 的进程名称的逗号分隔列表。在 `host` 上，如果省略，则使用 `--` 后命令的基本名称。

`-i`, `--interval`
::    采样间隔。默认 4096 (4KiB)。

`-o`, `--output` _DIRECTORY_
::    输出目录。如果已存在则必须为空。

`--all-heaps`
::    从目标注册的所有堆中收集分配。

`--heaps` _HEAPS_
::    要收集的堆的逗号分隔列表，例如：`libc.malloc,com.android.art`。需要 Android 12。

`--block-client`
::    当缓冲区已满时，阻塞客户端等待缓冲区空间。谨慎使用，因为这可能会显著降低客户端速度。这是默认选项。

`--block-client-timeout`
::    如果给出了 `--block-client`，则不要阻塞任何分配超过此超时时间（微秒）。

`--no-block-client`
::    当缓冲区已满时，提前停止 profile。

`-c`, `--continuous-dump`
::    转储间隔（毫秒）。0 禁用连续转储。

`-d`, `--duration`
::    Profile 持续时间（毫秒）。0 运行直到被中断。默认：直到被用户中断。

`--disable-fork-teardown`
::    不要在 Fork 中拆除客户端。这对于使用 vfork 的程序很有用。仅限 Android 11+。

`--dump-at-max`
::    转储最大内存使用量而不是转储时的内存使用量。

`--idle-allocations`
::    追踪自上次转储以来每个调用堆栈有多少字节未使用。

`--no-annotations`
::    不在 pprof 函数名后附加 Android ART 模式注释，例如 `[jit]`。

`--no-running`
::    不针对已经运行的进程。需要 Android 11。

`--no-start`
::    无操作，保留以实现向后兼容。

`--no-startup`
::    不针对在 Profile 期间启动的进程。需要 Android 11。

`--print-config`
::    打印配置而不是运行。用于调试。

`--shmem-size`
::    客户端和 heapprofd 之间的缓冲区大小。默认 8MiB。必须是 4096 的 2 的幂的倍数，至少 8192。

`--traceconv-binary`
::    本地 traceconv 的路径。用于调试。

`-h`, `--help`
::    显示帮助消息并退出。

## ANDROID-ONLY OPTIONS

这些标志在脚本中以 `args.subcommand == 'android'` 进行限制，传递给 `host` 时无效。

`-p`, `--pid` _PIDS_
::    要 Profile 的 PID 的逗号分隔列表。

`--disable-selinux`
::    在 Profile 持续时间内禁用 SELinux 强制执行。

`--no-android-tree-symbolization`
::    不使用 Android 树中当前 lunched 的目标进行符号化。

`--no-versions`
::    不获取关于 APK 的版本信息。

`--simpleperf`
::    获取 heapprofd 的 simpleperf 分析。这仅用于 heapprofd 开发。

## HOST-ONLY OPTIONS

`--preload-library` _PRELOAD\_LIBRARY_
::    `libheapprofd_glibc_preload.so` 的路径。如果省略，预构建版本将自动下载（linux-amd64/arm/arm64）。

`--tracebox-binary` _TRACEBOX\_BINARY_
::    本地 tracebox 二进制文件的路径。用于调试。

`--` _COMMAND_ [_ARGS..._]
::    必需的位置参数。要在 `LD_PRELOAD` 下启动的命令。二进制文件以 `PERFETTO_HEAPPROFD_BLOCKING_INIT=1` 运行，因此第一次分配会阻塞，直到 heapprofd 附加。

## 示例

对连接的 Android 设备上的 `system_server` 进行 Profile，直到被中断：

```bash
tools/heap_profile android -n system_server
```

对本地 Linux 二进制文件进行 Profile，从启动时捕获每次分配：

```bash
tools/heap_profile host -- ./my_binary --some-flag
```

`com.example.app` 的定期 5 秒快照：

```bash
tools/heap_profile android -n com.example.app -c 5000
```

打印给定调用将发出的 trace 配置，而不实际运行：

```bash
tools/heap_profile android -n system_server --print-config
```

## 备注

* 不带子命令的直接调用 `heap_profile -n NAME` 保留以实现向后兼容，等同于 `heap_profile android -n NAME`。新脚本应使用显式形式。
* `host` 子命令仅在 Linux 上运行；在其他平台上会报错。
* 有关生成 trace 的符号化和 Java/Kotlin 反混淆，请参阅[符号化和反混淆](/docs/learning-more/symbolization.md)。
