# Step 4b-1 smoke 故障与修复交接

- 日期：2026-10-18
- 当前 PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)
- 分支：`task_20261018_step4b_setup_fix`，base `step4b-atac-footprinting`
- 最近已审运行代码：`229ad968489c3c9ec7bc2d090b9f38f7d5e0bb2e`
- 数据与结果路径均在 Argos 的仓库外：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/`

## 最新运行

2026-10-18 03:05–03:13 EDT，按此前用户对 §6 首轮评测的独立授权运行 driver PID `16305`，日志：`/home/zz950/PMA_fetch/fp_4b1_229ad96_20261018.log`。设置阶段通过；prep 生成 91,210 个区域，其中 90,992 个有正 gDNA 覆盖，恰好选择了 2,000 个 B1 tiles；缺少的 chrY 上有 3 个 peak，215 个可查询区域为观察到的零覆盖。BAM 转换统计为 gDNA 577,891、ctrl 11,438、aux 11,687 fragments。

Smoke 最后输出 `SMOKE_FAIL`，未启动 full round 12 个 caller jobs。没有遗留 Step 4b 进程，raw input 未改动。

## 失败证据

- HINT 的 gdna/ctrl/aux 共 12 个 chunk 全部在 RGT 导入时失败：`ModuleNotFoundError: No module named 'pkg_resources'`。每组 `failed.txt` 均记录四个失败 chunk，`hint/events.bed` 为 0 bytes；没有 HINT 结果可供科学解释。
- 只读环境检查：pmafp 是 Python 3.11.17、setuptools 84.0.0，`pkg_resources` 不可导入；RGT 1.0.2 的 `rgt/__init__.py` 仍导入该模块。setuptools 官方版本历史确认 82.0.0 移除了 `pkg_resources`。
- TOBIAS 三组都生成 events。PRINT 与 TraceBIND 没有日志或输出；总控日志出现 6 次 `GDAL_DATA: unbound variable`。只读查看 r4p3 的 GDAL activation hook 确认其在 `set -u` shell 下无默认值地读取该变量。R 子进程在 conda activate 阶段退出是目前推断，尚待修复后 smoke 验证。
- 原 `run_round1.sh` 的无参数 `wait` 没有聚合所有后台 caller 的退出码；`run_4b1.sh` 只用文件存在检查，不能识别 0-byte HINT events。这次 driver 因 PRINT/TraceBIND 输出缺失而停下，但 gate 仍需 fail-closed 修复。

## 同一 PR 内的最小修复

本地正在修改：

1. 增加 `setuptools==80.9.0` 约束，并在 setup/prep 前检查其版本、`pkg_resources` 和 RGT 是否可导入；此依赖尚未安装到 Argos 环境。
2. HINT 每个 chunk 单独等待、检查退出码和输出路径；失败时不合并，非零退出。
3. `run_round1.sh` 逐项等待并汇总所有 callers 状态；任一失败即返回非零。
4. R conda activate 在子 shell 中局部关闭 `nounset` 后恢复，并显式传播激活失败；不覆盖 GDAL 配置变量。
5. Smoke driver 要求 smoke 成功并检查预期产物及 HINT failed marker，失败绝不进入 full round。

这些修复不改变数据、caller 方法、阈值或 benchmark 范围。修复和本交接记录需经当前 PR HEAD 的 GPT 明确 `APPROVE` 后，才能更新 Argos 环境或再次执行命令。下一次仅在既有用户授权内修复环境、验证 HINT/R caller smoke；smoke 全部通过前不得启动 full round。PR merge 仍需用户单独确认。

## GPT 诊断与来源

已向 PMA 项目的持久 GPT 对话提交独立诊断。其结论为 HINT 直接错误已确定，建议固定兼容 setuptools，并修复 smoke 的失败传播；没有批准新的代码或 Argos 运行。setuptools 版本历史：[官方文档](https://setuptools.pypa.io/en/latest/history.html#v82-0-0)。

## 03:21 EDT — GPT 二次诊断与 follow-up 修订

GPT 同意环境兼容、失败传播、精确 setuptools pin 可在同一 PR #4 修复，但强调事件 BED 允许合法的 0 行；不能把所有 smoke outputs 都要求非空。现有修订只要求事件 BED 文件存在、caller 成功退出；PRINT 连续 score track 单独要求非空且 gzip 可读。

GPT 还发现 smoke 与 full round 共用 BAM 路径会导致 full 误用前 20 个区域过滤的 BAM。follow-up 将缓存分为 `bam/smoke/` 与 `bam/full/`，并在下一次 smoke 前将旧 `runs_smoke/` 和 `bam/smoke/` 原样移动到 `smoke_attempt_archive/<UTC attempt>/`，避免旧失败产物被误认为当前输出，同时保留审计证据。

GPT 建议 R conda activation 在局部 `set +u` 中执行，而非将 `GDAL_DATA` / `GDAL_DRIVER_PATH` 置空；follow-up 采用此建议，校验 `CONDA_DEFAULT_ENV` 和 `Rscript`，并把 activation 输出写进 PRINT/TraceBIND 各自日志。driver 在昂贵 setup/prep 前预检 setuptools 80.9.0、`pkg_resources`、RGT import/CLI、`r4p3` activation 和必要 R 包。

**状态更正**：Argos `run_hint.sh` 记录的退出码是 1（chunk 失败后无可合并的 `fp.bed` 导致管道失败）；真正吞掉其失败状态的是父级 `run_round1.sh` 的无参数 `wait`，它仍输出 `ROUND1_DONE`。旧 smoke 最终由 PRINT/TraceBIND 缺失触发 `SMOKE_FAIL`。此前 GPT 诊断请求中关于 `run_hint.sh` 自身退出 0 的表述有误，现以 Argos 的 `hint.log` 为准。

follow-up 尚未验证或推送，也没有代码 approval。仅完成 shell 语法和 diff 格式检查；没有在 Argos 更改环境或再次运行。下一步在同一 PR 完成此最小修订与对应验证，再请求 GPT 审查当前 HEAD；审核通过前不发 Argos 命令。GPT 明确指出还需覆盖 caller 失败/成功零 events、旧输出不被复用、smoke/full BAM 路径隔离等验证场景。

## 03:22 EDT — Follow-up commit

同一 PR #4 的修复已推送：`b811005` 增加 setuptools/HINT preflight 与失败传播，`147d778` 进一步加入 R 环境预检、局部 nounset 处理、caller PID/label 状态聚合、smoke/full BAM 缓存隔离以及旧 smoke output/cache 归档。PRINT score track 要求非空且 gzip 可读；事件 BED 允许合法的 0 行。当前 PR HEAD `147d778` 尚未获 GPT review/APPROVE。

本次代码修改后 `bash -n scripts/04b_footprint/run_4b1.sh scripts/04b_footprint/run_round1.sh scripts/04b_footprint/run_hint.sh` 与 `git diff --check` 通过；没有添加/运行 tests。PR description 已更新为 smoke failure + runner fixes。Argos 自 `229ad96` 停止后未再访问，无环境安装或分析任务；full round 1 未启动，PR 未合并。任何后续 Argos 操作继续等待当前 HEAD 的明确 GPT `APPROVE`。

## 2026-10-18 03:32 EDT — GPT review of `97a6adc` found two blocking issues

GPT reviewed the full PR #4 HEAD `97a6adc51a50a5bb052531095d9c2d29eb8c95fd` and returned `REQUEST_CHANGES`. It approved the setuptools/RGT preflight, local `set +u` activation, HINT/caller status propagation, smoke/full BAM directory separation, stale smoke archiving, and valid zero-event handling. Audit/scope-control passed; review did not authorize Argos execution or merge.

- **F1 — BAM cache/build integrity:** `run_round1.sh` had neither `set -e` nor explicit status handling around `frags_to_bam.py`. A failed conversion could continue to caller launch, and reuse only checked nonempty BAM (not a valid index). Fixed by `ensure_bam_cache.sh`: validate cached BAM with samtools quickcheck and pysam index check; build to a unique temporary BAM; validate BAM+index before publishing; archive invalid prior cache; return nonzero on conversion/validation failure. `prepare_bams.sh` stops immediately on a failed sample before callers are launched.
- **F2 — behavior-level runner regression checks:** added `tests/test_step4b_runner_contract.sh` with mocked tools, covering cache build/reuse/corruption recovery, conversion failure stopping later BAM preparation, a successful HINT run with a valid empty events BED, HINT chunk failure propagation and stale event removal, and caller aggregation that reports one failure while waiting for all started jobs.

Local validation: the fixture passed under the available macOS Bash 3.2; it covers distinct smoke/full BAM paths, `bash -n` passed for all modified/new shell scripts, and `git diff --check` passed. The fixture uses mocks and does not replace real Argos pysam/tabix/RGT or R caller smoke validation. No Argos access, environment changes, benchmark run, or merge occurred after GPT's `REQUEST_CHANGES`. Next: review the exact diff, update PR/audit records in the same PR, push, request GPT review of the new HEAD, and only resume the already-authorized §6 Argos smoke if the new HEAD is explicitly approved.

## 2026-10-18 03:37 EDT — GPT approved d837246; retry audit gate

GPT explicitly approved complete PR #4 HEAD `d8372466f6152f08e6aad7f945fc070cdf57f330` in the persistent RA-Xiaolu / PMA项目 conversation. It confirmed F1 (BAM preparation/cache integrity) and F2 (runner behavior fixtures) are resolved, and audit/scope-control passed. GitHub formal review registration again returned HTTP 403, so the approval is documented in that GPT conversation and local audit records. No merge approval was given.

The user confirmed all downloads/reference checks passed, stated their Argos tasks ended, and instructed “开始做吧”; together with their earlier §6 first-round authorization, this independently authorizes the planned run. The GPT review does not itself grant execution authority. No Argos command has been run since the `229ad96` smoke failure. The latest known results remain: setup/prep passed; HINT failed on missing `pkg_resources`; R activation logged unset `GDAL_DATA`; TOBIAS produced smoke events; smoke gate failed and full jobs did not start. The environment has not yet received the reviewed setuptools pin.

`docs/CODEX_HANDOFF.md` now records the current PR/review state and removes stale statements that `d837246` is uncommitted/unreviewed. This audit-only increment must be pushed to the same PR and receive GPT approval before Argos access. After that gate, fast-forward the Argos checkout, apply only the reviewed dependency pin, and retry the authorized smoke. Do not start full round-1 jobs unless all smoke checks pass. No raw data, method, thresholds, benchmark scope, or merge state changes in this audit update.

## 2026-10-18 03:45 EDT — Argos HINT CLI preflight failure

GPT explicitly approved audit-only PR #4 HEAD `e1f1bc2cb7b1f8f151243c796fe85789e82efb1e`; approval is recorded in the persistent RA-Xiaolu / PMA项目 conversation. GitHub formal review submission returned HTTP 403. After review, Argos checkout `/home/zz950/PMA_code_4b` was fast-forwarded cleanly from `229ad96` to `e1f1bc2`; no Step 4b process was running and the required download/reference markers and inputs were present.

Applied the reviewed `setuptools==80.9.0` pin offline from the local conda package cache. Python 3.11.17, setuptools 80.9.0, `pkg_resources`, and `import rgt` pass. Driver PID `25079`, launched via `/home/zz950/PMA_fetch/pma_step4b1_launch_e1f1bc2.sh`, exited before setup/prep at `HINT_CLI_PREFLIGHT_FAIL`; log `/home/zz950/PMA_fetch/fp_4b1_e1f1bc2_20261018.log`. Directly reproducing `rgt-hint --help` returned 1 because RGT 1.0.2 imports `numpy.mat`, absent in NumPy 2.4.6. No smoke/full caller jobs ran, no raw input changed, and no benchmark result was generated.

GPT has been asked for an independent recommendation on the smallest compatible NumPy pin and its effects on the rest of the pmafp environment. The environment has not been changed beyond the already-reviewed setuptools pin. Next: record GPT's diagnosis, make and test a minimal repair in the same PR, update the PR description and audit files, then obtain explicit approval for the new HEAD before another Argos environment update/retry. No merge or benchmark-scope expansion is authorized.

## 2026-10-18 03:52 EDT — GPT approved failure audit; HINT isolation repair in progress

GPT explicitly approved audit-only PR #4 HEAD `4ebea92a236ba1a67739ca0f37aa84aa6df8da06`; the three audit files and PR description accurately report the `numpy.mat`/NumPy 2.4.6 preflight failure and preserve the execution/merge boundaries. GitHub formal review submission returned HTTP 403.

GPT's independent diagnosis verified that TOBIAS 0.17.5 requires NumPy >=2 while RGT 1.0.2 imports `numpy.mat`, removed in NumPy 2. It recommends preserving `pmafp` and using a separate `pma_hint` environment pinned to RGT 1.0.2, setuptools 80.9.0, NumPy 1.26.4, with only HINT routed to that environment. This is diagnosis/design advice, not implementation or Argos authorization.

Local uncommitted draft adds a clone-based `setup_hint_env.sh` that removes TOBIAS only from the clone, pins NumPy 1.26.4/setuptools 80.9.0, validates imports/CLI and `pip check`, writes environment manifests, and compares `pmafp` package manifests before/after. Driver preflight and `run_round1.sh` now use an explicit HINT-only executable path; the mock fixture checks the path selection. The runner contract fixture passed; changed/new shell files pass `bash -n`; `git diff --check` passed. No Argos command has run since PID 25079 exited before setup/prep; no `pma_hint` was created and no raw/processed data changed. Next: finalize the same-PR changes/audit, push and receive explicit GPT approval of the new HEAD before any Argos environment change or retry. The actual HINT small-BED caller test remains required before smoke acceptance; full jobs remain gated on all smoke callers passing.

## 2026-10-18 04:01 EDT — current review state after 2d55b74

GPT returned `REQUEST_CHANGES` on `feba417` with F1/F2. The focused F1 failure-path manifest audit and clone/install-failure mocks, plus F2 current-state corrections, are committed and pushed at `2d55b74ddc9fe084b780d2205d0920d9f38abc77`. PR #4 remains OPEN; the PR description now identifies `2d55b74` as current and says GPT review is pending. The worktree has audit-only edits in `Worklog.md` and `docs/CODEX_HANDOFF.md` to record the PR-body synchronization; these are not yet committed. No `pma_hint` was created, and no Argos command has run since the HINT CLI preflight failure. Await explicit GPT approval of the full latest HEAD before any Argos access. Do not merge without separate user confirmation.

## 2026-10-18 04:09 EDT — approved HEAD; isolated clone blocked by offline cache

GPT explicitly approved PR #4 full HEAD `4d099df44dc4bb48a93e110241168fadea1b1de6`, resolving F1/F2 with no blockers. GitHub formal review submission returned HTTP 403. After approval and under the user's independent §6 run authorization, Argos checkout `/home/zz950/PMA_code_4b` fast-forwarded from `e1f1bc2` to `4d099df`; no matching Step 4b process or existing `pma_hint` was found. Running the reviewed HINT environment builder reached `conda create --offline --use-local --clone pmafp` but failed because multiple required packages were not in the local cache; offline mode rejected mirror retrieval. The EXIT audit reported `PMAFP_INTEGRITY_OK`, and separate read-only checks found before/after pmafp conda and pip manifests byte-identical. The partial `pma_hint` remains for diagnosis; it has no executable `bin/python`, though `bin/rgt-hint` exists. No actual HINT, small-BED, smoke, or full run occurred; no raw data changed. Exact foreground SSH return status was not captured, but no setup process remained when checked. Next request GPT's minimal offline-compatible recovery design, record it in this same PR, and obtain approval of a new complete HEAD before any Argos environment retry. Do not overwrite/remove the partial clone or merge.

### 2026-10-18 03:54 EDT — HINT isolation implementation committed locally

Committed local candidate `9cff5179fa880c4de85771463a82f8e8fdf844f4` on the existing PR branch. The change adds `setup_hint_env.sh` to clone `pmafp`, remove TOBIAS only from the clone, pin RGT 1.0.2/setuptools 80.9.0/NumPy 1.26.4, validate HINT imports/CLI/`pip check`, and retain before/after conda/pip manifests proving `pmafp` remains unchanged. Driver preflight uses the dedicated environment; only the HINT caller is routed to its executable. Added a mock selector check. Local runner fixture, `bash -n` on modified/new shell files, and `git diff --check` passed.

This candidate is not yet pushed or reviewed. Argos `pma_hint` has not been created; no Argos command has been run since driver PID 25079 stopped before setup/prep. No data or benchmark outputs changed. Next: push this commit with updated PR description/current audit, request explicit GPT approval of the new full HEAD, then build and validate the isolated environment and run a small frozen-BAM HINT call before retrying the full smoke gate. No full round starts unless all smoke callers pass.

## 2026-10-18 03:59 EDT — GPT requested failure-path audit and current-state corrections

GPT reviewed pushed PR #4 HEAD `feba417ab83881546c13b6c60ad94ed6e7a07874` and returned `REQUEST_CHANGES` (GitHub formal review HTTP 403). It approved HINT-only runtime isolation/routing and scope-control. F1: `setup_hint_env.sh` had to audit pmafp manifests even if clone/install/check failed, preserve the original nonzero status, report integrity-check failure, and retain partial pma_hint. F2: current handoff/PR description were stale after push; they must identify `feba417` as the remote HEAD and record the two findings. No real HINT execution is required to resolve these code/audit findings, but remains a pre-smoke validation.

The local fix now uses an EXIT audit handler to export/compare pmafp conda/pip manifests on every path, reports `PMAFP_INTEGRITY_FAIL` if snapshots are absent or differ, preserves existing failing exit codes, and does not delete partial pma_hint. New mocks cover setup success, clone failure, dependency-install failure/source manifest audit, and refusing to overwrite an existing HINT environment. Runner fixtures, shell syntax checks, and `git diff --check` pass. Current-state handoff now reflects `feba417` and the pending F1/F2 repair; the PR description will be updated before push. No Argos environment changes or commands since the `e1f1bc2` preflight attempt; no `pma_hint` created, no data/results changed. Next: commit/push same-PR fixes and audit, obtain GPT approval for the new full HEAD, then proceed to environment creation only after approval.

## 2026-10-18 04:27 EDT — 离线 HINT bundle 恢复草稿

GPT 已批准审计版 HEAD `fc124f1`，但其关于克隆失败的诊断明确不授权新的 Argos 操作。此前整环境离线 clone 因 Conda 包缓存不全失败；本地现将恢复方案改为外部 Linux bundle + `pma_hint_v2` 新前缀，保留失败的 `pma_hint` 和原 `pmafp`。builder 拆成只读 `preflight` 与 `install` 两阶段，核验 linux-64、CPython 3.11、glibc 上限、Python/NumPy/setuptools 精确版本、已确认的 RGT 1.0.2 sdist SHA-256、wheel 与 pip lock/artifact 清单绑定及全部 lock 哈希；先执行离线 Conda/pip dry-run。只有安装、pip check、import/CLI 与 pmafp 前后清单审计通过后才写 `HINT_ENV_READY.json`。driver 要求 READY 对应同一代码 commit，并仍仅通过隔离环境运行 HINT。

本地 mock 验证 `tests/test_hint_env_builder.sh` 与 `tests/test_step4b_runner_contract.sh` 均通过；涉及文件 `bash -n` 与 `git diff --check` 通过。测试覆盖仅为 mock，真实 Linux bundle、Argos Conda/pip 兼容、HINT 小 BED 运行尚未验证。当前草稿未提交，Argos 未连接；下一步同步本 handoff/worklog 和 PR 描述，推送同一 PR 后请求 GPT 审核完整新 HEAD。在明确 `APPROVE` 前不得运行 Argos 命令；也不得合并。

## 2026-10-18 04:29 EDT — 负向验证补齐

修复 Conda lock 循环中的 here-doc/stdin 冲突后，最终重跑 `bash -n`、`tests/test_hint_env_builder.sh`、`tests/test_step4b_runner_contract.sh` 与 `git diff --check`，均通过。bundle mock 现验证错误平台与错误 RGT sdist 校验值会在创建目标前拒绝；测试中的 BAM conversion/prep failure 文本属于预期负向 fixture。Argos 没有连接或运行，也没有环境、数据、caller 或合并状态变化。接下来将这份本地实现和审计同步到同一 PR，并请 GPT 审核新完整 HEAD；审核明确通过前继续禁止任何 Argos 命令。


## 2026-10-18 04:29 EDT — recovery 实现本地提交

离线 HINT builder、driver READY 检查、bundle 规范、mock fixtures 及当前审计已提交为本地 commit `58bff3b`。提交时显式暂存 7 个相关文件并新增 `tests/test_hint_env_builder.sh`；无关的 `design/protein_binding_resources.md` 保持未暂存。此时 `origin` 和 PR #4 仍停在 `fc124f1`，尚未推送；当前 handoff/worklog 需再提交一次以反映这一状态。没有 Argos 操作。下一步提交审计更正，推送同一分支，更新 PR 正文，并请求 GPT 审核完整新 HEAD。

## 2026-10-18 04:38 EDT — 按 GPT bundle 合同加固本地实现

对照 GPT 的设计回复，发现并补齐四个不足：Conda lock 要证明是完整 solver closure；pip 不能把 Conda 管理的 NumPy 当成待安装依赖；预检需要汇总所有缺件；smoke 与真实 HINT small-BED 需要独立标记。新增 validate_hint_bundle.py，校验 RGT build report 对应官方 sdist 和 wheel 的 SHA、CPython ABI、GLIBC symbol 上限、auditwheel policy/native dependency 记录；从 wheel METADATA 检查 tags 及所有激活 Requires-Dist，并确保包只归 Conda 或 pip 一方管理。要求旧版 Conda 兼容的 tar.bz2 package 和带哈希的本地 channel repodata；先离线 solver dry-run，再校验返回的 LINK 包集合与锁文件完全相同。pip 使用 no-deps dry-run/install，依赖闭包由 metadata 映射和安装后 pip check 双重核验。Linux 子进程应用 48,000,000 KB 虚拟内存上限。环境 READY 与小 BED 运行标记分开；smoke 三组 HINT 成功后写入含代码/环境身份及 BAM、regions、events SHA-256 的 HINT_SMALLBED_VALIDATED.json，full round 需该标记。

验证：bash syntax、Python compile-in-memory、两组 mock tests、git diff --check 通过。fixture 覆盖多缺件汇报、缺 wheel、平台/来源不匹配、Conda closure 不符、安装失败/source audit、READY 发布和 runner 失败。测试中曾因 fixture 仍用 .conda 文件名失败，已切换 tar.bz2；macOS 无法设置 48,000,000 KB ulimit，故只在目标 Linux Argos 子进程应用，mock 测试不执行真实安装。所有错误均已修复，最终测试通过。当前远端 PR HEAD 仍是 971fdce；这轮代码尚未提交。没有连接 Argos、构建真实 Linux bundle、改环境、运行 HINT/benchmark、改数据或合并。下一步更新同一 PR 的 handoff/worklog/描述，推送后请 GPT 审核完整新 HEAD；明确批准前不运行 Argos 命令。


## 2026-10-18 04:39 EDT — small-BED gate 的失败传播

run_4b1.sh 没有启用 errexit；因此为 HINT_SMALLBED_VALIDATED 的写入和校验加上显式失败退出，避免 marker 写入/校验失败后仍进入 full round。marker 校验包含代码 commit、READY lock digest、三组 BAM/regions/events 的存在和 SHA-256；HINT 事件 BED 可为空，只要 caller 正常退出且无 failed chunks。最终重跑 shell syntax、Python compile-in-memory、两组行为 fixture 和 git diff --check，均通过。Argos 未连接或运行；本轮调整仍在本地，远端 PR HEAD 仍为 971fdce，待提交、推送并由 GPT 审核。

## 2026-10-18 04:41 EDT — 目标 ABI 的 wheel 标签判定

代码复核发现 validator 的 wheel tag 判定依赖调用它的 pmafp Python ABI，而目标 HINT 环境要求 CPython 3.11/Linux x86_64。已改为按目标 ABI 和 glibc 2.23 上限验证，并从 Conda lock 读取 Python 版本计算 Requires-Dist markers；新增兼容/不兼容 wheel tag fixture。shell syntax、validator compile-in-memory、builder fixtures、runner contract fixtures、git diff --check 均通过。远端 PR #4 HEAD 仍为 `971fdce`，修正尚未提交。没有 Argos 操作、外部 bundle 构建、HINT/benchmark 运行或数据更改；此项须和完整审计一起提交并请 GPT 审核。

## 2026-10-18 04:42 EDT — 本地实现提交

同一分支将离线 HINT bundle closure/provenance 校验、Conda solver closure 比对、受限安装子进程、独立 small-BED marker、fixture 与留痕提交为 `7ad22d3`。只暂存本任务八个文件；无关未跟踪 `design/protein_binding_resources.md` 未加入。验证在提交前已通过。此时提交只存在本地，origin/PR #4 仍为 `971fdce`；没有 Argos 或外部数据操作。下一步更新精确提交记录后推送原分支、更新 PR 描述并请 GPT 审核当前完整 HEAD，批准前不运行 Argos。

## 2026-10-18 04:52 EDT — GPT 复审 F1/F2 与本地修复

GPT 对完整 PR #4 HEAD `4a07dc5dfe5a7dd97cae2978e49ca913c96505fa` 返回 `REQUEST_CHANGES`。F1：dry-run LINK 只比对包名/版本/build，且未保证两份 repodata 受 inventory/hash 绑定、也未证明 lock 指定的 archive 就是实际安装的包。F2：wheel 校验缺少 `Requires-Python`、完整目标 marker 环境，以及裸 `linux_x86_64` binary wheel 的 glibc 兼容证据。

同一分支本地最小修复：验证 linux-64/noarch repodata 的存在、哈希 inventory 覆盖和 JSON 结构；逐个比对 lock 的文件名、name/version/build/SHA 与 repodata 记录；拒绝重复 dist；比较 solver LINK 可提供的 subdir/filename；solver 闭包通过后生成并在安装时使用锁定的本地 `@EXPLICIT` URL 清单。Wheel 增加 CPython 3.11 `Requires-Python` 检查、显式 Linux/CPython marker 值；未知内核 release/version marker 和裸 `linux_x86_64` tag fail closed。新增 negative fixtures 覆盖 repodata inventory 缺项、repodata/lock SHA 不一致和 solver filename 不一致，并验证安装使用 exact URLs。

验证：shell syntax、validator compile-in-memory、`tests/test_hint_env_builder.sh`、`tests/test_step4b_runner_contract.sh`、`git diff --check` 均通过。远端 PR HEAD 仍是 `4a07dc5`；本地修复未提交，需与同步后的审计一起提交并推送，再请 GPT 审核完整新 HEAD。没有 Argos 连接/命令、bundle 传输、环境变更、HINT/benchmark 运行、数据更改或合并；保持审核门禁关闭。
