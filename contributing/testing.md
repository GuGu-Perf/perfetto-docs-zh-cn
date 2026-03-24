# 测试

由于构建配置和嵌入目标的广泛多样性，Perfetto 的测试策略相当复杂。

常见测试目标(所有平台/检出):

`perfetto_unittests`: 
与平台无关的单元测试。

`perfetto_integrationtests`: 
端到端测试，涉及基于 protobuf 的 IPC 传输和 ftrace
集成（仅限 Linux/Android）。

`perfetto_benchmarks`: 
基准测试跟踪以下性能：(i) trace 写入，(ii) trace 回读
以及 (iii) ftrace 原始管道 -> protobuf 翻译。

## 运行测试

### 在 Linux / MacOS 上

```bash
tools/ninja -C out/default perfetto_{unittests,integrationtests,benchmarks}
out/default/perfetto_unittests --gtest_help
```

`perfetto_integrationtests` 要求在 Linux 上当前用户可以
读取/写入 ftrace debugfs 目录：

```bash
sudo chown -R $USER /sys/kernel/debug/tracing
```

### 在 Android 上

1. 通过 `adb` 连接设备
2. 启动内置模拟器(支持 Linux 和 MacOS):

```bash
tools/install-build-deps --android
tools/run_android_emulator &
```

3. 运行测试(在模拟器或物理设备上):

```bash
tools/run_android_test out/default perfetto_unittests
```

## 持续测试

Perfetto 在各种位置进行测试：

**Perfetto CI**： https://ci.perfetto.dev/ 
从独立检出构建和运行 perfetto\_{unittests,integrationtests,benchmarks}。
基准测试以简化形式运行以进行冒烟测试。
有关更多详细信息，请参阅 [此文档](/docs/design-docs/continuous-integration.md)。

**Android CI**(参见 go/apct 和 go/apct-guide): 
仅运行 `perfetto_integrationtests`

**Android 预提交(TreeHugger)** ： 
在提交每个 `external/perfetto` 的 AOSP CL 之前运行。

**Android CTS**(用于确保 API 兼容性的 Android 测试套件): 
内部滚动运行。

请注意，Perfetto CI 使用独立构建系统，其他构建为
Android 树的一部分。

## 单元测试

Perfetto 中大多数代码在类级别都存在单元测试。它们
确保每个类大致按预期工作。

单元测试目前在 ci.perfetto.dev 和 build.chromium.org 上运行。
在 APCT 和 Treehugger 上运行单元测试正在进行中。

## 集成测试

集成测试确保子系统(特别是 ftrace 和 IPC 层)
和 Perfetto 作为整体在端到端方面正确工作。

集成测试可以在两种配置中运行：

**1. 生产模式**(仅限 Android) 
此模式假设 tracing 服务（`traced`）和 OS 探测
服务（`traced_probes`）都已运行。在此模式下，测试仅启用
消费者端点并测试与生产
服务的交互。这是我们的 Android CTS 和 APCT 测试的工作方式。

**2. 独立模式**： 
在测试本身中启动守护程序，然后针对它们进行测试。
这是独立构建的测试方式。这是在 Linux 和 MacOS 上
运行集成测试的唯一受支持的方式。

## Trace Processor 差异测试

Trace processor 主要使用所谓的"差异测试"进行测试。

对于这些测试，trace processor 解析已知的 trace 并执行查询
字符串或文件。然后比较这些查询的输出（即"差异"）与
预期输出文件，并突出显示差异。

编写 metric 时也有类似的差异测试 - 不使用查询，
而是使用 metric 名称，预期输出字符串包含
计算 metric 的预期结果。

这些测试（对于查询和 metric）可以运行如下：

```bash
tools/ninja -C <out directory>
tools/diff_test_trace_processor.py <out directory>/trace_processor_shell
```

TIP: 查询差异测试预期只有单个查询，该查询在整个文件中产生输出（通常在末尾）。
调用 `SELECT RUN_METRIC('metric file')` 可能会混淆此检查，因为此查询会生成一些隐藏输出。
为了解决此问题，如果查询只有名为 `suppress_query_output` 的列，即使它有输出，也将被忽略(例如，
`SELECT RUN_METRIC('metric file') as suppress_query_output`)

## UI 像素差异测试

像素测试用于确保核心用户旅程正常工作，方法是验证它们
与黄金屏幕截图逐像素相同。它们使用无头
chrome 加载网页并截图，然后逐像素比较
黄金屏幕截图。你可以使用 `ui/run-integrationtests` 运行这些测试。

当一定数量的像素不同时，这些测试会失败。如果这些
测试失败，你需要调查差异并确定其是否有意。如果
这是所需的更改，你需要在 linux 机器上更新屏幕截图
以使 CI 通过。你可以通过生成和上传新的基线来更新它们（这需要通过 gcloud 访问 google 存储桶，只有 googlers 可以访问，googlers 可以 [在此](https://g3doc.corp.google.com/cloud/sdk/g3doc/index.md#installing-and-using-the-cloud-sdk）安装 gcloud)。

默认情况下，测试在 docker 容器中运行，除非传递 `-no-docker`。
建议使用容器以获得稳定和可重现的
测试环境，特别是对于重新设置基线，否则非常可能
在 CI 上运行时屏幕截图不匹配。

```
ui/run-integrationtests --rebaseline
tools/test_data upload
```

完成后，你可以提交并上传作为 CL 的一部分，导致 CI 使用你的新屏幕截图。

注意：如果你看到失败的差异测试，你可以通过使用以 `ui-test-artifacts/index.html` 结尾的链接在 CI 上查看像素差异。该页面上报告包含已更改的屏幕截图以及接受更改的命令（如果这些更改是需要的）。

## Android CTS 测试

CTS 测试确保任何修改 Android 的供应商保持与平台 API 的合规性。

这些测试包括上述集成测试的子集，并添加了更多复杂的测试，确保平台（例如 Android 应用程序等）和 Perfetto 之间的交互没有被破坏。

相关的目标是 `CtsPerfettoProducerApp` 和 `CtsPerfettoTestCases`。一旦这些构建完成，应运行以下命令：

```bash
adb push $ANDROID_HOST_OUT/cts/android-cts/testcases/CtsPerfettoTestCases64 /data/local/tmp/
adb install -r $ANDROID_HOST_OUT/cts/android-cts/testcases/CtsPerfettoProducerApp.apk
```

接下来，应在设备上运行名为 `android.perfetto.producer` 的应用程序。

最后，应运行以下命令：

```bash
adb shell /data/local/tmp/CtsPerfettoTestCases64
```

## {#chromium} Chromium waterfall

Perfetto 通过 [此自动滚轮](https://autoroll.skia.org/r/perfetto-chromium-autoroll) 不断滚入 chromium 的 //third_party/perfetto。

[Chromium CI](https://build.chromium.org) 运行 `perfetto_unittests` 目标，如 [buildbot 配置][chromium_buildbot] 中定义的。

你也可以在提交之前针对 Chromium 的 CI / TryBots 测试待定的 Perfetto CL。当你进行更棘手的 API 更改或测试 Perfetto CI 未涵盖的平台（例如 Windows、MacOS）时，这可能很有用，允许你在提交之前验证补丁（然后它最终会自动滚入 Chromium）。

为此，首先确保你已上传拉取请求到 GitHub。
接下来，创建一个新的 Chromium CL 来修改 Chromium 的 `//src/DEPS` 文件。

如果你最近上传了更改，修改 `src/third_party/perfetto` 的 `DEPS` 条目中的 git commit hash 可能就足够了：

```
  'src/third_party/perfetto':
    Var('chromium_git') + '/external/github.com/google/perfetto/' + '@' + '8fe19f55468ee227e99c1a682bd8c0e8f7e5bcdb',
```

将 git hash 替换为你最新补丁集的 commit hash。

或者，你可以添加 `hooks` 来在 Chromium 当前的 third_party/perfetto 修订版之上修补待定的 CL。为此，将以下条目添加到 Chromium 的 `//src/DEPS` 文件中的 `hooks` 数组，将 `refs/pull/XXXX/head` 修改为适合你的拉取请求的值。

```
  {
    'name': 'fetch_custom_patch',
    'pattern': '.',
    'action': [ 'git', '-C', 'src/third_party/perfetto/',
                'fetch', 'https://github.com/google/perfetto.git',
                'refs/pull/XXXX/head',
    ],
  },
  {
    'name': 'apply_custom_patch',
    'pattern': '.',
    'action': ['git', '-C', 'src/third_party/perfetto/',
               '-c', 'user.name=Custom Patch', '-c', 'user.email=custompatch@example.com',
               'cherry-pick', 'FETCH_HEAD',
    ],
  },
```

如果你想针对 Chrome 的 SDK 构建测试你的更改，你可以将 `Cq-Include-Trybots:` 行添加到 gerrit 中的更改描述中以用于 perfetto SDK trybots（一旦 Chrome 迁移到 SDK 完成，这将不再需要，请参阅 [跟踪 bug][sdk_migration_bug]）：

```
Cq-Include-Trybots: luci.chromium.try:linux-perfetto-rel
Cq-Include-Trybots: luci.chromium.try:android-perfetto-rel
Cq-Include-Trybots: luci.chromium.try:mac-perfetto-rel
Cq-Include-Trybots: luci.chromium.try:win-perfetto-rel
```

[chromium_buildbot]: https://cs.chromium.org/search/?q=perfetto_.*tests+f:%5Esrc/testing.*json$&sq=package:chromium&type=cs
[chromium_cl]: https://chromium-review.googlesource.com/c/chromium/src/+/2030528
[sdk_migration_bug]: https://crbug.com/1006541

