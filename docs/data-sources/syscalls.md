# 系统调用

在 Linux 和 Android（仅限 userdebug 构建上）上，Perfetto 可以 trace 系统调用。

目前，只有系统调用号记录在 trace 中，参数不存储以限制 trace 大小开销。

在导入时，Trace Processor 使用内部系统调用映射表，目前支持 x86、x86_64、ArmEabi、aarch32 和 aarch64。这些表通过 [`extract_linux_syscall_tables`](/tools/extract_linux_syscall_tables) 脚本生成。

## UI

在 UI 级别，系统调用与每个线程的 Slice track 内联显示：

![](/docs/images/syscalls.png '线程 track 中的系统调用')

## SQL

在 SQL 级别，系统调用与任何其他用户空间 Slice 事件没有什么不同。它们在每线程 Slice 堆栈中交错，可以通过查找 'sys\_' 前缀轻松过滤：

```sql
select ts, dur, t.name as thread, s.name, depth from slices as s
left join thread_track as tt on s.track_id = tt.id
left join thread as t on tt.utid = t.utid
where s.name like 'sys_%'
```

| ts | dur | thread | name |
| --------------- | --------- | --------------- | --------------- |
| 856325324372751 | 439867648 | s.nexuslauncher | sys_epoll_pwait |
| 856325324376970 | 990 | FpsThrottlerThr | sys_recvfrom |
| 856325324378376 | 2657 | surfaceflinger | sys_ioctl |
| 856325324419574 | 1250 | android.anim.lf | sys_recvfrom |
| 856325324428168 | 27344 | android.anim.lf | sys_ioctl |
| 856325324451345 | 573 | FpsThrottlerThr | sys_getuid |

## TraceConfig

```protobuf
data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "raw_syscalls/sys_enter"
 ftrace_events: "raw_syscalls/sys_exit"
 }
 }
}
```
