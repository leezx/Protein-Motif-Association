# PRINT 8 峰 smoke：登记竞态与预检退出码修复

时间：2026-10-20 10:37 EDT
范围：PMA footprint PR #8；ChIP BED6/PR #7 由 Claude 负责，不在本次范围。

## 审核结果与范围放行

固定 PMA 对话先对 PR #8 精确 HEAD `782a875900401fc201d29313643f4ee4b7203c4f` 复审为 `REQUEST_CHANGES`，复现两项 L1 缺陷：独立 session 子进程在登记 PGID 之前已启动，登记文件写失败时会泄漏；`bounded_check_output()` 忽略非零退出码。其 sandbox 中 deadline suite 的 `/proc` 清理断言失败。修复提交 `7133b1cc7d34c57da5f12f07542ab01319a04328` 再次经固定 PMA 对话 exact-head 审核，结果为 `APPROVE`；两个 finding 均关闭，无新增 L1 blocker，并明确放行一次限定 smoke。L2 继续 `BLOCKED / UNVERIFIED-critical`，真实 HDF5、PRINT S4、Argos `/proc`、并行 caller 和结果维度尚无运行证据。

## 最小修复

- 增加 exec gate：新 session 的 launcher 先阻塞读取一字节，目标程序只有在注册表完成写入和 fsync 后才会 `execvp`。若外层 worker 在登记期间退出，管道 EOF 会阻止目标程序启动。
- 登记失败时关闭 gate，按现有有界 TERM→KILL 流程清理并回收进程，再将失败抛出。
- preflight、PRINT caller 与 RSS sampler 均通过该启动函数，统一消除 start→register 竞态。
- `bounded_check_output()` 检查返回码；非零状态抛出含原始 stdout/stderr 的 `CalledProcessError`。
- 更新 smoke supervisor 对 base supervisor 的固定 SHA。

## 本地验证

通过：

- `python3 tests/test_print_smoke_deadline.py`：覆盖注册写失败时目标不得执行、worker 在注册期间被杀时管道 EOF 阻止目标执行、退出码 7 必须报错并保留 stdout/stderr、正常 worker 完成、TERM-resistant 子进程的有界 KILL 清理。
- `python3 tests/test_select_print_integration_smoke.py`
- `Rscript tests/test_print_variable_width.R`
- R parse、Python `py_compile`
- `bash tests/test_step4b_runner_contract.sh`
- `git diff --check`

本机复跑 deadline suite 通过；测试按监督器合同检查进程组终止，不把 Linux zombie-only PID 误认作仍运行的任务。reviewer sandbox 的失败与本机结果区分记录；本地合成测试不能验证 Argos Linux `/proc`。另在 rcapps3 做只读预检：x86_64、72 CPUs、约 920 GiB MemAvailable、无 `zz950` 队列作业、smoke 输出路径不存在。所有 staged scripts、冻结 BED/fragments/HDF5/models、PRINT modules 与 immutable gate 的 SHA-256 均匹配，R 依赖 `cladoRcpp`、`GenomicRanges`、`data.table`、`rhdf5` 可加载。该预检未调用 PRINT runner。

## 当前边界与下一步

候选 supervisor SHA-256：base `7d594c58de85c012cc3ff08d93c8c67252be65f9cd860497243bc9295ef0a234`；outer smoke supervisor `336c79277c1506447888dc6333db906b68d37cb5c893dbb1a559edb3fb785acc`。下一步仅通过不可变 `pma_bg_gate_v2.sh` 启动一次 8 峰 smoke。40-GiB VmRSS 是采样软停止，44-GiB RLIMIT_AS 是每进程限额而非任务硬上限。预检或 caller 任何失败都保留证据后停止，不重试、不运行全峰 V7、不改环境、不合并。


## 10:38 EDT — 唯一获批 smoke 在 caller 启动前失败

- 按固定 PMA 对话对 PR #8 精确 HEAD `7133b1cc7d34c57da5f12f07542ab01319a04328` 的 APPROVE，尝试通过不可变 gate 启动唯一一次 8 峰 PRINT smoke。远端状态文件记录 `BG_K562_PRINT_INTEGRATION_SMOKE_20261020_V1 EXIT=126 END=2026-10-20T10:38:51-04:00`。gate stderr 明确为 staged worker `run_print_integration_smoke_supervised.py: Permission denied`。
- 核验 gate 本身 mode 为 700、SHA-256 仍为 `3776778b950be90cad124c04937eee422c81466154eccdadfe9e57d58224253c`；worker ROOT、科学输出目录均不存在，且无匹配 caller 进程。由此可确认 caller/PRINT 计算没有启动。
- 因 caller 未启动，没有可报告的分析耗时、CPU、RSS、track/event 文件或 footprint 统计量。EXIT 126 是启动权限失败，不能当作算法运行时间。
- 本次是审核放行的唯一尝试，授权已消耗。固定 PMA 对话复审 mode-only 修复后另指出 supervisor 内部 ID/路径仍是 V1，拒绝新运行；已按 finding 改为 V2 独立 run ID、ROOT 与 output path，并将根因措辞改为“与缺少执行权限一致”。待新 HEAD 复审及明确放行后，才可能有新尝试。未做权限改动、重跑、全峰 V7、环境更新或合并。


## 10:43 EDT — 同 PR 修复 worker 可执行模式（待 exact-head 复审）

- 失败与缺少 execute 权限一致：gate 直接执行 staged worker 路径，而仓库把该 worker tracked 为 `100644`；但本地 Git mode 不能单独证明远端完整 mode/ACL/mount 状态。不可变 gate 的本身权限和 hash 正常。
- 最小修复：将 `scripts/04b_footprint/run_print_integration_smoke_supervised.py` 的 Git mode 改为 `100755`，使受控 staging 保留可执行意图。未来 staging 完成后、调用 gate 之前必须只读验证目标文件可读/可执行、各父目录可穿越、shebang 指向可执行的 Python 解释器，并核验文件 hash。当前没有改远端权限，也没有再次调用 gate。
- 失败记录已保留：唯一获批 smoke 的 gate 状态为 `EXIT=126`，caller 未启动、无科学输出。根据固定 PMA 审核，本次单次授权已消耗；任何后续运行必须先提交同一 PR、对修正后 exact HEAD 获取新 `APPROVE` 和新的单次运行放行。


## 10:44 EDT — fixed-PMA REQUEST_CHANGES：V2 路径隔离

- 固定 PMA 对话核验 live HEAD `8ee1ae28cfe8539434a848eb1044f517daab43ab`，确认 Git mode `100644 → 100755` 且 blob 不变；但发现 supervisor 内部仍硬编码 V1 run ID/root/output，与新的 attempt 不隔离，故不放行。
- 同 PR 最小修正：候选 run ID 改为 `BG_K562_PRINT_INTEGRATION_SMOKE_20261020_V2`；staged code directory、ROOT 和科学输出目录均改用独立 `_v2` 路径；新 worker SHA-256 为 `afffcdf49d74b85e21fd47913276e109b3cae34d383c15c51073251926b70a78`。V1 的 EXIT=126 记录和空目录证据保留原样。
- 按 reviewer 要求把“根因已确认”降为“失败与缺少执行权限一致”；本地 Git mode 不证明当时远端 ACL/mount。当前无远程访问、无新运行授权。


## 10:46 EDT — V2 路径修正已提交，等待 exact-head 复审

- V2 代码及审计更新提交为 `4c9774a62dd382e2a9ce66b4a47393f3c3f0e415`，已推送到原 PR #8 分支；本地 HEAD、origin 和 GitHub API 核对一致，PR 仍 OPEN、未合并。
- PR 描述与 `docs/CODEX_HANDOFF.md` 同步到该 SHA。尚未在固定 PMA 对话发起此 SHA 的新审核；未执行 Argos staging、权限更改或 V2 gate。


## 10:48 EDT — 准备最终 exact-head 审核包

- 同步 CODEX_HANDOFF，区分 V2 实现提交 `4c9774a` 与即将生成的最终文档提交；审核前将再次从本地、origin、GitHub API 实时核对最终 SHA，并同步 PR body。
- 当前无 Argos 访问、无 staging、无远程权限变更、无新 gate 调用。
