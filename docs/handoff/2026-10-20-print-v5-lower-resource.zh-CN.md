# PRINT V5 降低资源后继续

## 用户目标

用户要求降低资源消耗、修改参数后继续在 Argos 上跑 K562 完整 ATAC peak 集的 PRINT footprint。范围仍是 159,628 个原始 peak、PRINT 双尺度半径 10/20、CPU-only；不做准确度排名或 motif 分析。

## V4 依据

PR #8 HEAD `fb5d04fb469e8eae755fa39f5c86c300b7eeab1e` 记录的 V4 运行使用 16 workers。PRINT caller 86.1737 秒后被 watchdog 终止；两秒间隔的进程组 VmRSS 求和从 102,668,268 kB（97.91 GiB）跳至 153,992,220 kB（146.86 GiB），超过当时 100-GiB 采样软停止阈值。五个必需 native track/event/timing 文件均缺失，没有有效完整运行时间。该数字不是任务真实内存峰值或硬限制；共享页可能在 RSS 求和中重复计数。

## V5 实际运行配置（单次授权已耗尽）

- workers/CPU affinity：16 → 4。
- sampled process-group VmRSS soft-stop threshold：100 → 64 GiB。
- 保持原始 peak 集、半径 10/20、冻结输入/模型、PRINT commit、CPU-only 和不可变 Argos gate（每进程 RLIMIT_AS 44 GiB）。
- 新的日志与输出目录分别为 `/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v5/` 和 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_fullpeak_rcapps3_20261020_v5/`。

64-GiB 是采样软停止目标，不是 enforceable task-wide cap；采样间仍可能超出，VmRSS 求和也有计量局限。降低 worker 和阈值是资源控制试跑，不预先声称会成功或完成时间。实际结果见下文，V5 单次授权已耗尽。

## 审核与执行门

第一次 exact-head 审核对 HEAD `397736a137ea836bf769d3e65f74d9b8f3399eda` 返回 `REQUEST_CHANGES`：两个执行审计字段仍硬编码100 GiB，与64-GiB阈值不一致。已在HEAD `9a1abbd86c44179b993d99ef875446e3fa164f9d` 修正为由 `RSS_SOFT_STOP_KB` 同一常量派生停止原因后缀及summary阈值；停止行为本身未改。固定PMA对话实时复核该HEAD并批准exact-head L1/L2和一次V5尝试，限定全部fresh preflight通过后运行一次。该单次授权已消耗，V5运行结果如下；不得再次运行。

## V5 实际运行结果（2026-10-20）

- Fresh preflight 于07:50:46 EDT通过，主机 `rcGPUs.dfci.harvard.edu`/`rcapps3`、x86_64、72 CPU/affinity 0–71、MemAvailable 969,867,212 kB；冻结输入、模型、PRINT模块、gate、runner、supervisor hashes匹配；PRINT commit clean；R 4.2.2依赖检查通过；新V5路径和gate status不存在；无匹配进程。
- V5使用4 worker（CPU affinity 0–3）、全部159,628原始K562 peaks、PRINT radii10/20、CPU-only、64-GiB sampled process-group VmRSS soft-stop，经不可变gate `BG_K562_PRINT_FULLPEAK_20261020_V5`启动一次。
- Gate `EXIT=124`，07:53:54 EDT结束；caller运行74.6396 s后SIGTERM。此为停止前caller时间，不是完整运行时间。监督器preflight为112.5545 s；需与caller时间分开。
- 最大有效采样进程组VmRSS总和为128,329,172 kB = 122.38 GiB，超过64-GiB名义软阈值58.38 GiB。它不是任务真实峰值或硬上限；共享页可能重复计数，采样间也可能遗漏。每进程RLIMIT_AS仍为44 GiB，不构成任务组限制。
- 五个必需native结果文件（r10/r20 score tracks、r10/r20 event BED、timing TSV）全部缺失，四个stage timing均缺失，GNU time没有最终summary；没有得到可用footprint或完整时间基准。caller stdout只有初始化输出，结果目录为空。结束后检查无V5遗留进程。
- 外部证据：`/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v5/summary.json` SHA-256 `21facc37a7cb7b4a2925ea6fe5761e6ba7f0bec52e730654ee897b0cfcf08028`；`watchdog.jsonl` SHA-256 `5560f2fed8fcb32f89a9ada091df02db990a1ba8b8dfc222bc58317b006f1d43`；caller stdout SHA-256 `d2cc52aa85d931f3286e685ef62b26b5de2769bd991f89461a113c509a7a5cbd`；GNU-time stderr SHA-256 `e8f629642630f8bd86897752ac6beb482aff99b6268ca6888ed0fc22c0c327e8`。

结论：把worker数降到4仍没有将采样VmRSS总和控制在64 GiB软停止目标内，也没有成功产出。该配置在同一任务和当前监控路径下失败；74.64秒不能外推。V5单次授权已消耗，失败保留证据，不自动重试。

## 限定范围

不处理 ChIP BED6/PR #7，不运行 HINT、TOBIAS、TraceBIND 或其他 caller，不评估准确度，不发现 motif，不优化 PRINT 算法，不合并 PR。
