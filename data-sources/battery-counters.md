# 电源数据源

在 Android 上，Perfetto 捆绑数据源以从设备电源管理单元检索电源 Counters（在支持的地方）。

## 电池 Counter

_此数据源已在 Android 10 （Q） 中引入，并且需要设备上存在电源管理硬件。这在大多数 Google Pixel 智能手机上可用。_

现代智能手机配备有电源监控 IC，能够测量进出电池的充电量。这允许 Perfetto 观察整个设备（SoC、显示器、无线电和所有其他硬件单元的联合）从电池消耗的总和瞬时充电量。

简化的框图：

![](/docs/images/battery-counters.png "电池 Counter 的示意图")

这些 Counter 报告：

- 剩余电池容量（%）。
- 剩余电池充电量（微安时，µAh）。
- 瞬时（通常是小时间窗口的平均值）电流（微安，µA）

这些 Counter的存在和分辨率取决于设备制造商。在平台级别，此数据是通过轮询 Android [IHealth HAL][health-hal] 获得的。有关硬件规格和分辨率的更多详细信息，请参见[测量设备电源](https://source.android.com/devices/tech/power/device)。

[health-hal]: https://cs.android.com/android/platform/superproject/main/+/main:hardware/interfaces/health/2.0/IHealth.hal?q=IHealth

#### 在 USB 上插电时测量充电量

电池 Counter 测量进出电池的充电量。如果设备插入 USB 电缆，你可能会观察到正瞬时电流和总充电量的增加，表示充电量流入电池（即为其充电）而不是流出。

这可能会使实验室环境中的测量变得有问题。已知的解决方法是：

- 使用允许从主机端电气断开 USB 端口的专用 USB 集线器。这允许在测试运行时有效地断开手机连接。

- 在已 root 的手机上，电源管理 IC 驱动程序允许断开 USB 充电，同时保持 USB 数据链路处于活动状态。此功能是 SoC 特定的，未记录，并且未通过任何 HAL 公开。例如，在 Pixel 2 上，这可以通过以 root 身份运行来实现：
 `echo 1 > /sys/devices/soc/800f000.qcom,spmi/spmi-0/spmi0-02/800f000.qcom,spmi:qcom,pmi8998@2:qcom,qpnp-smb2/power_supply/battery/input_suspend`。
 请注意，在大多数设备上，内核 USB 驱动程序保持唤醒锁以保持 USB 数据链路处于活动状态，因此即使关闭屏幕，设备也永远不会完全挂起。

### UI

![](/docs/images/battery-counters-ui.png)

### SQL

```sql
select ts, t.name, value from counter as c left join counter_track t on c.track_id = t.id
```

ts | name | value
---|------|------
338297039804951 | batt.charge_uah | 2085000
338297039804951 | batt.capacity_pct | 75
338297039804951 | batt.current_ua | -1469687
338297145212097 | batt.charge_uah | 2085000
338297145212097 | batt.capacity_pct | 75
338297145212097 | batt.current_ua | -1434062

### TraceConfig

Trace proto:
[BatteryCounters](/docs/reference/trace-packet-proto.autogen#BatteryCounters)

Config proto:
[AndroidPowerConfig](/docs/reference/trace-config-proto.autogen#AndroidPowerConfig)

示例配置（Android）:

```protobuf
data_sources: {
 config {
 name: "android.power"
 android_power_config {
 battery_poll_ms: 250
 battery_counters: BATTERY_COUNTER_CAPACITY_PERCENT
 battery_counters: BATTERY_COUNTER_CHARGE
 battery_counters: BATTERY_COUNTER_CURRENT
 battery_counters: BATTERY_COUNTER_VOLTAGE
 }
 }
}
```

示例配置（Chrome OS 或 Linux）:

```protobuf
data_sources: {
 config {
 name: "linux.sysfs_power"
 }
}
```

## {#odpm} 设备内电源轨监控器（ODPM）

_此数据源已在 Android 10 （Q） 中引入，并且需要设备上的专用硬件。此硬件在大多数生产手机上尚不可用。_

Android 的最新版本引入了对硬件子系统级别更高级电源监控的支持，称为"设备内电源轨监控器"（ODPM）。这些 Counter 测量（硬件单元组的）功耗。

与电池 Counter 不同，它们不受电池充电/放电状态的影响，因为它们测量电池下游的电源。

电源轨 Counters 的存在和分辨率取决于设备制造商。在平台级别，此数据是通过轮询 Android [IPowerStats HAL][power-hal] 获得的。

Google 员工：有关如何更改 Pixel 设备上的默认轨选择的说明，请参见 [go/power-rails-internal-doc](http://go/power-rails-internal-doc)。

[power-hal]: https://cs.android.com/android/platform/superproject/main/+/main:hardware/interfaces/power/stats/1.0/IPowerStats.hal

简化的框图：

![](/docs/images/power-rails.png "ODPM 的框图")

### TraceConfig

Trace proto:
[PowerRails](/docs/reference/trace-packet-proto.autogen#PowerRails)

Config proto:
[AndroidPowerConfig](/docs/reference/trace-config-proto.autogen#AndroidPowerConfig)

示例配置：

```protobuf
data_sources: {
 config {
 name: "android.power"
 android_power_config {
 battery_poll_ms: 250
 collect_power_rails: true
 # 注意:可以在此部分中同时指定轨和电池 Counter。
 }
 }
}
```

## 相关数据源

另请参见 [CPU -> 频率缩放](cpu-freq.md) 数据源。
