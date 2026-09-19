# HANDOFF — 会话交接纪要

> 每次月度 agent 会话**开工前必读**；会话结束前**必须更新**本文件。
> 目的：把"本轮的坑与绕法、术语新决策"沉淀下来，避免下次会话重新摸索（教训随会话消失是月度模式最大的隐性成本）。
> 格式：新条目加在最上方，保留历史（太旧的可归档到底部）。

---

## 2026-09-19 会话（P0 工具链落地 + 欠账清零）

### 本轮做了什么
- 两轮上游同步翻译（093d5387→6faa79a3→1a186d13），含新页 memscope / trace-processor-cli
- 落地 P0 工具链：`audit.sh`（全量结构审计）、`proofread.sh`+`glossary.json`（术语/标点/标志 lint）、
  `compare_headings.sh` 重写（快照竞态修复）、`phrases.json`、`prompts/translate-batch.md`、
  workwork.sh fail-closed 断言 + pre-deploy tag + rollback-gh-pages 命令
- 用 audit.sh 清零了全部历史欠账：41 个文件约 80 处链接破损（**高频根因：链接右括号写成全角 `）`**，
  导致 URL 吞掉后续文本）、builtin.md 标题结构、perfetto-manifest.md 表格行

### 关键教训（下次会话必读）
1. **上游英文原文必须用 `git -C ../perfetto show HEAD:<path>` 获取**——
   deploy-local 会把中文 docs/ 拷进上游仓库覆盖英文工作树，直接读工作树会拿到中文
2. **上游站点构建已从 GN+ninja 迁移到 `build.mjs`**（入口 `./infra/perfetto.dev/build`，
   ~4 秒构建）。workwork.sh 已适配（自动探测新旧系统），首页靠 build.mjs 补丁渲染 README.md
3. **上游封闭工具链**：`python3 tools/install-build-deps --ui` 安装 node 22.23.1 + pnpm 10.34.5；
   全量 install-build-deps 会拉 362 个 test_data + android git 仓库，站点构建用不到
4. **终端代理**：系统 Clash 在 `127.0.0.1:7897`，命令行需显式
   `export https_proxy=http://127.0.0.1:7897 http_proxy=...`，否则 android.googlesource.com 等不可达
5. **playwright-cli**：本机无 Chrome，用 `playwright-cli -s=<name> open --browser=chromium <url>`；
   快照路径从 goto 的 stdout 里抓（`[Snapshot](.playwright-cli/page-*.yml)`），不要 ls -t 猜
6. **bash 3.2（macOS）**：没有 mapfile；双引号内 `$var` 紧跟全角字符会被并入变量名解析，
   用 `${var}` 形式
7. **audit.sh 曾有假阳性**：URL 归一化必须在 sort 之前（相对/绝对路径写法排序位置不同）；
   链接 title 部分（`](url "标题")`）允许翻译，比对时要剥掉
8. **builtin.md 的 `#### 描述` 标题后是 NBSP（U+00A0）**——上游如此，结构对齐时注意

### 术语/译法新决策
- 见 `.project/phrases.json`（本轮新增：从命令行合并 trace / Trace 合并 / trace_processor CLI 参考等链接文本约定）
- `Note:`（列表内小写形式）也保留英文，不译为「注意：」

### 已知未了事项
- proofread W1（中英文空格）警告 43 处——历史存量，未阻塞，后续会话顺手清理
- `plan/2026-09-19-ai-automation-roadmap.md` 第十三节：运行模式定为"人 + agent 月度"，
  agentic CI 方案保留备查，重启条件见该节

### 下次会话快速启动
```bash
export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897
bash .project/workwork.sh sync-check          # 1. 检查上游更新
bash .project/audit.sh                        # 2. 全量审计（应 0 差异，否则先修欠账）
# 3. 翻译：按 .project/prompts/translate-batch.md 模板派发子代理批次
# 4. 完成后：audit + proofread 全绿 → deploy-local 浏览器抽查 → 提交推送 → sync-update → deploy-gh-pages
# 5. 收尾：更新本文件（HANDOFF.md）
```
