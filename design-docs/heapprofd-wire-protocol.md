# heapprofd： 共享内存

_**状态**： 已实现_  
_**作者**： fmayer_  
_**审阅者**： rsavitski, primiano_  
_**最后更新**： 2019-02-11_

## 目标
重构 heapprofd 以使用 <code>[SharedRingBuffer](https://cs.android.com/android/platform/superproject/main/+/main:external/perfetto/src/profiling/memory/shared_ring_buffer.cc)</code>。


## 概述
不使用 socket 池将调用堆栈和 frees 发送到 heapprofd，而是使用单个共享内存缓冲区和信号 socket。客户端将描述 mallocs 或 frees 的记录写入共享内存缓冲区，然后在信号 socket 上发送一个字节以唤醒服务。

![](/docs/images/heapprofd-design/shmem-overview.png)

## 高级设计
在客户端和 heapprofd 之间使用共享内存缓冲区消除了服务中尽可能快地排空 socket 的需要，我们以前需要这样做以确保不阻塞客户端的 malloc 调用。这允许我们简化 heapprofd 的线程设计。

_主线程_具有与 traced 的 Perfetto producer 连接，并处理 `/dev/socket/heapprofd` 的传入客户端连接。它执行查找匹配传入 TraceConfig 的进程的逻辑，将进程与客户端配置匹配，并与客户端进行握手。在此握手期间，服务创建共享内存缓冲区。握手完成后，客户端的 socket 移交给特定的 _Unwinder Thread_。

握手完成后，sockets 由分配的 _Unwinder Thread's_ 事件循环处理。展开器线程拥有展开所需的元数据（`/proc/pid/{mem,maps}` FD，派生的 libunwindstack 对象和共享内存缓冲区）。在信号 socket 上接收到数据时，_展开线程_展开客户端提供的调用堆栈并发布任务到 _主线程_ 以应用于记账。重复此操作，直到缓冲区中没有更多待处理的记录。

要关闭 tracing session，_主线程_ 在相应的 _展开线程_ 上发布任务以关闭连接。当客户端断开连接时，_展开线程_ 在 _主线程_ 上发布任务以通知它断开连接。意外断开连接也是如此。

![](/docs/images/heapprofd-design/shmem-detail.png)

### 所有权
在任何时候，每个对象都只由一个线程拥有。不同线程之间不共享任何引用或指针。

**_主线程：_**

- 握手完成前的信号 sockets。
- 记账数据。
- 连接的进程集和 TraceConfigs(在 `ProcessMatcher` 类中)。

**_展开线程，每个进程：_**

- 握手完成后的信号 sockets。
- `/proc/pid/{mem,maps}` 的 libunwindstack 对象。
- 共享内存缓冲区。


## 详细设计
请参阅下面序列图中的以下阶段：

### 1. 握手
_主线程_ 从 traced 接收包含 `HeapprofdConfig` 的 `TracingConfig`。它将预期连接的进程及其 `ClientConfiguration` 添加到 `ProcessMatcher`。然后它查找匹配的进程（通过 PID 或 cmdline）并发送 heapprofd RT 信号以触发初始化。

接收此配置的进程连接到 `/dev/socket/heapprofd` 并发送 `/proc/self/{map,mem}` fd。_主线程_ 在 `ProcessMatcher` 中查找匹配的配置，创建新的共享内存缓冲区，并通过信号 socket 发送两者。客户端使用它们完成其内部状态的初始化。_主线程_ 将信号 socket 移交（`RemoveFiledescriptorWatch` + `AddFiledescriptorWatch`）给 _展开线程_。它还移交 `/proc` fd 的 `ScopedFile`s。这些用于创建 `UnwindingMetadata`。


### 2. 采样
既然握手已完成，所有通信都在 _客户端_ 和其对应的 _展开线程_ 之间进行。

对于每个 malloc，客户端决定是否采样分配，如果是，将 `AllocMetadata` + 原始堆栈写入共享内存缓冲区，然后在信号 socket 上发送一个字节以唤醒 _展开线程_。_展开线程_ 使用 `DoUnwind` 获取 `AllocRecord`(元数据，如大小、地址等 + 帧向量)。然后它发布任务到 _主线程_ 以将其应用于记账。


### 3. 转储/并发采样
转储请求可以由两种情况触发：

- 连续转储
- 来自 traced 的刷新请求

这两种情况的处理方式相同。_主线程_ 转储相关进程的记账并将缓冲区刷新到 traced。

通常，_展开线程_ 将从客户端接收并发记录。它们将继续展开并发布任务以应用记账。记账将在转储完成后应用，因为记账数据不能被并发修改。


### 4. 断开连接
traced 发送 `StopDataSource` IPC。_主线程_ 发布任务到 _展开线程_ 要求它断开与客户端的连接。它取消映射共享内存，关闭 memfd，然后关闭信号 socket。

客户端在下次尝试通过该 socket 发送数据时收到 `EPIPE`，然后拆除客户端。

![shared memory sequence diagram](/docs/images/heapprofd-design/Shared-Memory0.png "shared memory sequence diagram")


## 对客户端的更改
客户端将不再需要 socket 池，因为所有操作都在同一个共享内存缓冲区和单个信号 socket 上完成。相反，数据被写入共享内存缓冲区，然后在非阻塞模式下在信号 socket 上发送一个字节。

我们需要小心使用哪个操作将调用堆栈复制到共享内存缓冲区，因为 `memcpy(3)` 可能会由于源加固而在堆栈帧保护上崩溃。


## 相对于当前设计的优势
- 线程之间清晰的所有权语义。
- 线程之间不传递引用或指针。
- 使用更少锁的更高效客户端。

## 相对于当前设计的缺点
- 使用共享内存缓冲区膨胀目标进程 PSS/RSS。
- TaskRunners 是无界队列。这有可能为行为异常的进程排队大量记账工作。由于应用记账信息是相对便宜的操作，我们接受此风险。
