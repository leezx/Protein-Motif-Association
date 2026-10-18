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
- PR #4 已提交。ChatGPT 对完整 PR 给出 `REQUEST_CHANGES`：代码修复本身正确，但 handoff 不能把修复 PR 的批准表述成完整 driver 的运行授权。GPT 未能向 GitHub 提交正式 review（HTTP 403），结论记录在持久审核对话中。
- 当前远端 setup 已停止；数据和已生成的资源仍在 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/`。
- 在当前 PR 获得明确 `APPROVE` 前，不重启 setup 或任何依赖分析。
- PR 批准仅覆盖代码修复，不等于外部执行授权。仅做 setup 验证时，须直接调用 `scripts/04b_footprint/00_setup.sh`；不可用 `run_4b1.sh` 代替，因为它会继续运行 prep、smoke 和 12 个 round-1 jobs。
- 重启完整 driver 必须有独立于 PR 审查的用户授权。本项目负责人此前已指示 Codex 在 §6 门禁满足后启动第一轮评测；仅在这一既有授权范围内执行，不得将 GPT 的 PR `APPROVE` 当成额外执行授权或扩展分析范围。
- 重新请求同一 PR 的 GPT 复审。复审通过后，按上述授权边界继续；遇到新代码问题时仍在同一 PR 内最小修复并再次审查。

原始数据和分析输出均留在仓库外。
