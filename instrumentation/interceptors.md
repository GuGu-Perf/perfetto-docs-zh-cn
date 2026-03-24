# Trace packet interceptors (Tracing SDK)

Trace packet interceptor 用于将数据源写入的 Trace packet 重定向到自定义 backend，而不是正常的 Perfetto tracing 服务。例如，console interceptor 在生成时将所有 Trace packet 打印到控制台。另一个潜在用途是将 Trace 数据导出到另一个 tracing 服务，例如 Android ATrace 或 Windows ETW。

Interceptor 通过子类化 `perfetto::Interceptor` 模板来定义：

```C++
class MyInterceptor : public perfetto::Interceptor<MyInterceptor> {
 public:
 ~MyInterceptor() override = default;

 // 此函数为每个拦截的 Trace packet 调用。|context|
 // 包含有关 Trace packet 的信息以及由 interceptor
 // 跟踪的其他状态（例如，参见 ThreadLocalState）。
 //
 // 拦截的 Trace 数据以序列化的 protobuf 字节形式提供，
 // 通过 |context.packet_data| 字段访问。
 //
 // 警告：此函数可以在任何时候在任何线程上调用。请参阅
 // 下文了解如何从此处安全地访问共享 interceptor 数据。
 static void OnTracePacket(InterceptorContext context) {
 perfetto::protos::pbzero::TracePacket::Decoder packet(
 context.packet_data.data, context.packet_data.size);
 // ... 将 |packet| 写入所需目标 ...
 }
};
```

Interceptor 应该在任何 tracing 会话启动之前注册。请注意，interceptor 还需要通过如下所示的 trace config 激活。

```C++
perfetto::InterceptorDescriptor desc;
desc.set_name("my_interceptor");
MyInterceptor::Register(desc);
```

最后，通过 trace config 启用 interceptor，如下所示：

```C++
perfetto::TraceConfig cfg;
auto* ds_cfg = cfg.add_data_sources()->mutable_config();
ds_cfg->set_name("data_source_to_intercept"); // 例如 "track_event"
ds_cfg->mutable_interceptor_config()->set_name("my_interceptor");
```

一旦启用了 interceptor，来自受影响数据源的所有数据都会发送到 interceptor，而不是主 tracing 缓冲区。

## Interceptor 状态

除了序列化的 Trace packet 数据，`OnTracePacket` interceptor 函数还可以访问其他三种类型的状态：

1. **全局状态：** 这与普通静态函数没有区别，但必须小心，因为 |OnTracePacket| 可以在任何时候在任何线程上并发调用。

2. **每个数据源实例状态：** 由于 interceptor 类为每个拦截的数据源自动实例化，其字段可以用于存储每个实例的数据，例如 trace config。此数据可以通过 OnSetup/OnStart/OnStop 回调维护：

 ```C++
 class MyInterceptor : public perfetto::Interceptor<MyInterceptor> {
 public:
 void OnSetup(const SetupArgs& args) override {
 enable_foo_ = args.config.interceptor_config().enable_foo();
 }

 bool enable_foo_{};
 };
 ```

 在 interceptor 函数中，必须通过作用域锁访问此数据以确保安全：

 ```C++
 class MyInterceptor : public perfetto::Interceptor<MyInterceptor> {
 ...
 static void OnTracePacket(InterceptorContext context) {
 auto my_interceptor = context.GetInterceptorLocked();
 if (my_interceptor) {
 // 在此处访问 MyInterceptor 的字段。
 if (my_interceptor->enable_foo_) { ... }
 }
 ...
 }
 };
 ```

 由于访问此数据涉及持有锁，因此应该谨慎使用。

3. **每个线程/TraceWriter 状态：** 许多数据源使用 interning 来避免在 trace 中重复常见数据。由于 interning 字典通常为每个 TraceWriter 序列（即每个线程）单独保留，interceptor 可以声明一个与 TraceWriter 生命周期匹配的数据结构：

 ```C++
 class MyInterceptor : public perfetto::Interceptor<MyInterceptor> {
 public:
 struct ThreadLocalState
 : public perfetto::InterceptorBase::ThreadLocalState {
 ThreadLocalState(ThreadLocalStateArgs&) override = default;
 ~ThreadLocalState() override = default;

 std::map<size_t, std::string> event_names;
 };
 };
 ```

 然后可以在 `OnTracePacket` 中访问和维护此每个线程的状态，如下所示：

 ```C++
 class MyInterceptor : public perfetto::Interceptor<MyInterceptor> {
 ...
 static void OnTracePacket(InterceptorContext context) {
 // 更新 interning 数据。
 auto& tls = context.GetThreadLocalState();
 if (parsed_packet.sequence_flags() & perfetto::protos::pbzero::
 TracePacket::SEQ_INCREMENTAL_STATE_CLEARED) {
 tls.event_names.clear();
 }
 for (const auto& entry : parsed_packet.interned_data().event_names())
 tls.event_names[entry.iid()] = entry.name();

 // 查找 interning 数据。
 if (parsed_packet.has_track_event()) {
 size_t name_iid = parsed_packet.track_event().name_iid();
 const std::string& event_name = tls.event_names[name_iid];
 }
 ...
 }
 };
 ```
