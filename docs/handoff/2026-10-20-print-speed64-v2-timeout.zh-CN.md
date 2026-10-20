# PRINT 64-peak V2 运行记录

时间：2026-10-20 12:20 EDT  
范围：仅 PMA Step 4b footprint runtime；PR #8。ChIP BED6/PR #7 由 Claude 负责，不在本次范围。

## 运行结果

固定 PMA 项目对话批准了一次 exact-head V2 gate 调用。作业 `BG_K562_PRINT_PEAK_SPEED64_20261020_V2` 于 11:47:51 EDT 启动，外层监督器在 12:17:53 EDT 按 1,800 秒总预算结束，gate `EXIT=124`。PRINT caller 收到 TERM，退出码 -15。60 秒清理窗口内完成登记进程组清理；外层记录 `cleanup_survivors=[]`，之后只读进程检查也没有匹配进程。不得重跑 V2。

输入为冻结 K562 ENCSR868FGK IDR peak BED 的 64 个 midpoint-quantile 原始行，共 159,628 行中抽取 64 行；未修改区间。抽样区间总长度 62,211 bp，宽度 min/median/max 为 242/954/2,184 bp。PRINT 使用两个 CPU worker、radii 10/20、生产 chromosome-wise bias 路径。每进程 `RLIMIT_AS` 为 44 GiB，监控的进程组 `VmRSS` 软停止线为 40 GiB。

## 计时和资源

- Outer end-to-end：1,801.31 秒，触发 1,800 秒预算。
- gate 内置 preflight：89.77 秒；selector：0.84 秒。
- PRINT caller 在 TERM 前运行 1,710.18 秒（约 28 分 30 秒）。
- 进程组采样峰值 `VmRSS`：17,918,696 KiB，约 17.09 GiB。此值是近似采样值，不是硬性 aggregate 内存上限。
- GNU time 因 caller 被外部 TERM 后未正常结束，没有输出最终 CPU 时间或 GNU-time max RSS；不推算缺失指标。
- caller 日志记录 105 次评分调用完成、106 次开始，最后一次未完成。

此前已完成的 BAM→fragments 预处理耗时 28:18.88、约 4.00 GiB max RSS。V2 重用冻结 fragments，因此这段时间没有计入本次 30 分钟；从原始 BAM 到最终 track 的端到端计时需另行加上一次性预处理成本，但 V2 没有生成最终 track。

## 产物与结论

V2 没有生成 `print.r10`/`print.r20` tracks、native event BED 或 timing TSV。输出目录仅有中间 count tensor。故 64-peak footprint 作业未完成；本次只说明当前按 variable-width groups 的 PRINT 路径在两 worker 下超过 30 分钟预算。不能将部分评分调用当作完整 footprint 结果，也不能从中给出准确度或可靠的全峰运行时间估算。之前 8-peak V3 smoke 是唯一完成的 PRINT track：gate wall 424.117 秒、进程组采样峰值约 17.09 GiB；样本过小，不宜线性外推到 159,628 个 peak。

## 证据位置和 SHA-256

所有大数据、日志和结果均在 Argos/DATA 外部路径。运行证据根：

`/home/zz950/PMA_fetch/pma_print_peak_speed_rcapps3_20261020_v2/`

gate 记录在 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`，输出目录在
`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_peak_speed_rcapps3_20261020_v2/`。

| 文件 | SHA-256 |
|---|---|
| `summary.json` | `54761e2c7a0c3345d5d7c5d5501a54cd665606ab6c803f59a81416aebc54ceb6` |
| `outer_supervisor_summary.json` | `a1269cf84913fa8dbb9e4a903435028a6f293cc30045893726b0feee2f0ec92d` |
| `selection_summary.json` | `3c48c20de1fe4dba44e8f0a09dab75e6d236bd8baf0fab912121c03c7a13025f` |
| `runlogs/caller.stdout` | `78d151b3e449390c9275511b1eb5bab3f13739f27fe17ddcae2ddbda785b83b2` |
| `runlogs/gnu_time.stderr` | `f954490da1ee122bf1a78a245a97bcb2e95a064b46ea0a73275decc5a53efe61` |
| `watchdog.jsonl` | `8c0919db154a03ad759584619b9e9ae6c85127b74f63382fa0d8b1ebfd2e86d8` |
| selected BED | `5544df4ff88d483f0aa875a0ac805e7123404ff82f59cd21947b76e7e59de325` |

## Stage review and next action

- L1: FAIL for the expected complete sample track; timeout cleanup behaved as intended.
- L2: BLOCKED for accuracy and genome-wide runtime.
- L3: ON TRACK as a bounded diagnostic, PARTIAL progress. The 64-peak workload exceeds the 30-minute budget under this implementation/configuration; the sample did not finish and has no track.
- Recommendation: HOLD tool selection and full cancer ATAC calling. Ask the fixed PMA project conversation to review this milestone and recommend the smallest viable next runtime measurement. Do not start another compute attempt, optimize code, change environments, or merge PR #8 without a fresh exact-head review and explicit run approval.

HUMAN DECISION: PENDING
