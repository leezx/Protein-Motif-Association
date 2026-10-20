# PRINT 64-peak one-shot V1 失败与兼容性修复候选

时间：2026-10-20 11:40 EDT
范围：PMA Step 4b footprint / PR #8；ChIP BED6/PR #7 由 Claude 负责，不在本次范围。

## V1 执行结果

固定 `PMA｜固定阶段审核` 对 PR #8 exact HEAD `0f8437ee56806d7d0a7cf373976548e2a78f4b49`
批准了创建唯一代码暂存目录、按 SHA-256 暂存六个已审核脚本、通过新鲜预检后执行唯一 gate
命令。只读预检确认 Argos 主机为 `rcGPUs.dfci.harvard.edu` / x86_64，72 核、约 919 GiB
MemAvailable；冻结 BED、fragments、六个脚本、gate、bias/dispersion 模型哈希、PRINT commit、R
依赖均通过，无匹配进程、SGE job 或冲突输出路径。仅创建获批 code-stage 目录并暂存六个脚本，
未改系统、R、conda、PRINT 环境或输入。

唯一 gate 调用：`BG_K562_PRINT_PEAK_SPEED64_20261020_V1`，于 11:39:01 EDT 开始，11:39:02
结束，`EXIT=2`。错误为 `FAIL_CLOSED: __init__() got an unexpected keyword argument 'text'`：
Argos 的 Python `subprocess.run` 不接受 `text=True`。独立外层监督器在约 0.647 秒后记录
worker exit 2、无 timeout、无遗留进程组、无清理 survivors。selector 尚未运行；无 BED 子集、
bias/count/footprint 计算或科学输出。V1 evidence root 仅包含 `outer_supervisor_summary.json`
与空 `process_groups.jsonl`；gate metadata/stdout/stderr/status 保留在
`/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`；V1 scientific output 目录不存在。V1 单次授权已
消耗，不得重用 ID、覆盖证据或自动重试。

## 同一 PR 的最小修复候选

- 将 `subprocess.run(..., text=True)` 改为 Python 3.5 兼容的
  `universal_newlines=True`，并新增 AST 回归断言禁止恢复 `text=True`。
- 因 V1 run ID/目录已有失败证据，候选 V2 使用全新 code-stage、run root、output path 和
  `BG_K562_PRINT_PEAK_SPEED64_20261020_V2`，保留相同冻结 64-peak 选择、PRINT 生产
  chromosome-wise bias、2 workers、radii 10/20、CPU-only、30-minute end-to-end deadline、
  每进程 `RLIMIT_AS` 44 GiB 与 sampled process-group `VmRSS` 40-GiB soft stop。
- V1 失败后只读确认 Argos `/usr/bin/python3` 为 Python 3.5.2，解释了 `text=` 参数不兼容。
- 候选 V2 wrapper SHA-256：`7a210086eb819b8481a62f079ea5f184174e53e36495e34a7701eb540d8b4c4a`；其余脚本和 gate pins
  沿用 V1 已核验值。候选命令为：

  ```sh
  PMA_PRINT_SPEED64_EXPECTED_SHA256=7a210086eb819b8481a62f079ea5f184174e53e36495e34a7701eb540d8b4c4a \
    bash /home/zz950/PMA_fetch/pma_bg_gate_v2.sh \
    BG_K562_PRINT_PEAK_SPEED64_20261020_V2 \
    /home/zz950/PMA_fetch/pma_print_peak_speed_code_20261020_v2/run_print_speed64_supervised.py \
    ctrl print
  ```
- Local validation passed: Python `py_compile`, `tests/test_print_speed64_supervisor.py`,
  `tests/test_print_smoke_deadline.py`, `tests/test_select_print_integration_smoke.py`, R parser for
  `run_print.R`, and `git diff --check`. An initial test command named a nonexistent selector-test
  filename and exited 2 after the first three checks passed; the actual repository test
  `test_select_print_integration_smoke.py` was then run and passed. No Argos V2 code stage or run exists.
- 当前没有 V2 Argos 运行授权。需要同一固定 PMA 项目对 PR #8 新 exact HEAD 进行 Quick review，
  并明确批准且只批准一次 V2 gate invocation。任一预检失败即停止；V2 失败也不自动重试。

## 对目标的实际推进

V1 没有产生 footprint 或速度估计，但它确认监督器能在兼容性错误时 fail-closed 且不留下运行进程。
当前不能报告 64-peak 运行时间、CPU 或峰值内存，也不能作准确度结论。此前 8-peak V3 的约
7-minute / 17.09-GiB 结果仍不可线性外推至 159,628 个 peaks。下一项有价值的进展是修复兼容参数，
完成 V2 exact-head 审核和全新预检，再由一次获批准的运行测量时间/资源。
