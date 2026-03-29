# 使用 FrameTimeline 检测 Android 掉帧

NOTE: **FrameTimeline 需要 Android 12(S) 或更高版本**

如果帧在屏幕上呈现的时间与调度器给定的预测呈现时间不匹配，则称该帧是掉帧的。

掉帧可能导致：
- 不稳定的帧率
- 增加的延迟

FrameTimeline 是 SurfaceFlinger 内的一个模块，它检测掉帧并报告掉帧的来源。[SurfaceViews](https://developer.android.com/reference/android/view/SurfaceView) 目前**不支持**，但将来会支持。

## UI

对于屏幕上至少有一帧的每个应用程序，都会添加两个新 track。

![](/docs/images/frametimeline/timeline_tracks.png)

- 预期 Timeline
每个 Slice 代表给应用程序渲染帧的时间。为了避免系统中的掉帧，应用程序应在此时间范围内完成。开始时间是安排 Choreographer 回调运行的时间。

- 实际 Timeline
这些 Slice 代表应用程序完成帧(包括 GPU 工作并将其发送到 SurfaceFlinger 进行合成所花费的实际时间。开始时间是 `Choreographer#doFrame` 或 `AChoreographer_vsyncCallback` 开始运行的时间。此处 Slice 的结束时间代表 `max(gpu 时间， 发布时间)`。**发布时间**是应用程序的帧发布到 SurfaceFlinger 的时间。

![](/docs/images/frametimeline/app-timelines.png)

同样，SurfaceFlinger 也会获得这两个新 track，代表它预期完成的时间，以及它完成合成帧和在屏幕上呈现所花费的实际时间。在这里，SurfaceFlinger 的工作表示显示堆栈中其下方的所有内容。这包括 Composer 和 DisplayHAL。因此，Slice 代表 SurfaceFlinger 主线程从开始到屏幕更新的过程。

Slice 的名称表示从 [choreographer](https://developer.android.com/reference/android/view/Choreographer) 接收的令牌。你可以将实际 Timeline track 中的 Slice 与预期 Timeline track 中的相应 Slice 进行比较，以查看应用程序的表现与预期相比如何。此外，出于调试目的，令牌被添加到应用程序的 **doFrame** 和 **RenderThread** Slice 中。对于 SurfaceFlinger，相同的令牌显示在 **onMessageReceived** 中。

![](/docs/images/frametimeline/app-vsyncid.png)

![](/docs/images/frametimeline/sf-vsyncid.png)

### 选择实际 Timeline Slice

![](/docs/images/frametimeline/selection.png)

选择详细信息提供了有关帧发生了什么的更多信息。这些包括：

- **呈现类型**

帧是早、按时还是晚。
- **按时完成**

应用程序是否按时完成了帧的工作？
- **掉帧类型**

是否观察到此帧有掉帧？如果是，这显示观察到的掉帧类型。如果没有，类型将为 **None**。
- **预测类型**

当 FrameTimeline 接收到此帧时，预测是否已过期？如果是，这将显示 **Expired Prediction**。如果不是，则显示 **Valid Prediction**。
- **GPU 合成**

布尔值，告诉帧是否由 GPU 合成。
- **图层名称**

帧呈现到的图层/表面的名称。某些进程会更新多个表面的帧。在这里，具有相同令牌的多个 Slice 将显示在实际 Timeline 中。图层名称是区分这些 Slice 的好方法。
- **是缓冲区？**

布尔值，告诉帧是对应于缓冲区还是动画。

### 流事件

在应用程序中选择实际 Timeline Slice 还会绘制一条线回相应的 SurfaceFlinger Timeline Slice。

![](/docs/images/frametimeline/select-app-slice.png)

由于 SurfaceFlinger 可以将多个图层的帧合成为单个屏幕上的帧（称为 **DisplayFrame**），选择 DisplayFrame 会绘制箭头到所有被一起合成的帧。这可以跨越多个进程。

![](/docs/images/frametimeline/select-sf-slice-1.png)
![](/docs/images/frametimeline/select-sf-slice-2.png)

### 颜色代码

| 颜色 | 图像 | 描述 |
| :--- | :---: | :--- |
| 绿色 | ![](/docs/images/frametimeline/green.png) | 良好的帧。未观察到掉帧 |
| 浅绿色 | ![](/docs/images/frametimeline/light-green.png) | 高延迟状态。帧率平滑，但帧呈现较晚，导致输入延迟增加。|
| 红色 | ![](/docs/images/frametimeline/red.png) | 掉帧的帧。Slice 所属的进程是掉帧的原因。 |
| 黄色 | ![](/docs/images/frametimeline/yellow.png) | 仅由应用程序使用。帧是掉帧的，但应用程序不是原因，SurfaceFlinger 导致了掉帧。 |
| 蓝色 | ![](/docs/images/frametimeline/blue.png) | 丢失的帧。在 SurfaceFlinger 中，这意味着我们跳过了一帧，更喜欢更新的帧而不是此帧。在应用程序方面，这意味着 UI 线程的状态更新没有及时推送到 RenderThread，并且 RenderThread 在没有来自 UI 线程的状态更新的情况下绘制了帧。 |

## 掉帧说明

掉帧类型在 [JankInfo.h](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/native/libs/gui/include/gui/JankInfo.h?l=22) 中定义。由于每个应用程序的编写方式不同，因此没有通用的方法来深入应用程序的内部并指定掉帧的原因。我们的目标不是这样做，而是提供一种快速的方法来判断应用程序是否掉帧或 SurfaceFlinger 是否掉帧。

### None

一切都很好。帧没有掉帧。应该追求的理想状态。

### 应用程序掉帧

- **AppDeadlineMissed**

应用程序运行时间超过预期，导致掉帧。应用程序帧所花费的总时间是通过使用 choreographer 唤醒作为开始时间和 max（gpu，发布时间）作为结束时间来计算的。发布时间是帧发送到 SurfaceFlinger 的时间。由于 GPU 通常并行运行，gpu 可能在发布时间之后完成。

- **BufferStuffing**

这更像是一种状态而不是掉帧。如果应用程序在上一个帧甚至呈现之前就不断向 SurfaceFlinger 发送新帧，就会发生这种情况。内部缓冲区队列被尚未呈现的缓冲区填充，因此名称为 Buffer Stuffing。队列中的这些额外缓冲区仅一个接一个地呈现，因此导致额外的延迟。这也可能导致没有更多缓冲区供应用程序使用的阶段，并且它进入出队阻塞等待。应用程序执行的实际持续时间可能仍在期限内，但由于填充的性质，无论应用程序完成其工作的速度如何，所有帧都将至少延迟一个 vsync 呈现。在此状态下，帧仍然平滑，但与延迟呈现相关联的输入延迟增加。

### SurfaceFlinger 掉帧

SurfaceFlinger 有两种方式可以合成帧：
- 设备合成 - 使用专用硬件
- GPU/客户端合成 - 使用 GPU 进行合成

需要注意的一点是，执行设备合成是主线程上的阻塞调用。然而，GPU 合成是并行进行的。SurfaceFlinger 执行必要的绘制调用，然后将 gpu 栅栏交给显示设备。显示设备然后等待栅栏发出信号，然后呈现帧。

- **SurfaceFlingerCpuDeadlineMissed**

SurfaceFlinger 预期在给定的期限内完成。如果主线程运行时间超过该时间，则掉帧为 SurfaceFlingerCpuDeadlineMissed。SurfaceFlinger 的 CPU 时间是在主线程上花费的时间。如果使用了设备合成，这包括整个合成时间。如果使用了 GPU 合成，这包括编写绘制调用和将帧交给 GPU 的时间。

- **SurfaceFlingerGpuDeadlineMissed**

SurfaceFlinger 主线程在 CPU 上花费的时间 + GPU 合成时间一起超过了预期。在这里，CPU 时间仍然会在期限内，但由于 GPU 上的工作未按时准备好，帧被推到下一个 vsync。

- **DisplayHAL**

DisplayHAL 掉帧是指 SurfaceFlinger 完成其工作并按时将帧发送到 HAL，但帧未在 vsync 上呈现的情况。它在下一个 vsync 上呈现。可能是 SurfaceFlinger 没有给 HAL 工作足够的时间，或者 HAL 工作确实有延迟。

- **PredictionError**

SurfaceFlinger 的调度器提前计划呈现帧的时间。然而，这种预测有时会偏离实际的硬件 vsync 时间。例如，帧的预测呈现时间可能为 20ms。由于估计中的漂移，帧的实际呈现时间可能为 23ms。这在 SurfaceFlinger 的调度器中称为预测误差。调度器会定期自我纠正，因此这种漂移不是永久的。然而，具有预测漂移的帧仍将被分类为掉帧以进行跟踪。

孤立的预测误差通常不会被用户感知，因为调度器很快会适应并修复漂移。

### 未知掉帧

顾名思义，在这种情况下掉帧的原因是未知的。这里的一个例子是 SurfaceFlinger 或应用程序运行时间超过预期并且错过了期限，但帧仍然提前呈现。这种掉帧发生的概率非常低，但并非不可能。

## SQL

在 SQL 级别，fremetimeline 数据在两个表中可用
- [`expected_frame_timeline_slice`](/docs/analysis/sql-tables.autogen#expected_frame_timeline_slice)
- [`actual_frame_timeline_slice`](/docs/analysis/sql-tables.autogen#actual_frame_timeline_slice)

```
select ts, dur, surface_frame_token as app_token, display_frame_token as sf_token, process.name
from expected_frame_timeline_slice left join process using(upid)
```

ts | dur | app_token | sf_token | name
---|-----|-----------|----------|-----
60230453475 | 20500000 | 3135 | 3142 | com.google.android.apps.nexuslauncher
60241677540 | 20500000 | 3137 | 3144 | com.google.android.apps.nexuslauncher
60252895412 | 20500000 | 3139 | 3146 | com.google.android.apps.nexuslauncher
60284614241 | 10500000 | 0 | 3144 | /system/bin/surfaceflinger
60295858299 | 10500000 | 0 | 3146 | /system/bin/surfaceflinger
60297798913 | 20500000 | 3147 | 3150 | com.android.systemui
60307075728 | 10500000 | 0 | 3148 | /system/bin/surfaceflinger
60318297746 | 10500000 | 0 | 3150 | /system/bin/surfaceflinger
60320236468 | 20500000 | 3151 | 3154 | com.android.systemui
60329511401 | 10500000 | 0 | 3152 | /system/bin/surfaceflinger
60340732956 | 10500000 | 0 | 3154 | /system/bin/surfaceflinger
60342673064 | 20500000 | 3155 | 3158 | com.android.systemui


```
select ts, dur, surface_frame_token as app_token, display_frame_token, jank_type, on_time_finish, present_type, layer_name, process.name
from actual_frame_timeline_slice left join process using(upid)
```

ts | dur | app_token | sf_token | jank_type | on_time_finish | present_type | layer_name | name
---|-----|-----------|----------|-----------|----------------|--------------|------------|-----
60230453475 | 26526379 | 3135 | 3142 | Buffer Stuffing | 1 | Late Present | TX - com.google.android.apps.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity#0 | com.google.android.apps.nexuslauncher
60241677540 | 28235805 | 3137 | 3144 | Buffer Stuffing | 1 | Late Present | TX - com.google.android.apps.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity#0 | com.google.android.apps.nexuslauncher
60252895412 | 2546525 | 3139 | 3142 | None | 1 | On-time Present | TX - NavigationBar0#0 | com.android.systemui
60252895412 | 27945382 | 3139 | 3146 | Buffer Stuffing | 1 | Late Present | TX - com.google.android.apps.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity#0 | com.google.android.apps.nexuslauncher
60284808190 | 10318230 | 0 | 3144 | None | 1 | On-time Present | [NULL] | /system/bin/surfaceflinger
60296067722 | 10265574 | 0 | 3146 | None | 1 | On-time Present | [NULL] | /system/bin/surfaceflinger
60297798913 | 5239227 | 3147 | 3150 | None | 1 | On-time Present | TX - NavigationBar0#0 | com.android.systemui
60307246161 | 10301772 | 0 | 3148 | None | 1 | On-time Present | [NULL] | /system/bin/surfaceflinger
60318497204 | 10281199 | 0 | 3150 | None | 1 | On-time Present | [NULL] | /system/bin/surfaceflinger
60320236468 | 2747559 | 3151 | 3154 | None | 1 | On-time Present | TX - NavigationBar0#0 | com.android.systemui

## TraceConfig

Trace Protos:
[FrameTimelineEvent](/docs/reference/trace-packet-proto.autogen#FrameTimelineEvent)

Datasource:

```protobuf
data_sources {
 config {
 name: "android.surfaceflinger.frametimeline"
 }
}
```
