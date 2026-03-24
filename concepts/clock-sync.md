# 多个时钟域的同步

根据 [6756fb05][6756fb05],Perfetto 使用不同的时钟域处理事件。除了默认的内置时钟域集外，还可在 trace 时间动态创建新的时钟域。

时钟域之间允许漂移。在导入时，只要 trace 中存在 [ClockSnapshot][clock_snapshot] 数据包，Perfetto 的 [Trace Processor](/docs/analysis/trace-processor.md) 就能够重建时钟图并使用该图将事件重新同步到全局 trace 时间上。

## 问题陈述

在复杂的多生产者场景中，不同的数据源可以使用不同的时钟域发出事件。

一些示例：

- 在 Linux/Android 上，Ftrace 事件使用 `CLOCK_BOOTTIME` 时钟发出，但 Android Event Log 使用 `CLOCK_REALTIME`。其他一些数据源可以使用 `CLOCK_MONOTONIC`。由于挂起/恢复，这些时钟可能会随时间相互漂移。

- 图形相关事件通常由 GPU 打上时间戳，它可以使用与系统时钟漂移的硬件时钟源。

在 trace 时间，数据源可能无法使用 `CLOCK_BOOTTIME`(或者即使可能，这样做也可能过于昂贵)。

为了解决这个问题，我们允许使用不同的时钟域记录事件，并在导入时使用时钟快照重新同步它们。

## Trace proto 语法

时钟同步基于 trace 的两个元素：

1. [TracePacket 的 timestamp_clock_id 字段](#timestamp_clock_id)
2. [ClockSnapshot trace 数据包](#clock_snapshot)

### {#timestamp_clock_id} TracePacket 的 timestamp_clock_id 字段

```protobuf
message TracePacket {
 optional uint64 timestamp = 8;

 // 指定用于 TracePacket |timestamp| 的时钟 ID。可以是
 // ClockSnapshot::BuiltinClocks 中的内置类型之一，或
 // 生产者定义的时钟 id。
 // 如果未指定，默认为 BuiltinClocks::BOOTTIME。
 optional uint32 timestamp_clock_id = 58;

```

此（可选）字段确定数据包的时钟域。如果省略，它指的是 trace 的默认时钟域（对于 Linux/Android 为 `CLOCK_BOOTTIME`）。如果存在，此字段可以设置为：

- [clock_snapshot.proto 中定义的内置时钟之一][builtin_clocks](例如，`CLOCK_BOOTTIME`、`CLOCK_REALTIME`、`CLOCK_MONOTONIC`)。这些时钟的 ID <= 63。
- 自定义序列作用域时钟，64 <= ID < 128
- 自定义全局作用域时钟，128 <= ID < 2**32

#### 内置时钟
内置时钟覆盖了数据源使用 POSIX 时钟之一的最常见情况（参见 `man clock_gettime`）。这些时钟由 `traced` 服务定期快照。生产者除了设置 `timestamp_clock_id` 字段外，不需要做任何事情即可发出使用这些时钟的事件。

#### 序列作用域时钟
序列作用域时钟是应用程序定义的时钟域，仅在同一 `TraceWriter` 编写的 TracePacket 序列内有效（即具有相同 `trusted_packet_sequence_id` 字段的 TracePacket）。在大多数情况下，这实际上意味着 *"同一数据源在同一线程上发出的事件"*。

这涵盖了仅在数据源内使用且不跨不同数据源共享的时钟域的最常见用例。序列作用域时钟的主要优点是避免了 ID 歧义问题，对于最简单的情况可以正常工作（&trade;）。

为了使用自定义序列作用域时钟域，数据源必须：

- 使用 `timestamp_clock_id` 在 [64, 127] 范围内发出数据包
- 至少发出一次 [`ClockSnapshot`][clock_snapshot] 数据包

这样的 `ClockSnapshot`:

- 必须在同一序列（即由同一 `TraceWriter`）上发出，该序列用于发出引用此类 `timestamp_clock_id` 的其他 `TracePacket`。
- 必须包含以下快照：(i) 自定义时钟 id [64, 127] 和 (ii) 另一个时钟域，该时钟域可以在导入时针对默认 trace 时钟域（`CLOCK_BOOTTIME`）进行解析(参见下面的 [操作部分](#operation))。

两个不同 `TraceWriter` 序列之间的 `timestamp_clock_id` 冲突是可以的。例如，两个彼此不知情的数据源都可以使用时钟 ID 64 来引用两个不同的时钟域。

#### 全局作用域时钟
全局作用域时钟域与序列作用域时钟域类似工作，唯一的区别是它们的作用域是全局的，适用于 trace 的所有 `TracePacket`。

上述相同的 `ClockSnapshot` 规则适用。唯一的区别是，一旦 `ClockSnapshot` 定义了 ID >= 128 的时钟域，该时钟域可以被任何 `TraceWriter` 序列编写的任何 `TracePacket` 引用。

必须小心避免由彼此不知情的不同数据源定义的全局时钟域之间的冲突。

因此，**强烈不建议**仅使用 ID 128(或任何其他任意选择的值)。相反，推荐的模式是：

- 为时钟域选择一个完全限定的名称(例如 `com.example.my_subsystem`)
- 选择时钟 ID 为 `HASH("com.example.my_subsystem") | 0x80000000`，其中 `HASH(x)` 是完全限定的时钟域名称的 FNV-1a 哈希。

### {#clock_snapshot} ClockSnapshot trace 数据包

[`ClockSnapshot`][clock_snapshot] 数据包定义两个或多个时钟域之间的同步点。它传达了 *"在此时刻，时钟域 X,Y,Z 的时间戳为 1000、2000、3000"* 的概念。

trace 导入器([Trace Processor](/docs/analysis/trace-processor.md)) 使用此信息在这些时钟域之间建立映射。例如，意识到时钟域 X 上的 1042 == 时钟域 Z 上的 3042。

`traced` 服务定期自动为内置时钟域发出 `ClockSnapshot` 数据包。

数据源应仅在使用自定义时钟域（无论是序列作用域还是全局作用域）时发出 `ClockSnapshot` 数据包。

自定义时钟域的 `ClockSnapshot` *不必*包含 `CLOCK_BOOTTIME` 的快照（尽管如果可能，建议这样做）。Trace Processor 可以基于图遍历处理多路径时钟域解析（参见 [操作](#operation） 部分)。

## 操作

在导入时，Trace Processor 将尝试使用到目前为止看到的 `ClockSnapshot` 数据包，通过最近邻近似将每个 TracePacket 的时间戳转换为 trace 时钟域（`CLOCK_BOOTTIME`）。

例如，假设 trace 包含 `CLOCK_BOOTTIME` 和 `CLOCK_MONOTONIC` 的 `ClockSnapshot`，如下所示：

```python
CLOCK_MONOTONIC 1000 1100 1200 1900 ... 2000 2100
CLOCK_BOOTTIME 2000 2100 2200 2900 ... 3500 3600
```

在此示例中，`CLOCK_MONOTONIC` 比 `CLOCK_BOOTTIME` 领先 1000 ns，直到 T=2900。然后两个时钟失去同步（例如，设备被挂起），并且在下一个快照中，两个时钟相距 1500 ns。

如果看到 `timestamp_clock_id=CLOCK_MONOTONIC` 和 `timestamp=1104` 的 `TracePacket`，时钟同步逻辑将：

1. 找到 `CLOCK_MONOTONIC` <= 1104 的最新快照(在上面的示例中是 `CLOCK_MONOTONIC=1100` 的第二个)
2. 通过将 delta（1104 - 1100）应用于相应的 `CLOCK_BOOTTIME` 快照（2100，所以 2100 + （1104 - 1100） -> 2104）来计算到 `CLOCK_BOOTTIME` 的时钟域转换。

上面的示例相当简单，因为源时钟域（即由 `timestamp_clock_id` 字段指定的时钟域）和目标时钟域（即 trace 时间，`CLOCK_BOTTIME`）在同一个 `ClockSnapshot` 数据包中快照。

即使两个域未直接连接，只要两者之间存在路径，也可以进行时钟域转换。

从这个意义上说，`ClockSnapshot` 数据包定义了一个非循环图的边，该图被查询以执行时钟域转换。所有类型的时钟域都可以在图搜索中使用。

在更一般的情况下，时钟域转换逻辑操作如下：

- 使用图中的广度优先搜索，识别源时钟域和目标时钟域之间的最短路径。
- 对于识别的路径的每个时钟域，使用上述最近邻解析转换时间戳。

这允许处理以下复杂场景：

```python
CUSTOM_CLOCK 1000 3000
CLOCK_MONOTONIC 1100 1200 3200 4000
CLOCK_BOOTTIME 5200 9000
```

在上面的示例中，没有快照直接链接 `CUSTOM_CLOCK` 和 `CLOCK_BOOTTIME`。但是存在一个间接路径，允许通过 `CUSTOM_CLOCK -> CLOCK_MONOTONIC -> CLOCK_BOOTTIME` 进行转换。

这允许同步假设的 `TracePacket`，其具有 `timestamp_clock_id=CUSTOM_CLOCK` 和 `timestamp=3503`，如下所示：

```python
# 步骤 1
CUSTOM_CLOCK = 3503
最近快照: {CUSTOM_CLOCK:3000, CLOCK_MONOTONIC:3200}
CLOCK_MONOTONIC = (3503 - 3000) + 3200 = 3703

# 步骤 2
CLOCK_MONOTONIC = 3703
最近快照: {CLOCK_MONOTONIC:1200, CLOCK_BOOTTIME:5200}
CLOCK_BOOTTIME = (3703 - 1200) + 5200 = 7703
```

## 注意事项

仅当 A -> B 路径中的所有时钟域都是单调的（或者至少在 `ClockSnapshot` 数据包中看起来是这样）时，才允许两个域（A,B）之间的时钟解析。如果在导入时检测到非单调性，则该时钟域在图搜索中被排除作为源路径，仅允许作为目标路径。

例如，想象在应用夏令时的夜间捕获一个 trace，该 trace 具有包括 `CLOCK_BOOTTIME` 和 `CLOCK_REALTIME` 在内的两者，当时实时时钟从上午 3 点跳回上午 2 点。

这样的 trace 将包含几个快照，这些快照打破了两个时钟域之间的双射性。在这种情况下，将 `CLOCK_BOOTTIME` 时间戳转换为 `CLOCK_REALTIME` 始终可能而不会产生歧义（最终两个不同的时间戳可以解析为同一个 `CLOCK_REALTIME` 时间戳）。反之是不允许的，因为上午 2 点到上午 3 点之间的 `CLOCK_REALTIME` 时间戳有歧义，并且可以解析为两个不同的 `CLOCK_BOOTTIME` 时间戳)。

[6756fb05]: https://android-review.googlesource.com/c/platform/external/perfetto/+/1101915/
[clock_snapshot]: https://android.googlesource.com/platform/external/perfetto/+/refs/heads/main/protos/perfetto/trace/clock_snapshot.proto
[timestamp_clock_id]: https://android.googlesource.com/platform/external/perfetto/+/3e7ca4f5893f7d762ec24a2eac9a47343b226c6c/protos/perfetto/trace/trace_packet.proto#68
[builtin_clocks]: https://android.googlesource.com/platform/external/perfetto/+/3e7ca4f5893f7d762ec24a2eac9a47343b226c6c/protos/perfetto/trace/clock_snapshot.proto#25
