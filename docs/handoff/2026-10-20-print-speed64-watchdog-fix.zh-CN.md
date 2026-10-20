# PRINT 64-peak watchdog review 修订

时间：2026-10-20 11:30 EDT
范围：仅 PMA Step 4b footprint，PR #8；Claude 负责的 ChIP BED6/PR #7 不在范围。

## 审核 finding

固定 PMA 对话对 PR #8 HEAD `6c500bf9afeff5e44eba153ddd2d91d2952f5c69` 的 Quick 复审为
`REQUEST_CHANGES`。唯一 blocker：64-peak wrapper 直接运行 worker，同一进程承担 peak 选择、文件校验、
preflight、caller 和输出校验；阻塞读取可能拖过 deadline，且没有独立父进程在超时后清理 worker
及已登记的独立进程组。handoff 还把 30 分钟总预算错误写成 caller-stage 预算。审核没有访问 Argos，
不批准本次 gate 调用。L2 准确度继续 `BLOCKED / UNVERIFIED-critical`，不属于 runtime-only 任务阻塞项。

修复 commit `58f62eefebdc3c6058843f0a47536604b198273e` 已推送；GitHub PR API 的 head 和
`git ls-remote origin refs/heads/task_20261019_hint_overlay_smoke` 均报告此 SHA。PR #8 仍 OPEN。

## 同一 PR 的最小修订

- 64-peak 脚本现复用已审核的 `run_print_integration_smoke_supervised.py` outer-parent/worker 模式；
  父进程启动隔离 worker，worker 内执行选择、哈希/preflight、PRINT caller 和产物验证。
- 单调时钟 deadline 从父监督器启动时开始并传给 worker。执行预算为完整 30 分钟，覆盖选择、哈希、
  preflight、caller 与输出验证。超时时父进程 TERM worker 与 registry 中的所有独立 process groups，
  最多等待 60 秒清理，再 KILL；D 状态进程可能无法立即消失。清理宽限期单独报告，不算入执行预算。
- 父监督器在证据根目录写入 `outer_supervisor_summary.json`，记录 worker exit、是否超时、是否遗留
  process groups、清理 survivors 和父端总 wall。
- 新增 `tests/test_print_speed64_supervisor.py`：验证入口把所有工作交给受监督 worker，并验证 worker
  阻塞时已登记的 detached process group 经有界 TERM/KILL 清理。既有 8-peak deadline/cleanup 回归也通过。
- `docs/CODEX_HANDOFF.md` 与候选 handoff 已更正：30 分钟包括 selection/preflight/caller/output
  validation，不包括已完成的 BAM→fragments（28:18.88）预处理或超时后的最多 60 秒清理宽限。

## 当前候选运行边界

沿用此前列明的 64 个冻结 K562 peak、PRINT chromosome-wise bias、2 workers、radii 10/20、CPU-only、
每进程 44-GiB `RLIMIT_AS`、采样 40-GiB VmRSS soft-stop、run ID、唯一外部目录和显式 `ctrl print`
标签。当前 wrapper SHA-256：`d741ba0234741de452f5d10682e76b5585d54b51b4496c3fb6653c013099ac6a`；
外层 watchdog SHA-256：`1b4c574e71a8d63c34c92c26810c822e627c4cd25cd78eb7cbc85e8996ca68ad`。

本次验证通过：Python `py_compile`；`tests/test_print_speed64_supervisor.py`；
`tests/test_print_smoke_deadline.py`；R parser 对 `run_print.R` 的语法检查；`git diff --check`。
因 PRINT runner 在 V3 后更新了 warning 记录，旧 V3 smoke 测试现在将其 runner SHA 作为历史身份核验，
不要求旧 one-shot wrapper 与当前 runner 文件 hash 相等；64-peak 候选单独验证当前 runner hash。

没有运行 Argos 命令、读取实验数据、暂存代码或改变环境。修订推送后，须在固定
`PMA｜固定阶段审核` 对话对新 exact HEAD 复审，并取得明确的一次性 gate 放行；失败不重试，不全峰，不改环境，不 merge。
