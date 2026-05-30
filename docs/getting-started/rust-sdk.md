# 使用 Rust SDK 记录 Trace

在本指南中，你将学习如何：

- 使用 Perfetto Rust SDK 向 Rust 应用添加 TracePoint。
- 记录包含自定义事件的 Trace。
- 使用 `#[tracefn]` 属性宏实现自动函数插桩。
- 使用 `tracing` crate 并以 Perfetto 作为后端。
- 使用 GPU 事件 ProtoBuf 扩展 `TracePacket`。

NOTE: Rust SDK 是社区维护项目。它可能不具备官方 C++ SDK 同等水平的支持、稳定性或功能覆盖。

Perfetto Rust SDK 为 Perfetto Tracing 框架提供了安全且符合 Rust 习惯的绑定。它将 Perfetto C API 封装为 Rust 抽象，用于管理 Tracing Session、DataSource 和 Track Event。

## Crate

SDK 分为多个 crate：

| Crate | 描述 |
|-------|------|
| `perfetto-sdk` | 核心 SDK，包含 Tracing Session、DataSource 和 Track Event |
| `perfetto-sdk-sys` | Perfetto C API 的底层 FFI 绑定 |
| `perfetto-sdk-derive` | `#[tracefn]` 过程宏，用于自动函数插桩 |
| `perfetto-sdk-protos-gpu` | GPU 事件 ProtoBuf 绑定，扩展 `TracePacket` |
| `perfetto-sdk-protos-trace-processor` | Trace Processor 的 ProtoBuf 绑定 |
| `tracing-perfetto-sdk` | Perfetto 的 `tracing-subscriber` Layer |

## 设置

将 SDK 添加到你的 `Cargo.toml`：

```toml
[dependencies]
perfetto-sdk = "1"
```

默认情况下，这会编译并静态链接捆绑的 Perfetto C 库。无需外部依赖。

## Track Event

初始化 Perfetto 并定义你的 Trace 类别：

```rust
use perfetto_sdk::producer::*;
use perfetto_sdk::track_event::*;
use perfetto_sdk::{scoped_track_event, track_event_begin, track_event_end, track_event_instant};

// 定义 Trace 类别。每个类别可以在 Trace 配置中
// 独立启用或禁用。
perfetto_sdk::track_event_categories! {
    pub mod my_categories {
        ("rendering", "Events from the graphics subsystem", []),
        ("network", "Network upload and download statistics", []),
    }
}
use my_categories as perfetto_te_ns;

fn main() {
    Producer::init(
        ProducerInitArgsBuilder::new()
            .backends(Backends::IN_PROCESS)
            .build(),
    );
    TrackEvent::init();
    my_categories::register().unwrap();

    // 作用域事件 —— 当作用域退出时结束。
    scoped_track_event!("rendering", "DrawPlayer",
        |ctx: &mut EventContext| {
            ctx.add_debug_arg("player_number",
                TrackEventDebugArg::Uint64(1));
        },
        |_| {}
    );

    // 手动 begin/end 事件。
    track_event_begin!("rendering", "DrawGame");
    track_event_end!("rendering");

    // 瞬时事件。
    track_event_instant!("rendering", "VSync");
}
```

## 收集 Trace

### 进程内 Tracing

对于无需 Tracing 服务的独立 Trace 收集，使用进程内后端创建 `TracingSession`。完整可运行示例见 `contrib/rust-sdk/perfetto/examples/tracing_session.rs`。

### 系统 Tracing

要连接到正在运行的 Perfetto Tracing 服务（`traced`），改用系统后端：

```rust
use perfetto_sdk::producer::*;

Producer::init(
    ProducerInitArgsBuilder::new()
        .backends(Backends::SYSTEM)
        .build(),
);
```

你的应用作为 Producer，系统 Tracing 服务控制何时开始和停止 Tracing。使用[系统 Tracing](/docs/getting-started/system-tracing.md)工具记录 Trace。

## 使用 `#[tracefn]` 自动函数插桩

`perfetto-sdk-derive` crate 提供了一个过程宏，可以自动用 Track Event 对函数进行插桩。它会将所有输入参数捕获为调试注解。

```toml
[dependencies]
perfetto-sdk = "1"
perfetto-sdk-derive = "1"
```

然后使用 `#[tracefn]` 注解函数：

```rust
// 假设类别定义与上例相同。
use perfetto_sdk::producer::*;
use perfetto_sdk::track_event::*;
perfetto_sdk::track_event_categories! {
    pub mod my_categories {
        ("rendering", "Events from the graphics subsystem", []),
    }
}
use my_categories as perfetto_te_ns;
use perfetto_sdk_derive::tracefn;

#[tracefn("rendering")]
fn draw_player(player_number: u32, x: f64, y: f64) {
    // 自动发出 "draw_player" Track Event。
    // player_number、x 和 y 被捕获为调试注解。
}
```

该宏将函数体包装在 `scoped_track_event!` 中，因此事件跨越整个函数执行。类别名作为宏参数传入。

## 使用 `tracing` crate

如果你的应用使用了 Rust 的 [`tracing`](https://crates.io/crates/tracing) crate，可以使用 `tracing-perfetto-sdk` 将事件发送到 Perfetto，而无需修改现有的插桩代码：

```toml
[dependencies]
tracing = "0.1"
tracing-subscriber = "0.3"
tracing-perfetto-sdk = "1"
```

初始化并安装 Layer：

```rust
use tracing_subscriber::prelude::*;

tracing_perfetto_sdk::init();
tracing_subscriber::registry()
    .with(tracing_perfetto_sdk::PerfettoLayer::new())
    .init();

// 标准 tracing 宏发出 Perfetto 事件。
let _span = tracing::info_span!("DrawGame").entered();
tracing::info!(player = 1, "drawing player");
```

Span 成为持续时间的 Slice，事件成为瞬时事件，字段被捕获为调试注解，源码位置自动附加。

## GPU 事件 ProtoBuf

`perfetto-sdk-protos-gpu` crate 扩展了 `TracePacket` 的 GPU 特定字段，用于发出 GPU Counter 事件、渲染阶段事件、Vulkan 事件等。

```toml
[dependencies]
perfetto-sdk = "1"
perfetto-sdk-protos-gpu = "1"
```

导入 `TracePacketExt` trait 以访问 GPU 字段：

```rust
use perfetto_sdk_protos_gpu::protos::trace::trace_packet::prelude::*;
use perfetto_sdk_protos_gpu::protos::trace::gpu::gpu_counter_event::*;

fn emit_gpu_counter(packet: &mut perfetto_sdk::protos::trace::trace_packet::TracePacket) {
    packet.set_gpu_counter_event(|event: &mut GpuCounterEvent| {
        event.set_counters(|counter: &mut GpuCounterEventGpuCounter| {
            counter.set_counter_id(1);
            counter.set_double_value(42.0);
        });
    });
}
```

这通常在自定义 DataSource 的 Trace 回调中使用。完整示例见 `contrib/rust-sdk/perfetto-protos-gpu/examples/gpu_counters.rs`。

## Track Event 扩展

可以使用扩展机制向 Track Event 添加自定义 ProtoBuf 字段。`perfetto-sdk-protos-gpu` crate 定义了 GPU 扩展，例如 `gpu_api`，用于标记 Track Event 的 GPU API 类型。

在 `EventContext` 上使用 `set_proto_fields` 添加扩展字段：

```rust
// 假设类别定义与上例相同。
use perfetto_sdk::producer::*;
use perfetto_sdk::track_event::*;
use perfetto_sdk::track_event_instant;
perfetto_sdk::track_event_categories! {
    pub mod my_categories {
        ("rendering", "Events from the graphics subsystem", []),
    }
}
use my_categories as perfetto_te_ns;
use perfetto_sdk_protos_gpu::protos::trace::gpu::gpu_track_event::{
    GpuApi, TrackEventExtFieldNumber,
};

track_event_instant!("rendering", "cuLaunchKernel", |ctx: &mut EventContext| {
    ctx.set_proto_fields(&TrackEventProtoFields {
        fields: &[TrackEventProtoField::VarInt(
            TrackEventExtFieldNumber::GpuApi as u32,
            GpuApi::GpuApiCuda as u64,
        )],
    });
});
```

扩展字段在 Trace 中显示为 Track Event 上的 `gpu_api: GPU_API_CUDA`，Trace Processor 会将其解码到 `slice` 表参数的 `gpu_api` 列中。

## 下一步

- **[Track Event](/docs/instrumentation/track-events.md)**：了解更多关于不同类型 Track Event 的信息。
- **[Rust SDK 示例](https://github.com/google/perfetto/tree/main/contrib/rust-sdk/perfetto/examples)**：DataSource、Track Event 和 Tracing Session 的可运行示例。
- **[GPU Counter 示例](https://github.com/google/perfetto/tree/main/contrib/rust-sdk/perfetto-protos-gpu/examples)**：GPU Counter DataSource 的示例。
