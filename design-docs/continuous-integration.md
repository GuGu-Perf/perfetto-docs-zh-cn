# Perfetto CI

此 CI 在 Android 的 TreeHugger 之上使用（而不是替代它）。它提供早期测试信号以及对 TreeHugger 不支持的其他操作系统和较旧 Android 设备的覆盖。

有关项目测试策略的更多详细信息，请参阅 [Testing](/docs/contributing/testing.md) 页面。

CI 基于 GitHub actions。入口点是 [.github/workflows/analyze.yml](/.github/workflows/analyze.yml)。

analyze 步骤根据更改的文件触发其他工作流（UI、linux 测试等）。

## GCE 中的自托管 runners

我们使用在 GitHub 项目中注册的自托管 runners。

托管它们的 Google Cloud 项目称为 `perfetto-ci`

源代码位于 [infra/ci](/infra/ci)

## Worker GCE VM

我们有可变数量的 GCE vms（参见 config.py 中的 `GCE_VM_TYPE`），由自动缩放器驱动，最多可达 `MAX_VMS_PER_REGION`。

每个 GCE vm 运行固定数量（`NUM_WORKERS_PER_VM`）的 `sandbox` 容器。

每个 sandbox 容器运行一个 GitHub Action Runner 实例。

构建和测试在 Action Runner 中进行。

除此之外，每个 GCE vm 运行一个名为 `worker` 的特权 Docker 容器。worker 处理 VM 的基本设置，除了通过 supervisord 确保始终有 N 个 sandbox 运行之外什么都不做。

整个系统镜像只读。VM 本身是无状态的。除了 Google Cloud Storage（仅用于 UI 工件）和 GitHub 的缓存之外，没有状态持久化。SSD 仅用作交换的临时磁盘 - 以使用大的 tmpfs - 并在每次重启时清除。

VM 使用 Google Cloud Autoscaler 动态生成，并使用由 ci.perfetto.dev AppEngine 推送的 Stackdriver 自定义 metrics 作为成本函数。此类 metrics 是排队的 + 运行的 pull-requests 的数量。

GCE vm 和特权 docker 容器使用服务账户 `gce-ci-worker@perfetto-ci.iam.gserviceaccount.com` 运行。

sandbox 使用受限的服务账户 `gce-ci-sandbox@perfetto-ci.iam.gserviceaccount.com` 运行，该账户仅被允许在 gs://perfetto-ci-artifacts 中创建 - 但不能删除或覆盖 - 工件。

# 序列图

这是在 worker 实例上从引导到测试运行依次发生的事情。

```bash
make -C /infra/ci worker-start
┗━ gcloud start ...

[GCE] # From /infra/ci/worker/gce-startup-script.sh
docker run worker ...

[worker] # From /infra/ci/worker/Dockerfile
┗━ /infra/ci/worker/worker_entrypoint.sh
 ┗━ supervisord
 ┗━ [N] /infra/ci/worker/sandbox_runner.py
 ┗━ docker run sandbox-N ...

[sandbox-X] # From /infra/ci/sandbox/Dockerfile
┗━ /infra/ci/sandbox/sandbox_entrypoint.sh
 ┗━ github-action-runner/run.sh
 ┗━ .github/workflows/analyze.yml
 ┣━ .github/workflows/linux-tests.yml
 ┣━ .github/workflows/ui-tests.yml
 ...
 ┗━ .github/workflows/android-tests.yml
```

## 操作手册

### Frontend (JS/HTML/CSS/py) 更改

本地测试：`make -C infra/ci/frontend test`

使用 `make -C infra/ci/frontend deploy` 部署

### Worker/Sandbox 更改

1. 使用以下命令构建并推送新的 docker 容器：

 `make -C infra/ci build push`

2. 重新启动 GCE 实例，手动或通过：

 `make -C infra/ci restart-workers`

## 安全考虑

- gs://perfetto-artifacts GCS bucket 可被 GAE 和 GCE 服务账户读取和写入。

- 总体而言，此项目中的任何账户都没有任何有趣的权限：
  - worker 和 sandbox 服务账户在 CI 项目本身之外没有任何特殊功能。即使被破坏，它们也不允许执行任何无法通过旋转自己的 Google Cloud 项目来完成的操作。

- 此 CI 仅处理功能和性能测试，不处理任何类型的持续部署。

- GitHub actions 仅对 perfetto-team 和 perfetto-contributors 自动触发。

- Sandboxes 不太难逃脱（Docker 是唯一的边界）。

- 因此，pre-submit 和 post-submit 构建工件都不被认为是可信的。它们仅用于建立功能正确性和性能回归测试。

- CI 构建的二进制文件不会在 CI 项目之外的任何其他机器上运行。它们故意不推送到 GCS。

- 唯一保留（最多 30 天）并上传到 GCS bucket 的构建工件是 UI 工件。这仅仅是为了获取 HTML 更改的视觉预览。

- UI 工件从与生产 UI 不同的来源（GCS per-bucket API）提供服务。
