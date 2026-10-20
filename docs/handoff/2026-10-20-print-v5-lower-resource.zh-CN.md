# PRINT V5 降低资源后继续

## 用户目标

用户要求降低资源消耗、修改参数后继续在 Argos 上跑 K562 完整 ATAC peak 集的 PRINT footprint。范围仍是 159,628 个原始 peak、PRINT 双尺度半径 10/20、CPU-only；不做准确度排名或 motif 分析。

## V4 依据

PR #8 HEAD `fb5d04fb469e8eae755fa39f5c86c300b7eeab1e` 记录的 V4 运行使用 16 workers。PRINT caller 86.1737 秒后被 watchdog 终止；两秒间隔的进程组 VmRSS 求和从 102,668,268 kB（97.91 GiB）跳至 153,992,220 kB（146.86 GiB），超过当时 100-GiB 采样软停止阈值。五个必需 native track/event/timing 文件均缺失，没有有效完整运行时间。该数字不是任务真实内存峰值或硬限制；共享页可能在 RSS 求和中重复计数。

## V5 候选配置

- workers/CPU affinity：16 → 4。
- sampled process-group VmRSS soft-stop threshold：100 → 64 GiB。
- 保持原始 peak 集、半径 10/20、冻结输入/模型、PRINT commit、CPU-only 和不可变 Argos gate（每进程 RLIMIT_AS 44 GiB）。
- 新的日志与输出目录分别为 `/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v5/` 和 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_fullpeak_rcapps3_20261020_v5/`。

64-GiB 是采样软停止目标，不是 enforceable task-wide cap；采样间仍可能超出，VmRSS 求和也有计量局限。降低 worker 和阈值是资源控制试跑，不预先声称会成功或完成时间。V5 尚未运行。

## 审核与执行门

变更保留在同一个 OPEN PR #8，不合并。须把此代码、handoff、worklog 和当前精确 PR HEAD 提交到用户指定的固定 PMA 项目审核对话，获取 exact-head L1/L2 `APPROVE` 和明确的一次 V5 执行授权。审核通过后才可做新鲜 Argos 资源/输入 hash/R 依赖/输出路径/无活动进程预检，并经不可变 gate 启动一次。预检或运行失败均保留日志并停止，不自动重跑。

## 限定范围

不处理 ChIP BED6/PR #7，不运行 HINT、TOBIAS、TraceBIND 或其他 caller，不评估准确度，不发现 motif，不优化 PRINT 算法，不合并 PR。
