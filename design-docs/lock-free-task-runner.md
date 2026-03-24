# LockFreeTaskRunner 设计文档

## 概述

[`base::LockFreeTaskRunner`](/include/perfetto/ext/base/lock_free_task_runner.h) 是一个跨平台的无锁多生产者单消费者任务执行引擎，是 Perfetto 大部分代码的基础，包括 SDK 和设备上的服务。

它提供从多个线程进行线程安全任务发布，同时确保所有任务执行发生在单个指定线程上，消除了对传统的基于互斥锁的同步的需求。

关键属性：

- 无互斥锁或自旋锁：PostTask() 和 Run() 的时间有界。
- 在没有突发的情况下（即不超过 2 x 512 = 1024 个待处理任务），除了复制非平凡的 `std::function<void()>` 所需的内容外，不执行任何分配。
- 与传统的 UnixTaskRunner 兼容的行为：任务以相同的顺序提取和处理。

在避免锁争用方面，这个新的任务运行器比我们传统的 UnixTaskRunner 快约 2 倍：

```
$ out/rel/perfetto_benchmarks --benchmark_filter='.*BM_TaskRunner.*'
...
-------------------------------------------------------------------------------------------
Benchmark Time CPU Iterations
-------------------------------------------------------------------------------------------
BM_TaskRunner_SingleThreaded<UnixTaskRunner> 27778190 ns 27772029 ns 25
BM_TaskRunner_SingleThreaded<LockFreeTaskRunner> 10381056 ns 10375656 ns 67
BM_TaskRunner_MultiThreaded<UnixTaskRunner> 567794 ns 344625 ns 2033
BM_TaskRunner_MultiThreaded<LockFreeTaskRunner> 265943 ns 265754 ns 2749
```

## 架构

在本文档的其余部分，我们将把线程称为：

- **写入者** 调用 `PostTask()` 的 N 个线程。
- **读取者** 在 `Run()` 循环中运行任务的线程。

本文档仅关注 PostTask() 的设计，完全不讨论 PostDelayedTask() 或 Add/RemoveFileDescriptorWatch()。这些函数的逻辑与传统 UnixTaskRunner 保持不变，它们只是通过首先跳转到任务运行者线程来实现，然后在主线程上操作延迟任务列表和 FD 集。
这涉及与传统 UnixTaskRunner 相比的额外跳转（如果从其他线程调用）。然而：(1) 在实践中，我们代码库中对 PostDelayedTask() 和 Add/RemoveFileDescriptorWatch() 的大多数调用都发生在主线程上;（2）它们几乎不是热路径。


### 基于 Slab 的架构

LockFreeTaskRunner 使用基于 slab 的方法实现 **多生产者单消费者(MPSC)** 队列。

Slab 包含：

- **任务数组**： 512 个任务槽的固定大小数组（`kSlabSize`）。
 这些由写入者线程写入，由读取者线程消费。

- **槽 Counter**： 用于保留槽的原子 Counter `next_task_slot`。
 这用于确定写入者应该获取数组中的哪个槽（或者确定 slab 已满）。
 这仅由写入者线程访问，从不由读取者访问。
 当 slab 已满时，这可能在竞争情况下增长 > `kSlabSize`(没关系，一旦所有槽都满了，`next_task_slot` 的值就变得无用)。

- **发布位图**： `tasks_written`。一个 512 位的固定位图，每个任务一个。位由写入者线程通过原子释放-OR 操作翻转，以指示第 i 个槽中的任务准备好并且可以消费。读取者线程从不改变此位图。最终它变为 0xff..ff 并在整个 Slab 的生命周期中保持那样。

- **消费位图**： `tasks_read`。与上述类似，但这仅由读取者线程访问。当任务被消费时，位翻转为 1。写入者线程从不访问此位图。最终这也变为 0xff..ff。
 Slab 只能在两个位图都已填充时被删除（所有任务槽都已被写入者写入并被读取者消费）。

- **链表指针**： `prev` 指向前一个 Slab。
 这仅由读取者线程遍历。写入者只查看最新的 slab，从不访问 prev 指针（除了在构建新 Slab 时）。

Slabs 排列为单向链表。

请注意，此列表不是原子的，只有 `tail_` 指针是。读取者线程是遍历列表的唯一线程，写入者只访问最新的 Slab，并最终追加新的 Slabs，替换 `tail_`。


```
 tail_ (atomic_shared_ptr)
 |
 ▼
 +-----------------+ +-----------------+ +-----------------+
 | Slab N | | Slab N-1 | | Slab 0 |
 | tasks: [....] | | tasks: [....] | | tasks: [....] |
 | next_task_slot | | next_task_slot | | next_task_slot |
 | prev (sptr) ----+----->| prev (sptr) ----+----->| prev = nullptr |
 +-----------------+ +-----------------+ +-----------------+
```

1. **单向访问**： Producer 线程只访问 `tail` slab，从不向后遍历。
2. **消费者所有权**：只有主线程遵循 `prev` 指针并排空任务。
3. **突发处理**：新 slab 在当前 slab 已满时由写入者自动分配。

在正常条件下（即没有数千个任务的突发），我们只有两个 slab。大小为 1 的空闲列表（`free_slab_`）避免了对分配器的压力，有效地在两个 slab 之间翻转而无需 new/delete。

只有尾指针的单向链表表明读取者具有 O(N) 的最坏情况复杂度，因为它必须遍历整个列表才能到达第一个任务（它必须 FIFO 运行任务）。然而，在实践中我们期望总是只有两个 slab(如果我们有 10k-100k 个任务的队列，遍历列表是我们最后的问题)。

此设计的主要缺点是它在大量任务时扩展性差，因为 Run() 变得更慢（以遍历列表）并且堆栈贪婪（它在堆栈上使用递归来遍历列表而不使用堆）。我们不期望在 Perfetto 中有大量待处理任务（已知问题 b/330580374 等除外，无论如何都应该修复）。

## 线程考虑

### 生产者线程工作流程

`PostTask()` 操作遵循此无锁协议：

1. **加载尾部**： 原子加载当前 `tail_` slab 指针
2. **获取引用计数**： 为此 Slab 增加引用计数桶(稍后讨论)
3. **保留槽**： 原子递增 `next_task_slot` 以保留位置
4. **处理溢出**： 如果 slab 已满，分配新 slab 并尝试原子更新 `tail_`
5. **写入任务**： 在保留的槽中存储任务
6. **发布**： 使用释放语义在 `tasks_written` 位掩码中设置相应的位
7. **释放引用计数**： 在 `ScopedRefcount` 析构函数运行时自动递减

#### 溢出处理

当 slab 变满时(`slot >= kSlabSize`):

```cpp
Slab* new_slab = AllocNewSlab();
new_slab->prev = slab;
new_slab->next_task_slot.store(1, std::memory_order_relaxed);
slot = 0;
if (!tail_.compare_exchange_strong(slab, new_slab)) {
 // 另一个线程赢得了竞争，使用他们的 slab 重试
 new_slab->prev = nullptr;
 DeleteSlab(new_slab);
 continue;
}
```

### 消费者线程工作流程

`Run()` 中的主线程执行：

1. **任务排空**： `PopNextImmediateTask()` 获取下一个任务
2. **延迟任务处理**： 检查过期的延迟任务
3. **文件描述符轮询**： 处理 I/O 事件并确保公平性
4. **任务执行**： 带看门狗保护运行任务

在当前设计中，运行循环对每个任务执行一次 poll()。这可以说是可优化的：如果我们知道有突发的任务，我们可以背靠背地运行它们，而不在 poll(timeout=0) 上浪费系统调用时间。

当然，这需要一些限制，以防止 livelocks，在那种情况下，（设计糟糕的）函数不断重新发布自己，直到 socket 收到数据（这将需要 FD watch 任务触发）。

然而，多年来我们的测试已经累积了对传统 UnixTaskRunner 的严格公平性的依赖。它们期望能够通过 `IsIdleForTesting()` 告知事件地平线上是否有任何即将到来的 FD watch。正如 Hyrum 定律所教导的，这现在是我们的 TaskRunner 的一个 API，并将持续到几个测试被重写和去抖动之前。


#### 任务消费算法

`PopTaskRecursive()` 实现消费逻辑：

- 它使用递归遍历回 Slabs 列表（在正常条件下实际上只回退一个 Slab）。
- 它扫描 `task_written` 位图中的所有位，并将它们与 `task_read` 位图与运算以按顺序提取未消费的任务。
- 如果所有任务都被读取，则进行 Slab 的删除（稍后更多）。

```cpp
std::function<void()> PopTaskRecursive(Slab* slab, Slab* next_slab) {
 // 首先,递归检查较旧的 slabs(FIFO 顺序)
 Slab* prev = slab->prev;
 if (prev) {
 auto task = PopTaskRecursive(prev, slab);
 if (task) return task;
 }
 
 // 然后检查当前 slab 的已发布任务
 for (size_t w = 0; w < Slab::kNumWords; ++w) {
 BitWord wr_word = slab->tasks_written[w].load(std::memory_order_acquire);
 BitWord rd_word = slab->tasks_read[w];
 BitWord unread_word = wr_word & ~rd_word;
 // 查找并消费第一个未读任务...
 }
 
 // 安全的 slab 删除逻辑...
}
```

### 引用计数系统

乍一看，写入者只访问尾部 Slab 并且从不回退列表的简单访问模式极大地简化了对复杂同步原语的需求。然而，有一个微妙的竞争需要考虑，这需要一些复杂性。

考虑以下场景，其中两个写入者线程正在调用 `PostTask()`，而读取者同时运行并删除一个 slab。

**初始条件**：

任务运行器只包含一个 Slab S0，恰好是满的：
`tail_ -> S0 (full) -> nullptr`

**竞争**：

- 线程 A 读取 `tail_` 指针并读取 S0 的地址。在继续进行 `next_task_slot` 的原子递增（这将揭示 Slab 已满）之前，它被抢占，暂停一会儿。
 ```cpp
 slab = tail_.load();
 // 抢占发生在这里
 slab->next_task_slot.fetch_add(1);
 ...
 ```

- 线程 B 做同样的事情，但没有被抢占。所以它读取 S0，发现它已满，分配一个新的 Slab S1 并替换尾部。
 线程 B 很高兴，现在：
 `tail_ -> S1 -> S0 -> nullptr`

- Run() 线程开始循环。它注意到有两个 slabs，注意到 S0 已满，不是尾部并且因此安全（!）可以删除。

- 此时线程 A 恢复其执行，尝试递增 S0->`next_task_slot`，但 S0 已被删除，导致 use-after-free。


**是什么导致了这种竞争？**

确实，删除非尾部 Slab 是安全的，因为写入者不遍历链表。但是，线程可能在它恰好是尾部时观察到了非尾部 Slab，并且读取者线程没有办法知道。

向 Slab 本身添加引用计数（或任何其他属性）是无用的，因为它不解决关键问题，即 Slab 可能消失了。缓解需要在 Slab 之外发生。

在 LockFreeTaskRunner 的中间设计中，使用 `shared_ptr<Slab>` 来缓解此问题。非侵入式 STL `shared_ptr` 引入了中间控制块，该控制块将 Slab 与其引用计数解耦。不幸的是，libcxx 实现对 shared_ptr（需要从不同线程交换 `shared_ptr<Slab> tail_`）的原子访问使用 32 个互斥锁的哈希池，实际上打破了我们的无锁意图（请参阅 [`__get_sp_mut`][__get_sp_mut]）。

[__get_sp_mut]: https://github.com/llvm/llvm-project/blob/249167a8982afc3f55237baf1532c5c8ebd850b3/libcxx/src/memory.cpp#L123

**最初的简单缓解方法**：

最初的简单缓解方法如下：想象每个写入者在开始之前增加一个全局引用计数（例如 `task_runner.num_writers_active`），并在完成其 PostTask() 后减少它。这将允许读取者知道在任何时间点是否有任何写入者处于活动状态。

在读取者侧，如果 `num_writers_active > 0`，我们可以跳过删除 slab - 并在下一个任务时再试。请注意，这不是互斥锁，也不是自旋锁，因为没有人等待其他人。它基于以下原则：

- 写入者只能通过 `tail_` 指针观察 Slab。
- 当读取者决定删除 slab 时，它只删除非尾部 Slabs，因此它知道 `tail_` 指向与正在删除的 slab 不同的 slab。
- 如果没有写入者处于活动状态，没有人可能观察到任何 Slab，更不用说正在被删除的 Slab。
- 如果写入者在 `num_writers_active > 0` 检查后立即变为活动状态，它必然会观察到新的尾部 Slab(假设 _顺序一致性_)，并且无法观察正在被删除的较旧 Slab。

现在，虽然这将解决我们的竞争，但它会使我们暴露于一个有问题的场景：如果写入者线程恰好每次 Run() 到达该检查时都在发布任务，我们可能永远无法删除 slabs。

诚然，此场景相当不现实：如果写入者始终处于活动状态，我们可能会爆炸任务运行器，假设任务运行需要比调用 PostTask() 更多的时间。

**当前的缓解方法**：

原则上，我们希望每个 Slab 有一个引用计数。但是，如前所述，引用计数不能存在于 Slab 本身上，因为它用于控制对 slab 的访问。

我们可以在任务运行器中使用 `map<Slab*, atomic<int>>` 持有每个 slab 的引用计数，但这会导致堆开销，并且还需要一个无锁映射。

我们选择的是一种折衷解决方案：我们有一个固定数量（32）的引用计数桶，并通过哈希函数将每个 Slab 映射到一个桶。

当然，两个 slabs 可能最终共享相同的引用计数，创建误报：由于哈希冲突，我们可能认为 Slab 被引用计数，即使它没有。

但是，在此上下文中，误报是无害的。在绝对最坏的情况下，我们退化为上述描述的简单缓解方法，这在竞争视角下仍然是正确的。

在实践中，我们将延迟 Slab 删除的概率除以了 32 倍。

这是支持 `LockFreeTaskRunner.refcounts_` 原子整数数组和写入者使用的 `ScopedRefCount` 类的逻辑。


### 延迟任务处理

延迟任务使用单独的 `FlatSet<DelayedTask>` 容器。这需要一些成本来维护条目排序（我们期望只有少数延迟任务，因为它们主要用于超时），但避免了大多数情况下的分配（FlatSet 基于向量，并且仅在必要时分配）。

另一方面，反向排序允许 Run 以 O(1) 提取任务。
