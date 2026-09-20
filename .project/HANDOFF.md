# HANDOFF — 会话交接纪要

> 每次月度 agent 会话**开工前必读**；会话结束前**必须更新**本文件。
> 目的：把"本轮的坑与绕法、术语新决策"沉淀下来，避免下次会话重新摸索（教训随会话消失是月度模式最大的隐性成本）。
> 格式：新条目加在最上方，保留历史（太旧的可归档到底部）。

---

## 2026-09-20 会话：A12 代码块内容检查（第 18 类坑）

- 用户肉眼发现 atrace.html 代码块缩进错误 → 排查发现**系统性缩进塌缩**（嵌套 2/4/6/8
  空格被压成 1 空格，62 文件 236 处）+ 个别标点混入（`:data_sources`）——
  **DOM 签名与 audit 均不可见**（签名只看标签结构，不看块内容文本）
- 新增 A12：代码块非注释行须与上游逐字节一致；**行尾注释剥离后比对**（初版未剥离，
  政策 B 下行尾注释可译造成假阳性——先校准再修复的纪律再次生效）
- 修复模式：代码部分取上游原文、保留中文行尾注释（行拼接时 splice）
- 残留教训：converting.md 存在**块序错位**（中英块不对应），批量修复依赖块配对，
  配对偏移会误伤——修复后必须 git diff 审查 + A12 复跑

## 2026-09-19 会话（终局）：review 全绿

- **最终状态：audit 0 / proofread 0 错误 / compare-structure 122 页 0 差异（政策 B）**
- 最后 10 页的根因补充（新坑，入 workwork.md 4.5）：
  1. **无语言标注代码块 + hljs 自动检测**：中文内容（AI 提示词、流程图、CMake 注释）
     会翻转语言检测或丢嵌套 span——此类块**必须保持英文原文**（已回改 5 处：
     android-trace-analysis/using-ai 的 AI 提示词、in-app-tracing 的 CMake、
     data-explorer-architecture 的流程图）
  2. SQL 注释 `-- Note:` 前缀需保持英文（hljs-doctag 只认 ASCII）
  3. marked 4.3 全角怪癖确认版：闭合 `**`/`_` 前是 ASCII 标点且后紧跟全角标点→失效；
     `_…_` 后跟全角句号即失效（`*…*` 仅受前一种影响）→ 修复模式：定界符后加空格
  4. 列表内续行缩进必须达到父项内容列宽（`1.  ` = 4 列），否则逃出列表
- 共 6 轮迭代收敛（首差修复后逐层暴露后续差异）——全量差异报告比首差报告重要

## 2026-09-19 会话（续 3）：政策 B 落地 + dev server 竞态坑

- **政策 B 落地**：compare-structure 默认容忍 hljs 高亮类差异（代码注释翻译惯例），
  `--strict-hljs` 严格模式；25 页差异降至 10 页（7 页是原先被 hljs 噪音掩盖的真实分歧，
  已派后台清扫）
- **竞态坑（重要）**：compare-structure 的英文站构建会 `git restore docs` 把
  ../perfetto/docs 临时翻成英文，而 deploy-local 启动的 dev server（build.mjs --serve）
  带文件监听会自动重建——若两者并发，dev server 可能停在英文快照。
  **规则：跑 compare-structure 期间不要开着 dev server；跑完重启 deploy-local**
  （治本方案留给未来：en 构建改用 git worktree，不动共享工作树）

## 2026-09-19 会话（续 2）：review 体系最终架构落地（双构建对比 + 全量清零）

- **compare-structure 改为双构建模式**（默认）：同一上游 commit 本地构建英文站（out/en-site）
  与中文站（out/zh-site），文件级 DOM 签名逐元素比对——彻底消除对比官网的时间偏移/CDN/网络
  噪音；`--live` 降级为部署抽查（本地构建 vs 线上）
- **audit 扩到 A1-A11**：新增锚点/语言标签/行内代码/加粗斜体（段落感知计数：
  剥离列表符后跨行合并，`_x_` 归一化为 `*`——按行计数会被上游 80 列硬换行系统性骗过）
- **全量清零**：源码层欠账（含 perfetto-cli 漏译 10 个选项、faq 整段漏译、
  chrome-tracing 等整块列表脱出）+ 渲染层非 hljs 差异全部修复；当前 audit 0 /
  proofread 0 / compare-structure 非 hljs 0
- **仅剩 24 页 hljs 类差异 = 代码块注释翻译**（待政策决策：停止译注释求严格像素一致，
  或放行 hljs 差异）
- **CJK 渲染坑清单**（重要！下次翻译直接避开）：见 workwork.md 4.5——`_中文_` 斜体不可靠
  用 `*…*`；闭合 `**` 紧邻全角标点特定形态失效（以 compare-structure 真实渲染为权威，
  曾加 E4 启发式但在验证正常的语料上误报已删——启发式让位于真实渲染判定）；列表续行缩进
  镜像上游；行尾双空格硬换行
- 修复批次模式：主代理跑工具出清单 → 3 个并行子代理按页段分工 → 各自用
  `compare-structure --page` / `audit --files` 验证 → 主代理全量复核

## 2026-09-19 会话（续）：工具归一为 workwork.py（单文件 + 单文档）

- 按用户决策：全部工具合并为 `.project/workwork.py`（9 子命令，纯 python 跨平台），
  全部工程文档合并为 `.project/workwork.md`；删除 workwork.sh/audit.sh/proofread.*/compare_*/
  ai-skill.md/TRANSLATION_GUIDE.md/AGENTS.md；精简原则写入 workwork.md 硬约束第 2 条
- 移植坑：bash→python 的 URL 正则 `[^)]` 会跨行匹配（grep 逐行不会），必须 `[^)\n]`；
  相对链接 base 别漏 `docs/` 前缀
- 待人工确认事项：本地提交 bd08567e（callout 修复）仍未推送；本次归一改动未提交

## 2026-09-19 会话（P0 工具链落地 + 欠账清零）

### 本轮做了什么
- 两轮上游同步翻译（093d5387→6faa79a3→1a186d13），含新页 memscope / trace-processor-cli
- 落地 P0 工具链：`workwork.py audit`（全量结构审计）、`workwork.py proofread`+`glossary.json`（术语/标点/标志 lint）、
  `compare-structure（workwork.py 子命令）` 重写（快照竞态修复）、`phrases.json`、`prompts/translate-batch.md`、
  工具（现 workwork.py）fail-closed 断言 + pre-deploy tag + rollback-gh-pages 命令
- 用 workwork.py audit 清零了全部历史欠账：41 个文件约 80 处链接破损（**高频根因：链接右括号写成全角 `）`**，
  导致 URL 吞掉后续文本）、builtin.md 标题结构、perfetto-manifest.md 表格行

### 关键教训（下次会话必读）
1. **callout 判定以 render.mjs 为准**（已核对源码 `renderParagraph`）：**段首大写**
   `NOTE:` / `TIP:` / `WARNING:` / `TODO:` / `FIXME:` / `Summary:`（大小写敏感，列表内
   缩进会被解析器剥离、同样生效）才渲染成提示框，必须保留英文；
   **混合大小写 `Note:` 是纯文本，必须翻译成中文**（如「注意:」）。教训来源：
   曾把纯文本 Note: 误"修复"为英文导致线上出现未翻译文本，且浏览器 review 只比
   标题结构、没查散文，未能兜住——现已加 workwork.py audit A7（提示框数量 vs 上游）+
   proofread W2/W3（段首中文标志词、英文引导词+中文）三层防护
2. **上游英文原文必须用 `git -C ../perfetto show HEAD:<path>` 获取**——
   deploy-local 会把中文 docs/ 拷进上游仓库覆盖英文工作树，直接读工作树会拿到中文
2. **上游站点构建已从 GN+ninja 迁移到 `build.mjs`**（入口 `./infra/perfetto.dev/build`，
   ~4 秒构建）。工具已适配（自动探测新旧系统），首页靠 build.mjs 补丁渲染 README.md
3. **上游封闭工具链**：`python3 tools/install-build-deps --ui` 安装 node 22.23.1 + pnpm 10.34.5；
   全量 install-build-deps 会拉 362 个 test_data + android git 仓库，站点构建用不到
4. **终端代理**：系统 Clash 在 `127.0.0.1:7897`，命令行需显式
   `export https_proxy=http://127.0.0.1:7897 http_proxy=...`，否则 android.googlesource.com 等不可达
5. **playwright-cli**：本机无 Chrome，用 `playwright-cli -s=<name> open --browser=chromium <url>`；
   快照路径从 goto 的 stdout 里抓（`[Snapshot](.playwright-cli/page-*.yml)`），不要 ls -t 猜
6. **bash 3.2（macOS）**：没有 mapfile；双引号内 `$var` 紧跟全角字符会被并入变量名解析，
   用 `${var}` 形式
7. **workwork.py audit 曾有假阳性**：URL 归一化必须在 sort 之前（相对/绝对路径写法排序位置不同）；
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
python3 .project/workwork.py sync-check          # 1. 检查上游更新
python3 .project/workwork.py audit                        # 2. 全量审计（应 0 差异，否则先修欠账）
# 3. 翻译：按 .project/prompts/translate-batch.md 模板派发子代理批次
# 4. 完成后：audit + proofread 全绿 → deploy-local 浏览器抽查 → 提交推送 → sync-update → deploy-gh-pages
# 5. 收尾：更新本文件（HANDOFF.md）
```
