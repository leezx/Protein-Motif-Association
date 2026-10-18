# Step 4b-1 setup 修复交接

- 日期：2026-10-18
- 分支：`step4b-atac-footprinting`
- PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)，base `step4b-atac-footprinting`
- 修复 commit：`8e33a35`（PR head 后续可能因审计元数据更新）
- 任务：修复 Argos 首次 setup 在 PRINT 资源预览处退出的问题。

## 证据与修复

Argos 上 driver PID 8822 在 `00_setup.sh` 阶段以 `SETUP_FAIL` 退出，尚未进入 smoke test 或 round 1。日志最后出现 PRINT 共享资源目录列表；资源文件已解包，但 `hg38.chrom.sizes`、`hg38.fa` 和 `.fai` 尚未生成。

脚本启用 `set -euo pipefail`，随后执行 `ls -la precomputedTn5Bias dispModel | head`。在 Argos 对该命令进行只读复现，退出码为 141（`ls` 被 `head` 提前关闭管道）。修复仅将该预览改为 `ls -ld precomputedTn5Bias dispModel`，不改变输入、阈值或 benchmark 方法。

## 验证与门禁

- Shell 语法检查：`bash -n scripts/04b_footprint/00_setup.sh` 通过。
- Git diff 检查：`git diff --check` 通过；修复 commit 为 `8e33a35`。
- GPT 对 commit `9c8ff5a` 的范围澄清给出 `APPROVE`；其后因 GitHub 集成 HTTP 403，结论只记录在持久审核对话，未写入 GitHub review。随后 setup 运行尝试发现 FASTA 中断恢复问题；本次 PR 又包含该修复，当前 HEAD 需要重新审核。
- 当前远端 setup 已停止；数据和已生成的资源仍在 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/`。
- 在当前 PR 获得明确 `APPROVE` 前，不重启 setup 或任何依赖分析。
- PR 批准仅覆盖代码修复，不等于外部执行授权。仅做 setup 验证时，须直接调用 `scripts/04b_footprint/00_setup.sh`；不可用 `run_4b1.sh` 代替，因为它会继续运行 prep、smoke 和 12 个 round-1 jobs。
- 重启完整 driver 必须有独立于 PR 审查的用户授权。本项目负责人此前已指示 Codex 在 §6 门禁满足后启动第一轮评测；仅在这一既有授权范围内执行，不得将 GPT 的 PR `APPROVE` 当成额外执行授权或扩展分析范围。
- 重新请求同一 PR 的 GPT 复审。复审通过后，按上述授权边界继续；遇到新代码问题时仍在同一 PR 内最小修复并再次审查。

## 2026-10-18 01:40 EDT — setup attempt stopped at external-run PR gate

GPT approved the scope clarification at commit `9c8ff5a`. The driver was then started under the user's separate first-round benchmark direction but stopped during setup after recognizing that the repository requires a reviewed PR for each external run. PID 11481; log `/home/zz950/PMA_fetch/fp_4b1_rerun_20261018.log`. It copied chromosome sizes and started decompressing the reference, then stopped before `.fai`, input preparation, smoke tests, or round 1. The downloaded gzip reference is unchanged. The generated, unindexed `hg38.fa` is partial (1,398,439,936 bytes); no process remains.

The attempt showed that the old setup treated any nonempty `hg38.fa` as complete. The PR now preserves unindexed output under `processed/round1/setup_interrupted/`, decompresses to a temporary path, atomically installs the full reference, and indexes it. This updated code and audit record require GPT review before another Argos command. No analysis has run.

原始数据和分析输出均留在仓库外。

## 2026-10-18 01:46 EDT — FAI 完成状态复审与修复

GPT 对 PR #4 当前 HEAD `1333434` 给出 `REQUEST_CHANGES`。已知的“部分 FASTA、无索引”恢复正确，但仅用非空 `.fai` 判定完成会漏掉索引写入中断、FASTA 缺失或 stale/mismatched FAI。GPT 未发现新的审计范围阻断项，原 scope-control finding 继续为 RESOLVED；GitHub review 提交仍返回 HTTP 403。

在同一 PR 中新增 `setup_reference.sh`：仅当 FASTA、FAI 与最后写入的 SHA256 完成标记相互匹配才复用；否则将既有 FASTA、FAI 和标记归档到外部工作目录，从原始 gzip 解压到同目录临时文件、在临时 FASTA 上建索引，再安装 FASTA/FAI 并最后原子写入标记。新增小型本地 fixture 覆盖部分 FASTA、部分 FAI、有效 pair 复用、FASTA 缺失但 stale FAI 存在四种情况，均通过。`bash -n`、`git diff --check` 通过。未访问 Argos，未执行外部分析。

GPT 还指出 PR 描述没有概括 interruption recovery；提交前将更新 PR 描述反映完整修复范围。当前代码和审计改动仍需在本 PR 获取新 HEAD 的明确 `APPROVE` 后，才可同步或在 Argos 上运行。完整 benchmark 仍按用户此前授权范围执行，PR approval 不扩大该范围；合并另需用户确认。
