# PRINT L2 最小集成验证候选

时间：2026-10-20 10:01 EDT
范围：PMA footprint PR #8；ChIP BED6 / PR #7 不在本任务内。
状态：候选代码已推送至 PR #8。2026-10-20 10:05 EDT 只读查询确认 `qstat -u zz950` 无作业、未发现 PRINT smoke 进程或 smoke 输出目录；没有做 Argos 预检或计算。2026-10-20 10:06 EDT 的 handoff/worklog 状态同步提交后，将在固定 PMA 项目对话审核其精确 HEAD。

## 为什么继续做小型集成验证

PR #8 的 variable-width 修复已获固定 PMA 对话对代码提交 `4d6bc671853ecca21a14ff81c8b82fdbeb8086f4` 的 L1 `APPROVE`，但 L2 仍为 `BLOCKED / UNVERIFIED-critical`。真实 HDF5 读取、PRINT 的 S4 槽替换、并行 caller 端到端、输出维度都尚未在真实输入上验证。此前 V6 在计数和 footprint 之前因最后一个 bias chunk 的列数不一致退出；V6 授权已消耗，不能重试它。

## 候选运行范围

- 输入：K562 ENCSR868FGK 冻结 peak BED 的 8 个原始行；不平移、不扩展、不裁剪区间。
- 选择约束：至少两个染色体、至少三种宽度、每个 chromosome+width 组行数恰为 3/2/2/1，且在输入 BED 中交错，验证分组后能恢复原行顺序。
- 计算：固定 PRINT commit、真实 hg38 bias HDF5 和 radii 10/20 模型；从同一 frozen fragments 生成一个 8 区域 countTensor；两个 CPU worker；PRINT 原生逐区域 caller。
- 对照：对每个 group/radius/原始行，从保存的 countTensor 与 bias 行独立构造 ATAC 矩阵，调用 PRINT `regionFootprintScoring()`。count、坐标、summit、range 和结果字段结构严格比对；数值绝对/相对容差均为 `1e-10`，NA/Inf mask 必须一致。重读导出的 score tracks 和 native-event BED，与 direct scorer 的轨道/事件再核对。报告 16 个 group-row-radius 对照。
- 资源守卫：只能经固定 Argos gate；wrapper 检查 gate SHA 和继承的每进程 `RLIMIT_AS <=44 GiB`。总墙钟上限 30 分钟，process-group sampled VmRSS 40 GiB 时软停止；软停止不等于硬任务内存上限。CPU-only，清空 GPU 环境变量；不做自动重试。
- 输出：唯一外部目录 `/home/zz950/PMA_fetch/pma_print_integration_smoke_rcapps3_20261020_v1/` 与 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_integration_smoke_rcapps3_20261020_v1/`。仓库只保存脚本、审计记录和外部路径引用。

## 本地候选与验证

加入了 frozen-BED 哈希检查和 8 行选择器、PRINT direct-comparison helper、可选真实 runner 校验，以及带唯一路径/文件哈希/资源上限的单次 supervisor。selector fixture、variable-width/comparison helper fixtures、R parse、Python `py_compile`、既有 runner contract fixture 和 `git diff --check` 均通过。机器没有 `hdf5r`、冻结 bias HDF5 和 PRINT checkout，因此这些本地检查不能替代真实集成结果，也不能据此声称获得 footprint output。

代码文件 SHA-256：selector `7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856`；runner `b3602e3ca4660a5feed4c8100f5bcbf6b024a9df8571b80d7e09acc1598b97cb`；helper `664d8ff626f903ae107759c4112aa7692061244795f374c1d562d0ce8e4453c6`；base supervisor `3c6ede01d5836dcdccbb1b579376557d0ea4934bb4cac36dc4e5532b0d220997`；smoke supervisor `084de78158ca9a44ecf96467335fd95fb11e9e171c39addc93bdbc6309946187`。这些是本 handoff 写入时的本地候选哈希；commit/push 后必须重新读取当前值。

候选实现提交：`c76113871433d9b99c471f66814b401348b45252`。状态同步提交的 HEAD 以后续 GitHub PR #8 live API 为准；PR 保持 OPEN/unmerged。

## 审核与运行门禁

候选已推到同一个 PR #8。此前 GitHub API 与远端分支曾短暂显示不同 SHA；2026-10-20 10:05 EDT 的 `gh pr view` 和 `gh api` 均确认一致为 `0d8543db67c42beee6e1f4c6ba83db9a711ddd98`，OPEN、未合并。2026-10-20 10:05 EDT 对 Argos 的只读检查未发现 queued job、匹配进程或 smoke 输出目录。状态同步提交后会重新读取并在固定 PMA 对话审核新的精确 HEAD。用户明确要求降低资源并继续；当前持续授权仅覆盖审核后唯一一次 8-peak Argos smoke。V6 的单次授权已消耗，不能重用；若本次 smoke 失败，不自动重试。没有当前精确 HEAD 的 PMA 审核通过前，不做远端预检或计算。小型集成验证即使通过，也只支持所覆盖的实现路径；它不证明 159,628 peaks 的完整运行时间、全任务内存可行性或生物学准确度。全峰运行必须另行审核和授权。

## 当前可测进展

- 代码路径：L1 binding 修复已经批准；新加的 direct-vs-grouped真实输入验证候选尚未审核。
- 真实 footprint 结果：仍为 0；当前任务是修复并验证 caller 集成，尚未产生任何新的 tracks/events。
- 时间/资源：V6 失败前观察到 caller wall `19:14.53`、最大 GNU-time RSS 约 `25.74 GiB`、采样进程组 VmRSS 约 `25.73 GiB`；这是 bias 前处理失败尝试，不是全峰完成时间。新 smoke 尚未运行，无成功时间或内存值。

## 2026-10-20 10:08 EDT — exact-head review findings and same-PR fixes

固定 PMA 对话审查了 PR #8 exact HEAD `657cd3ffb24f3cc1e9d2230d99c3d1526ecebd18`，给出 `REQUEST_CHANGES`，只列两个 blocker：

1. 30 分钟计时先前只覆盖 caller 采样循环；selector 与预检里的哈希、依赖检查可能阻塞，且可能在预算耗尽后才启动 caller。修复为共享一个 monotonic deadline，selector/preflight 子进程使用剩余时间作为 timeout；supervisor 的哈希和依赖预检也检查同一 deadline；截止后不启动 caller。caller 超时时，已有 process-group 清理发送 TERM，最多等待 60 秒后 KILL；30 分钟是计算预算，60 秒是单独的清理宽限。输出校验也运行在同一 deadline 内。
2. direct scorer 原先复用了已分组 bias 矩阵行，不能独立发现偏好提取或行映射错误。修复后重新打开冻结 bias HDF5，按每个原始 BED 行的染色体和 1-based 区间坐标直接提取向量；先与分组矩阵行做逐元素精确比较，再将独立向量交给原生逐区域 scorer。只在 8-row smoke mode 中，分组 bias 构建改为读取目标 interval slices，避免把整条染色体 bias 数组装入内存；full-run 模式保留原有 chromosome-wise 读取，避免对未来全峰运行引入 159k 次随机 HDF5 读取。

本地验证通过：`python3 tests/test_print_smoke_deadline.py`、`python3 tests/test_select_print_integration_smoke.py`、`Rscript tests/test_print_variable_width.R`、R parse、Python `py_compile`、`bash tests/test_step4b_runner_contract.sh`、`git diff --check`。新 deadline fixture 覆盖有效/过期 monotonic 截止；HDF5 helper fixture 覆盖 1-based inclusive slice 的长度和值。它不替代真实 HDF5/PRINT/S4/parallel 集成。

当前候选代码 SHA-256：selector `7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856`；PRINT runner `44853e1a865bcdf86c87ca6fbabd0279d86d144b14953b1b0533c679eb5098f2`；helper `fa2aaba9248a9a67621fe269210b7afd81920aaa3bf85cac443f0a2371865174`；base supervisor `34330aa103d9f15168fbacb4fbab5d278a6336a79ce0476a0c3ed2aa27606b33`；smoke supervisor `35a33b3ca779af5fb70ebcf960f26a7640bd2d33153bd4c1a68d6da24870808d`。

修复已在同一 PR 提交为 `a33a26c63488d983f7a243ede6df994fe8ed4721` 并推送；2026-10-20 10:12 EDT GitHub PR API 确认该实现提交为 live HEAD。后续状态同步会产生新的文档 tip，精确复审应以推送后的 live API SHA 为准。没有 Argos 预检、远端计算、环境变更或实验数据读取；之前只读查询未发现队列作业或 smoke 进程。本轮 `REQUEST_CHANGES` 没有放行 smoke，L2 仍 BLOCKED。若新的 exact HEAD 获 APPROVE，仍只执行一轮 8-region smoke；失败保留日志且不重试，不自动扩展至全峰 V7。
