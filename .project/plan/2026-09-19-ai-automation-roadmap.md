# AI 自动化优化路线图

> 日期：2026-09-19
> 背景：三轮完整翻译工作流（`093d5387..6faa79a3`、`6faa79a3..1a186d13` 等）之后的复盘讨论，
> 结合业界实践检索，评估本项目（AI 辅助的 Perfetto 文档中文翻译）的自动化优化空间。

## 一、当前工作流（As-Is）

以 `.project/ai-skill.md` 为规范，每轮人工（AI 会话）驱动：

```
1. sync-check        # 检测上游 perfetto/docs 更新（对比 LAST_SYNC）
2. 人工阅读 diff     # 每轮约 2000~5000 行，按文件拆批次
3. 派发 AI 翻译      # 并行子代理，逐文件对照 diff 应用译文
4. 结构校验          # 标题数/围栏数 vs 上游（仅变更文件）+ 补历史欠账
5. deploy-local      # 本地构建（上游 build.mjs）+ 浏览器逐页对比官网
6. 提交推送 main     # translate: sync upstream docs update (a..b)
7. sync-update       # 更新 LAST_SYNC
8. deploy-gh-pages   # 构建产物修补路径后强推 gh-pages 分支
9. 线上验证          # 浏览器抽查线上页面 vs perfetto.dev
```

关键事实：
- 仓库无任何 GitHub Actions workflow（`.github/` 仅有 CODEOWNERS）
- 上游已把站点构建从 GN+ninja 迁移到 `build.mjs`（约 4 秒完成全量构建），
  `workwork.sh` 已适配并含首页补丁（`/` 用 `docs/README.md` 渲染）
- 术语表存在于 `TRANSLATION_GUIDE.md`，但是 Markdown 表格，机器不可直接执行

### 关于 proofread.sh 的澄清（2026-09-19 考古结论）

`TRANSLATION_GUIDE.md` 第 227 行仍引用 `bash .project/proofread.sh --file ...`，
**该脚本从未存在于 git 历史中**（`git log --all -- .project/proofread.sh` 无记录）：
- 2026-04-12 `5893898`（规范从 666 行精简重写为 87 行）时被写入规范，是一个"承诺"而非实现
- 2026-04-19 `4899298`（合并统一工具脚本）清理旧脚本引用时漏删了这一条
- 每轮翻译子代理都会报告"脚本不存在"，属残留引用，非遗弃脚本

## 二、观察到的真实痛点（近三轮实证）

| # | 痛点 | 证据 | 根因 |
|---|------|------|------|
| 1 | 历史欠账反复出现 | 第 1 轮补 4 文件、第 2 轮补 8 文件（如 commands-automation-reference 多 7 个旧章节） | 只翻译本轮 diff 涉及文件，从不全量审计，漂移在未变更文件中累积 |
| 2 | 规范与工具脱节 | 规范引用的 proofread.sh 不存在 | 术语表机器不可读，校验承诺未落地 |
| 3 | 浏览器校验脆弱、全手工 | compare_headings.sh 误报（README=0、protozero 17/16）、快照文件混淆 | 快照竞态 + 依赖本地 playwright 会话 |
| 4 | 上游接口变化无预警 | GN+ninja→build.mjs 迁移打断 workwork.sh，引发首页回退线上事故 | 无构建冒烟测试守门 |
| 5 | 编排只存在于会话经验 | 每轮需人工读 diff、拆批次、派发、汇总、部署 | 编排逻辑未沉淀为可定时执行的脚本 |

## 三、业界实践要点（检索结论）

- **GitHub Actions + LLM 翻译**已成熟：AI Translate Action、微软 Co-op Translator
  （markdown + 图片文字）、Lingo.dev（GitHub App，push/PR 即翻译）；
  LocalHero 总结了 DIY / OpenAI API / 自托管三路线
- **定时 fork 同步**：Fork-Sync-With-Upstream / repo-sync 等 action 用 cron 自动追上游；
  注意 GitHub 限制——仓库 60 天无提交会自动禁用 scheduled workflow，需 keepalive
- **TMS（Crowdin/Transifex）三件套**值得移植：术语表（glossary）、翻译记忆（TM）、
  机器预翻译 + 人工审核分层；CI 采用分层校验（便宜的通用检查先跑，贵的语义检查后跑）
- **LLM 做 review**：CI 中用 LLM 审查翻译质量并留 inline comment 是常见实践
- TMS 平台本身不适合本项目（上游是他人仓库、纯 markdown、无 string key），
  但理念可以低成本自研移植

## 四、优化路线图

### P0 —— 本地质量门禁自动化（无 API 依赖，立即收益）

| 项 | 内容 | 解决的痛点 |
|----|------|-----------|
| P0-1 | `audit.sh`：全量（127 文件）结构审计——标题数/围栏数/表格数/图片数/链接数 vs 上游，输出欠账清单 | #1 历史欠账 |
| P0-2 | 补齐 `proofread.sh` + 术语表机器可读化（`glossary.json`）：该译未译/不该译被译、`NOTE:` 被汉化、半角句号、中英文空格、代码块外 URL 改动 | #2 |
| P0-3 | 修 compare_headings.sh 快照竞态（按 session + 时间窗锁定快照）；清理规范中的幽灵引用 | #3 |

### P1 —— CI 化（GitHub Actions，半自动：AI 出 PR、人审合并）

> 2026-09-19 补充：结合"翻译仓库每次要下载/编译上游源仓库是否合适"的评审，
> 详细可行性结论与坑见第五节。P1 按**分层设计**修订：
> 轻量 job（sparse checkout 仅 docs/，无构建）+ 重量 job（仅部署时浅克隆全树）。

| 项 | 内容 | 依赖/风险 |
|----|------|----------|
| P1-1 | 定时 workflow（cron 每日）：sparse checkout 上游 docs/ → sync-check → 有更新则触发翻译 job（LLM API，产出 PR） | API key 进 Secrets；60 天保活 |
| P1-2 | PR 质量门禁（必跑、无 LLM、无上游构建）：audit + proofread + 站内链接检查（对上游 docs/ sparse checkout 做结构比对即可） | 无 |
| P1-3 | 部署自动化（仅 main merge 触发）：浅克隆上游全树 + 官方 hermetic 工具链 + build.mjs 构建 + sed 路径修补 + `actions/deploy-pages` | Pages 权限；concurrency 防并发 |

### P2 —— 质量增强（P1 稳定后）

| 项 | 内容 |
|----|------|
| P2-1 | 翻译记忆（TM）：从已翻译文件构建中英句对库，翻译时作 few-shot 注入，防术语/句式漂移 |
| P2-2 | AI review bot：PR 上 LLM 对 diff 做术语/流畅度审查，留 inline comment |
| P2-3 | PR 预览：构建产物上传 artifact，审核者直接看渲染效果 |
| P2-4 | 欠账看板：audit 结果持久化 JSON，输出 badge/页面 |

### 边界与决策点

- **不建议全自动合并**：术语是软约束，lint 只能查硬规则。
  分级策略——纯链接/命令替换类小 diff 可自动合并，正文翻译保留人审
- **成本**：每轮 ~1500 行 diff 的 LLM 翻译成本可控，按文件分批并行已验证
- **待决策**：
  1. P1-1 用哪家 LLM API（key 进 GitHub Secrets）
  2. 是否允许小改动自动合并，还是全部人审
  3. cron 频率（每日 / 每周）

## 五、CI 可行性评估：翻译仓库要下载/编译上游源仓库，GitHub Actions 合适吗？

**结论：合适，但必须分层。** 关键前提：上游已迁移到 `build.mjs`，
站点构建**不再编译任何 C++**（GN+ninja 已废除），只做 markdown 渲染 + JS/Python 生成器。
实测体量：上游 `.git` 125MB、`docs/` 53MB（图片为主）、`protos/` 4MB、
stdlib SQL 2MB、hermetic node 187MB、node_modules 171MB、站点产物 81MB。
公共仓库 Linux runner 免费不限时，磁盘 ~14GB 充裕。

分层设计（避免"每次全量下载编译"）：

| 层 | 触发 | 上游获取方式 | 耗时量级 |
|----|------|--------------|----------|
| L0 检测 | cron 每日 | `git clone --filter=blob:none --sparse` 仅 docs/（<10MB） | 秒级 |
| L1 门禁 | 每个 PR | 同上（结构/术语比对只需要 docs/） | 分钟级 |
| L2 翻译 | L0 发现有更新 | 同上 + LLM API | 分钟~小时级，按文件分批 |
| L3 部署 | main merge | 浅克隆全树（--depth 1，~200MB）+ hermetic node/pnpm（官方产物，校验 sha256）+ build.mjs（~10s） | 5-10 分钟 |

sync-check 需要 `LAST_SYNC..HEAD` 的 diff：浅克隆下先
`git fetch --depth=1 origin <LAST_SYNC_sha>` 再两点 tree-diff 即可（不需要完整历史），
或直接用 GitHub compare API。

### 已识别的坑（按严重度）

1. **GITHUB_TOKEN 不触发后续 workflow**：用内置 token 创建的 PR 不会触发该 PR 的
   CI 检查（GitHub 防递归机制）。→ 翻译 job 开 PR 必须用 PAT 或 GitHub App token。
2. **dead-link 硬失败**：`render.mjs` 的 `assertNoDeadLink` 遇死链直接 throw——
   上游文件改名会令中文文档指向它的链接变死链，部署 job 挂。当门禁是优点，
   但要有"上游重构 → 先修链再部署"的预期（本轮 `traceconv` 大改名就是实例）。
3. **sed 可移植性**：workwork.sh 的部署路径修补用 macOS 语法 `sed -i ''`，
   Linux runner 下报错。→ CI 版用 GNU sed 语法或改 python。
   （官方 `deploy-pages` 不能省掉 sed：build.mjs 按根路径 perfetto.dev 生成链接，
   仓库子路径部署仍需修补。）
4. **cron 60 天休眠**：上游无更新的月份仓库无提交，scheduled workflow 被自动禁用。
   → keepalive（每月空 commit 或调 re-enable API）。
5. **缓存设计**：actions/cache 上限 10GB/仓库、LRU 驱逐；key 必须绑定上游 HEAD
   否则陈旧。第一版建议不缓存 hermetic 工具链（增量下载 ~50MB/次可接受），
   规避"缓存失效逻辑写错 → 用旧上游构建"的隐性错误。
6. **install-build-deps 不能全跑**：官方全量脚本会拉 362 个 test_data 文件 +
   android.googlesource.com 一堆 git 仓库（本地实测），站点构建完全不需要。
   → 只取官方 UI_DEPS 清单中的 node+pnpm 两个产物（带 sha256 校验），仍是官方 hermetic 方式。
7. **LLM job 的坑**：fork 来源 PR 不注入 secrets（我们自开 PR 无此问题，但须知）；
   6h job 上限 → 大批量翻译要分文件批处理 + 可重入；重跑结果不确定 → 翻译 PR 必须人审；
   API 成本随 diff 波动。
8. **并发竞争**：两次部署同时跑会互相覆盖。→ `concurrency: group: deploy`。
9. **生成参考页是英文**：protos/stats/stdlib 参考页由上游源码即时生成（英文），
   本地构建现状亦如此，非 CI 引入；audit 也无法覆盖这些页面。
10. **blog 依赖**：build.mjs 需要 `//blog` 目录（孤儿分支），缺失时静默跳过不失败——
    CI 无需处理，但要知道线上没有博客是正常现象。

### 与"完全按 Perfetto 官方方式"原则的兼容性

CI 仍用官方封闭工具链（node/pnpm 官方产物 + sha256 校验 + build.mjs），
只是**跳过与站点无关的官方依赖**（test_data、android git 仓库）和**用浅克隆
替代全量 clone**。构建逻辑本身零魔改——上游再迁移构建系统时，CI 冒烟会在
merge 前失败并提示，而不是像本轮一样在部署时才发现。

## 六、目标架构与各阶段设计理由（2026-09-19 综合评估结论）

```
                        ┌────────────────────────────────┐
                        │  数据资产层（单一事实来源）        │
                        │  glossary.json │ TM 翻译记忆      │
                        │  TRANSLATION_GUIDE.md │ audit 基线 │
                        └───────┬───────────────┬────────┘
                                │ 喂给 lint      │ 喂给 LLM prompt
  google/perfetto               ▼               ▼
       │                 ┌────────────┐  ┌────────────┐
       │  L0 检测(每日)   │  L1 门禁    │  │  L2 翻译    │
       └────────────────►│ (每个PR)    │  │ (有更新时)  │
         sparse docs/    │  无LLM      │◄─┤  LLM API   │
                         └─────┬──────┘  └─────┬──────┘
                               │ 通过           │ 产出 PR(PAT)
                               ▼               ▼
                         ┌─────────────────────────┐
                         │  人：审 PR / 定术语 / 兜底  │
                         └────────────┬────────────┘
                                      │ merge main
                                      ▼
                         ┌─────────────────────────┐
                         │  L3 部署(merge触发)        │
                         │  浅克隆+官方工具链+build.mjs │
                         │  +deploy-pages(原子发布)   │
                         └─────────────────────────┘
```

| 层 | 设计 | 为什么这样设计 |
|----|------|----------------|
| L0 检测 | cron 每日，sparse checkout 仅 docs/（<10MB），秒级 | 检测只需 docs/ 树；上游不可挂 webhook 只能定时拉；日粒度匹配人工审阅节奏；keepalive 对冲 60 天休眠 |
| L1 门禁 | 每个 PR，纯确定性检查（audit 全量 127 文件 + glossary lint + 链接检查），无 LLM 无构建；构建冒烟仅 paths 过滤触发（workflow/workwork.sh 变更时） | 门禁必须可复现可信免费；全量审计消灭漂移欠账（两轮返工根因）；glossary.json 一份数据喂 lint 和 prompt 两处；重检查按需触发，普通翻译 PR 不付构建成本，但上游构建迁移事故在 merge 前暴露 |
| L2 翻译 | L0 触发，LLM API 按文件分批并行 + 翻译后自审计重试 + PAT 开 PR | 分批规避 token/6h 限制且可重入；LLM 不确定 → 人审兜底 + GITHUB_TOKEN 限制天然要求 PAT/PR 形态；机械检查先拦 LLM 结构错误省人审精力；小 diff 自动合并把人力留给判断力环节 |
| L3 部署 | merge 触发，浅克隆全树 + 官方 node/pnpm 产物（sha256）+ 首页补丁 + build.mjs + sed 路径修补 + deploy-pages + concurrency 组 | 只取两个官方产物即保持 hermetic 零魔改，又跳过 362 个 test_data/android 仓库；deploy-pages 原子可审计无本地凭据；dead-link 硬失败是发布前最后一道闸 |
| 人 | 审 PR、定术语、处理硬失败、维护 glossary/规范 | 术语是软约束无法机械化；LLM 重跑结果不同必须人审；规范维护是 lint 和 prompt 的共同源头 |

**演进顺序的理由**：P0 先行（零决策依赖、立刻去返工，且脚本本地/CI 两处复用不返工）
→ P1 骨架（把编排从会话经验变成仓库资产，保留人审积累信任）
→ P2 增强（TM/review bot 只有在大流量经过 CI 后才有意义）。

## 七、发布管控：审批发布与一键回退（2026-09-19 补充）

利用 GitHub 原生机制补齐 L3 部署层的"人工放行 + 回退"：

| 需求 | 机制 | 说明 |
|------|------|------|
| 人看完点按钮发布 | **Environments + Required Reviewers** | deploy job 声明 `environment: production`，CI 到此暂停显示 "Waiting for review"，审批人在 Actions UI 点 Review deployments → Approve/Reject；附部署历史与 URL 时间线 |
| test 路径预览 | 见下表三选一 | GitHub Pages 每仓库单站点、Actions 部署整体替换，原生无多槽位 preview |
| 回退按钮 | **workflow_dispatch 手动工作流** | 带输入参数（目标 SHA）的手动触发；源码在 git、构建 ~10s，按旧 SHA 重建重发 = 确定性回退；回退 job 也挂 `environment: production` 防误触 |

预览方案取舍：

| 方案 | 做法 | 代价 | 建议 |
|------|------|------|------|
| A | 不做在线预览：PR 审 markdown diff + CI 附 audit 报告 artifact | 无 | **起步推荐**——翻译 review 本质是审文本，渲染问题由 audit 兜底 |
| B | gh-pages 分支子路径 `/preview/pr-N/` | 放弃 deploy-pages 原子性，回到强推模式 | 需要预览且不想引第三方时 |
| C | Cloudflare Pages/Netlify 按 PR 自动预览域名 | 外部依赖 | 业界文档站标准做法，预览需求强烈时 |

修订后的发布链：L2 翻译 PR（人审内容）→ merge → L3 构建（门禁含 dead-link）→
**production environment 审批放行** → 上线；异常时 rollback 工作流按 SHA 重建回退。
人与 CI 的交接面全部显式化为按钮，不依赖任何人记得本地脚本。

## 八、上游架构变动的防护设计（fail-closed 原则，2026-09-19 补充）

原则：不防止上游变动，而是让变动在**发布前响亮失败**（fail-closed），
绝不**发布后静默出错**（fail-open）。本轮两次事故分别验证了两条路径：
build.mjs 迁移打断 workwork.sh（fail-closed，安全）与首页补丁失效致英文页上线（fail-open，危险）。

上游耦合面清单与表现：

| 耦合点 | 变动表现 | 设计 |
|--------|---------|------|
| git/diff 逻辑 | ≈永不 | 安全 |
| markdown 结构（audit） | 高频，报差异 | 安全，属常态工作 |
| 构建入口 `./infra/perfetto.dev/build` | 命令不存在，构建失败 | fail-closed，安全 |
| 首页补丁（pattern 替换 build.mjs） | `PATTERN-NOT-FOUND` 退出 1 | fail-closed，安全 |
| sed 路径修补 | 模板变更时**静默无效 → 坏链上线** | 危险，需按下文加断言 |
| 工具链版本（node/pnpm） | 上游升 lockfile，旧 pnpm 安装失败 | 半安全，需按下文派生版本 |

防护措施：

1. **契约收敛 + fail-closed 改写**：所有上游耦合收敛进一个 adapter 层；sed 修补后
   必须断言产物（`grep 'href="/perfetto-docs-zh-cn/assets/style.css' index.html'`、
   首页含"什么是 Perfetto"），失败即退出——本轮线上事故的疫苗。
2. **工具链版本从上游派生**：CI 运行时解析上游 `tools/install-build-deps` 清单获取
   node/pnpm 版本与 sha256，不在 workflow 硬编码——上游升级自动跟随。
3. **契约活性检查**：每周例行构建冒烟（全量克隆+构建+首页断言，~10min），
   上游构建系统迁移 7 天内暴露；workflow/adapter 自身变更时强制跑同样冒烟。
4. **LLM 第二嵌入点——break-fix**：契约检查失败时开诊断 job，把失败日志+上游 diff
   喂 LLM 生成修复建议 PR（新 patch pattern、新 sed 规则），人审合并。
   与翻译 job 同模式：LLM 生成、机械验证、人放行。
5. **兜底**：environment 审批人在线上前把关；rollback 按 SHA 重建，
   适配层全坏也能回到上一已验证状态。

## 十、与现行 agent 驱动模式的对比及迁移策略（2026-09-19 补充）

> **已决策（2026-09-19）：采用中间态 agentic CI 作为目标架构。**
> 理由：LLM 驱动整个工作流的价值在于自主解决问题（本会话实证：上游构建系统迁移、
> pnpm 工具链断裂、首页补丁失效均由 agent 自主修复），而非仅翻译文本。
> 纯 API 翻译方案（原 P2）降级为可选项，不再作为目标。

| 维度 | agent 月度驱动 | CI 架构 |
|------|----------------|---------|
| 人力 | ≈0 | ≈0（auto-merge + 自动审批配置下） |
| 时效 | 滞后 ≤30 天 | 滞后 ≤1 天 |
| 单次成本 | 高（全栈 LLM 会话） | 低（编排免费，LLM 仅翻译） |
| 一致性 | 随模型/上下文波动 | 脚本确定性 |
| 审计/回退 | 直推无痕迹 | PR 历史 + 审批 + rollback |
| 供应商依赖 | 绑定 agent 工具与 skill 格式 | GitHub 基础设施 |
| 漂移发现 | 月度运行时 + 会话内救火 | 周冒烟 7 天内报警 |

核心论点：agent 会话的固定成本（重读文档、摸索、试错、事故）**每月重复支付**，
教训随会话消失；CI 把教训一次性固化为代码（断言/审计/版本派生），此后免费复用。

### agentic CI 目标形态（LLM 驱动 + 脚本护栏）

```
cron 每日 / 手动
    │
    ▼
[L0 detect]  纯脚本，无 LLM：sparse 拉 docs/，比对 LAST_SYNC
    │ 无变化 → 结束（成本≈0）         ── 成本闸门：agent 只在有事可做时启动
    │ 有变化
    ▼
[agent job]  LLM 驱动，全权执行 .project/ai-skill.md 工作流：
    · sync-check / 阅读 diff / 分批翻译          （生成）
    · 调用 audit.sh / proofread.sh 自检并修复      （机械护栏，agent 主动跑）
    · 遇到构建断裂/补丁失效 → 自主诊断修复         （自主性，纯脚本没有）
    · 开 PR（PAT），附 audit 报告
    │
    ▼
[L1 gate]    纯脚本 CI 检查（同款 audit/lint 独立重跑）
    │        ── 关键原则：agent 的产出必须被非 agent 的检查验证
    │ 小 diff → auto-merge；正文翻译 → 人审（可逐步放宽）
    ▼
[L3 deploy]  merge 触发：官方工具链构建 + fail-closed 断言 + deploy-pages
             （可选 environment 审批；rollback 按 SHA）
```

设计要点：
1. **ai-skill.md 就是 agent 的岗位说明书**——现有文档已按 agent 可执行的方式写成，
   迁移成本极低；需同步修订为引用 P0 脚本（audit/proofread）代替"手搓 bash"
2. **成本闸门（L0）保留纯脚本**：agent 会话昂贵，只在有上游变更时启动；
   日粒度增量 diff 比月度批量小，单次会话成本反而下降
3. **护栏不可妥协**：agent 产出必须过独立的确定性 CI 检查（同款脚本两处运行），
   这是"自主性"能安全放大的前提；fail-closed 断言同样适用
4. **自主性边界**：agent 可修上游断裂（开修复 PR），但不直接碰 main 和 Pages——
   一切经 PR；事故回退用 rollback 工作流
5. **60 天休眠**：上游长期无变更时仓库无提交，需 keepalive job 保活 cron

迁移三档（原第 2 档即目标，第 3 档降为可选）：
1. **只做 P0**：脚本化审计供 agent 会话调用，无论是否上 CI 都值得；
2. **中间态（已选定）= agentic CI**：如上设计；
3. ~~完全 CI（翻译走纯 API）~~：降级为可选优化，非目标。

## 十一、建议落地顺序（2026-09-19 按 agentic CI 决策修订）

1. **P0（先行，无决策依赖）**：audit.sh（全量结构审计）+ proofread.sh + glossary.json
   （术语机器可读）+ compare_headings.sh 快照竞态修复——本地与 CI 两处复用，
   agent 会话（现行月度模式）立刻受益；
2. **P1 = agentic CI 骨架**（按第十二节审查结论拆为 P1a 地基 / P1b 上线）：
   - P1a：ai-skill.md 参数化、open-PR 去重与断点、预算熔断、失败通知、文档 lint；
   - P1b：L0 detect → agent job → L1 gate（含 PR 完整性比对）→ L3 deploy，
     信任建立期先行，凭据最小化。
   **前置决策**：agent 运行器选型（Claude Code Action / 其他 agent CLI in Actions）、
   API token 进 Secrets、auto-merge 阈值、environment 审批开/关；
3. **P2（可选增强）**：TM 翻译记忆、AI review bot、预览、欠账看板、回译校验——
   纯 API 翻译流水线不再是目标。

## 十二、agentic CI 漏洞审查（2026-09-19）

结论：骨架成立，审查出 3 个阻塞级漏洞、5 个补强缺口、2 个不可消除的残余风险。

### 阻塞级（不修则 P1 上线即翻车）

| # | 漏洞 | 说明 | 补强 |
|---|------|------|------|
| 1 | **ai-skill.md 非环境无关** | 文档假设 `../perfetto` 平级克隆、`127.0.0.1:7897` 代理、playwright-cli 会话——CI runner 三条全不成立，agent 照搬即迷路 | ai-skill.md 参数化（路径/代理/校验手段由环境注入），区分本地会话与 CI 行为差异 |
| 2 | **PR 模式下状态机缺口** | PR 未合并则 LAST_SYNC 不推进 → L0 次日重复检测 → 多个翻译 PR 互相冲突；agent 中途崩溃留下半成品 | open 翻译 PR 存在时跳过（去重）；concurrency 组；LAST_SYNC 随 PR 合并生效；按文件粒度断点清单 |
| 3 | **预算与循环无硬上限** | 自主修 bug 无天然停止条件，6h job 上限对应失控 token 成本 | 会话级 token/步数硬熔断；超限即开失败报告 Issue 退出 |

### 补强缺口

| # | 缺口 | 补强 |
|---|------|------|
| 4 | audit 查不出漏翻文件 | L1 增加纯脚本比对：PR 变更文件集合 ≡ 上游 diff 文件集合（+已声明欠账） |
| 5 | 缺信任建立期 | 前 N 轮强制人审 + 抽查校准，再逐步放宽 auto-merge 阈值 |
| 6 | 凭据与注入面 | PAT 最小权限（仅本仓库无 admin）或短期 GitHub App token；翻译的上游文档是不可信输入（prompt 注入载体）需明示威胁模型；**merge 权限与生成权限永久分离——agent 不得自审自并** |
| 7 | 失败静默停摆 | 预算熔断/agent 卡死/L1 失败 → 自动开 Issue 或邮件通知 |
| 8 | 文档-脚本漂移（proofread.sh 幽灵为先例） | CI 廉价 lint：工程文档引用的脚本路径必须存在 |

### 残余风险（明示，不可消除）

| # | 风险 | 可选缓解 |
|---|------|---------|
| 9 | 结构对但语义错（漏译段落/幻觉内容），全自动合并时质量下限 = LLM 单次表现 | P2 回译校验：LLM 中文译回英文与原文比相似度，拦漏译/幻觉（成本约翻倍） |
| 10 | 错误翻译上线后静默存活 | 定期随机抽样回译抽查 |

## 十三、运行模式决策（2026-09-19 复审）

**维持"月度本地人工触发 agent 会话"为运行模式，暂不迁移 agentic CI。**

复审逻辑：第十二节 3 个阻塞级漏洞的共同前提是**无人值守运行**；月度本地模式下
人（每月 30 分钟的在场）天然充当调度器、去重器、预算熔断器和环境适配层，
零成本绕开全部三个问题。CI 的增量收益（时效 ≤1 天、审计、免人工发起）
在当前阶段不足以覆盖 P1a/P1b 的工程成本与残余风险。

**仍然要做的（与运行模式无关，纯收益）：**
1. P0 三件套（audit.sh / proofread.sh + glossary.json / compare_headings 竞态修复）
   ——直接强化月度会话，消灭欠账返工与术语违规；
2. workwork.sh 补 fail-closed 断言（sed 修补后产物验证、构建后首页断言
   含"什么是 Perfetto"）——堵住 fail-open 事故类（本轮首页事故的疫苗），
   本地模式同样受益，约 20 行。

**重启 CI 迁移的触发条件（出现任一即重估，避免凭感觉摇摆）：**
1. 读者对文档滞后的投诉成为实际问题（新鲜度需求成立）；
2. 月度批量持续增大，单次会话 token 成本与出错面增长到不可接受；
3. 维护者无法保证每月一次的触发。

此前各节的 agentic CI 设计（第十、十一、十二节）保留为**触发条件满足时的
现成方案**，不废弃。

## 十四、渲染语义一致性体系（2026-09-19，源自 Note: 未翻译事故的体系化复盘）

事故的类：**译文与上游在"渲染语义"层不一致**（上游纯文本 ↔ 译文提示框，标题对比不可见）。
修复框架（四层）：

| 层 | 根因 | 修复 | 状态 |
|----|------|------|------|
| L1 症状 | 5 处 Note: 未翻译/译走 | 逐处修正 | ✅ |
| L2 规则 | proofread 规则与渲染器真实语义不符（未区分大小写/位置） | 规则以 render.mjs 源码为事实依据重写（E2 收窄、W2/W3 降级为警告） | ✅ |
| L3 检测 | 无任何检查能发现 callout 漂移 | audit.sh A7：callout 数量 vs 上游 | ✅ |
| L4 流程 | lint 修复未经确认直接部署；浏览器 review 只比标题结构 | ai-skill.md 增加"提交/推送/部署需人工确认"硬约束 | ✅（成文） |

### 渲染器特殊构造 × 检测覆盖矩阵（事实来源：render.mjs/md_utils.mjs 源码枚举）

| 渲染构造 | 语义 | 结构检测 | 状态 |
|----------|------|----------|------|
| 段首大写 NOTE:/TIP:/WARNING:/TODO:/FIXME:/Summary: | 提示框 | A7 数量 parity | ✅ |
| 图片/链接 URL | 资源引用 | A5/A6（URL 归一化集合） | ✅ |
| 代码围栏 | 代码块 | A3 数量 | ✅ |
| 标题层级 | 结构 | A2 数量 | ✅（锚点逐一对齐未做） |
| `<?tabs>`/`TAB: ` | 选项卡 | **无** | ❌ 待加 |
| 代码块语言标签（```lang） | 高亮/mermaid 渲染 | **无** | ❌ 待加 |
| 行内代码 span 数量 | 段落 shape | **无** | ❌ 待加（A8 候选） |
| 加粗/斜体标记数量 | 段落 shape | **无** | ❌ 待加（A9 候选） |
| toc.md `{.class}` 属性 | 侧边栏过滤 | 无（单文件，人工） | △ |
| 定义列表（`\n:`） | dl 渲染 | 无（低价值） | △ |

### 仍未体系化的三类缺口

1. **矩阵空格**：tabs/语言标签/行内代码/加粗斜体的 parity 检查未实现（均属"渲染语义不可翻译"
   构造，规则与 A7 同构，实现成本低）
2. **规则与事实来源的自动同步**：glossary.json 的 marker 清单是手工维护的，上游 render.mjs
   若新增标志会静默失配——可让 audit.sh 从 render.mjs 源码提取 startsWith 标志清单，
   与 glossary.json 比对（规则本身的规则）
3. **运行时 review 层**：compare_headings.sh 仍是"标题"对比，可升级为 compare_structure.sh
   （标题 + callout 元素 + tabs + 代码块高亮类的运行时计数比对），把浏览器 review 从
   "抽样人工"变成"全量结构化"；语义级（漏译/幻觉）仍只能靠回译抽查（P2）

### 流程层新约束（2026-09-19 起生效）

- **提交/推送/部署（deploy-gh-pages）逐次需人工确认**，工作流文档描述的是顺序而非授权
- lint/规则修复视为翻译变更，走同一门禁（audit+proofread 全绿 + 人工确认）
- 新增 lint 规则必须先在语料上校准（flags 逐一对照上游确认为真违规）才能作为 error 级

## 十五、月度模式优化清单（2026-09-19）

核心洞察：**audit.sh 落地后，月度会话从"按流程执行"变为"跑审计 → 修到全绿"**——
幂等、可断点、可验证，中断/遗漏不再依赖 git status 推断。这是月度模式的最大
单点优化，也是以下各项的地基。

| # | 优化点 | 说明 | 优先级 |
|---|--------|------|--------|
| 1 | P0 三件套 + fail-closed 断言 | 见十三节"仍然要做的" | ★★★（已在计划） |
| 2 | HANDOFF.md 会话纪要 | 每次会话结束记录：本轮的坑与绕法、术语新决策；下次开工先读——用文件解决"教训随会话消失" | ★★★ |
| 3 | 短语对照表（轻量 TM） | 短语级定型译法（含链接文本约定，如"从命令行合并 trace"）存 JSON；翻译前注入、proofread 校验——本会话「Trace 合并」vs「Trace 合并的工作原理」不一致的教训 | ★★★ |
| 4 | 部署前自动 tag | 记录上一个 gh-pages SHA（或 tag），事故时一条 force push 回退——gh-pages 强推无回退点的廉价保险 | ★★★ |
| 5 | 子代理 prompt 模板化 | 公共部分（规范+术语+链接约定）抽成 .project/prompts/ 模板，避免每次手写漂移 | ★★ |
| 6 | 校验聚焦 | 变更/新增页浏览器比对 + 其余页 audit 结构审计，替代 122 页全量慢扫（本会话实际做法的固化） | ★★ |
| 7 | 批次划分脚本化 | 按 diff 文件列表自动分组出批次清单 | ★★ |
| 8 | 回译抽查 | 每轮随机抽 2-3 文件 LLM 回译比对原文，拦"结构对但语义错" | ★★ |
| 9 | 欠账趋势 | audit 结果持久化，连续轮次可见 | ★ |
| 10 | sync-check 输出精简 | 本会话 46KB 输出大部分无用 | ★ |

## 十六、review 体系最终架构：本地双构建对比（2026-09-19 用户确认）

决策：**不再以官网线上页为内容比对基准**。同一个上游 commit 本地构建两份站点
（英文原版 + 中文翻译版，同一 build.mjs、同一 CSS、同一首页补丁），逐文件比对
渲染产物。官网只保留"部署后抽查"角色（验证部署路径，不验证内容）。

```
upstream git HEAD（= LAST_SYNC 同源）
   ├─ 构建英文站: git restore docs → build --out out/en-site
   └─ 构建中文站: 复制 zh docs → build --out out/perfetto.dev
                     │
                     ▼
        渲染产物文件级 DOM 签名比对（无 HTTP、无 CDN、无时间偏移）
```

对比官方线上页的三个噪音源（官网 HEAD ≠ LAST_SYNC 的时间偏移、CDN 缓存、网络
抖动）全部消除；"同一构建器 + 同一 CSS + DOM 签名一致 = 渲染必然一致"。

### 实施任务（2026-09-19 执行）

| # | 任务 | 状态 |
|---|------|------|
| T1 | compare-structure 改造：默认双构建模式（en-site vs zh-site 文件级比对）；--live 模式改为"本地构建 vs 线上抓取"做部署抽查；差异分类汇总（hljs 高亮类/行内格式互换/结构差异）+ 全量差异报告 | ✅ 完成 |
| T2 | audit 补充检查：A8 显式锚点序列 {#...}、A9 代码块语言标签序列、A10 行内代码 span 数、A11 加粗/斜体数量（段落感知计数，`_x_` 归一化） | ✅ 完成 |
| T3 | 全量分诊：双构建比对全部 toc 页面，按三类归因；非 hljs 类（结构/行内格式）逐项修复清零（含 perfetto-cli 漏译 10 选项、faq 整段漏译等重大发现） | ✅ 完成（非 hljs 0，hljs 24 页待 T4） |
| T4 | 代码注释翻译政策（**待用户决策**，T3 产出数据后决定）：停止翻译注释（严格像素一致）或工具放行 hljs 差异（务实一致） | 待决策 |
| T5 | 回译抽查纳入月度清单（workwork.md 快速启动第 6 步） | ✅ 完成 |
| T6 | workwork.md/HANDOFF 同步更新（含 4.5 CJK 渲染坑清单） | ✅ 完成 |

### 分层 review 漏斗（最终形态）

| 层 | 工具 | 拦什么 | 成本 |
|----|------|--------|------|
| 1 源码结构 | audit A1-A11 | 结构欠账 | 秒级 |
| 2 规则 | proofread | 术语/标志/标点 | 秒级 |
| 3 渲染结构 | compare-structure（双构建） | callout 漂移/格式互换/英文残留 | ~1 分钟 |
| 4 语义抽样 | 回译抽查（月度会话内 LLM） | 错译/漏译/幻觉 | 每轮几分钟 |
| 5 部署抽查 | compare-structure --live（2-3 页） | 部署路径/CDN | 分钟级 |

## 十七、review 实践复盘：坑、方法论与完备性判定（2026-09-19）

> 本轮 review 体系升级（第十六节 T1-T6）的完整复盘。背景：从"标题数量对比"升级为
> 四层漏斗（源码结构/规则/渲染/部署），首跑 122 页中 88 页差异、57 项源码欠账，
> 最终非 hljs 清零。以下是过程中的全部坑与提炼。

### 17.1 坑清单（22 个，按层归因）

**工具层（6）**
| # | 坑 | 处置 |
|---|----|------|
| 1 | bash 3.2 无 mapfile | 迁移 python |
| 2 | `$var` 后紧跟全角字符被并入变量名（unbound，踩两次） | `${var}` 写法 + 迁移 python |
| 3 | `sed -i ''` macOS 专有，GNU 下报错 | 迁移 python（跨平台） |
| 4 | python 正则 `[^)]` 跨行匹配（grep 逐行不会），URL 提取吞换行 | `[^)\n]` |
| 5 | 相对链接归一化 base 漏 `docs/` 前缀 | 补前缀 |
| 6 | 浏览器快照竞态（`ls -t` 猜最新快照拿到别的会话） | 从 goto stdout 捕获本次快照 |

**方法论层（5，最深刻）**
| # | 坑 | 教训 |
|---|----|------|
| 7 | A10/A11 按行计数被上游 80 列硬换行系统性欺骗，子代理按错误规则"镜像换行"修了一轮 | **错误规则比没有规则更糟——会驱动错误修复污染语料**；规则先校准再执法 |
| 8 | E4 启发式（闭合符+全角标点=bug）在渲染验证正常的语料上误报 | **启发式让位于权威渲染判定** |
| 9 | hljs 差异排在签名序列前面，掩盖后面 7 页真实结构差异 | **噪音先归一化，比对继续** |
| 10 | 拿官网线上页当对比基准（时间偏移/CDN/网络三重噪音） | **双构建同源对比** |
| 11 | A8 把"本地多出锚点"当差异（实为中文标题 slug 适配） | 规则区分缺失/多出的方向性 |

**流程层（4）**
| # | 坑 | 处置 |
|---|----|------|
| 12 | dev server 竞态：compare-structure 英文构建翻转共享 docs 目录，watch 型 server 重建后停在英文快照 | 短期规则：不并发/跑完重启；治本：git worktree（未做） |
| 13 | 41 文件拆批派发漏 5 个 | 清单驱动派发须核对数量 |
| 14 | 两个子代理并行修改 workwork.py | 主代理复核工具完整性 |
| 15 | 规则修复与语料修复交错（规则修对后，迁就旧规则的改动需甄别） | 规则变更先行并通知所有批次 |

**语料层（7 大类历史错误，本次全部获得自动化检测）**
| # | 类别 | 规模 | 检测 |
|---|------|------|------|
| 16 | `_中文_` 下划线斜体静默不渲染 | 一两百处 | A11 + 双构建 |
| 17 | 全角 `）` 混入 URL 破坏链接 | 80+ 处 | A6 |
| 18 | 列表续行缩进不足整体脱出列表 | 多页 | 双构建 |
| 19 | 闭合 `**` 紧邻全角标点特定形态失效 | 若干 | 双构建（权威） |
| 20 | callout 大小写/位置判定错误 | 5 处 | A7 + render.mjs 语义 |
| 21 | 整段漏译 | perfetto-cli 10 选项、faq 段落等 | 双构建元素数 |
| 22 | 硬换行（行尾双空格）丢失 | 多处 | 双构建 |

### 17.2 可迁移的方法论（五条）

1. **金标准是真实渲染产物**——一切中间表示的启发式近似都可能骗你
2. **规则先校准再执法**——flags 逐一对照确认真违规才能升 error 级
3. **对比必须同源同时态**——同一 commit 双构建
4. **差异先分类归因（hljs/inline/struct），噪音归一化后继续比对**
5. **共享可变资源（目录/端口）要显式管理**——并发场景必出竞态

### 17.3 完善项（明确未做）

| 优先级 | 项 | 说明 |
|--------|----|------|
| 治本 | en 构建改用 git worktree | 消除与 dev server 的共享目录竞态（坑 12） |
| 增强 | compare-structure 默认输出全量结构化差异（JSON） | 现为失败页首差 + --verbose |
| 增强 | 英文残留检测扩展到标题 | 现只查 p/li |
| 增强 | 站内锚点链接目标存在性校验 | A6 现排除 `#` 链接，断锚查不出 |
| 增强 | 表格列数比对 | A4 现只比行数 |
| 实践 | 回译抽查首跑 | 清单第 6 步已规定但尚无首例（语义层唯一防线） |
| 存量 | W1 空格警告 45 处 | 不阻塞 |
| 自动化 | 规则与事实来源自动同步 | render.mjs 新增构造时检查项不会自更新 |

### 17.4 完备性判定

**不是"最完备"，且该提法本身需修正。**完备性的正确度量不是"没有已知漏洞"，而是：
1. 已知错误类别全部有自动化检测 ✅（四层漏斗覆盖 17.1 语料层 7 类）
2. 未知类别有暴露通道 ✅（回译抽查/人工 review/线上抽查——但语义层薄）
3. 规则可被证伪和校准 ✅（本轮 E4 添加-删除、A10/A11 升级实证了机制有效）

**两块明确的未完备区**：语义级检测（错译/意译偏离仅回译一道防线，未实践）；
规则自同步（上游渲染器演化时检查矩阵靠人工跟进）。
