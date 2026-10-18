# Step 4b-1 setup 修复交接

- 日期：2026-10-18
- 分支：`step4b-atac-footprinting`
- PR / commit：待创建
- 任务：修复 Argos 首次 setup 在 PRINT 资源预览处退出的问题。

## 证据与修复

Argos 上 driver PID 8822 在 `00_setup.sh` 阶段以 `SETUP_FAIL` 退出，尚未进入 smoke test 或 round 1。日志最后出现 PRINT 共享资源目录列表；资源文件已解包，但 `hg38.chrom.sizes`、`hg38.fa` 和 `.fai` 尚未生成。

脚本启用 `set -euo pipefail`，随后执行 `ls -la precomputedTn5Bias dispModel | head`。在 Argos 对该命令进行只读复现，退出码为 141（`ls` 被 `head` 提前关闭管道）。修复仅将该预览改为 `ls -ld precomputedTn5Bias dispModel`，不改变输入、阈值或 benchmark 方法。

## 验证与门禁

- Shell 语法检查和 PR diff 检查：待执行。
- 当前远端 setup 已停止；数据和已生成的资源仍在 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/`。
- 在当前 PR 获得明确 `APPROVE` 前，不重启 setup、smoke test 或 round-1 分析。
- 获批后同步同一分支，在 Argos 重跑 driver；检查 setup 和输入准备，再逐项确认三个 smoke 集合的输出。

原始数据和分析输出均留在仓库外。
