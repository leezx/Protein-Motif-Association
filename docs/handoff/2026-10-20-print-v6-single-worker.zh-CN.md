# PRINT V6 单 worker 低资源候选

## 用户方向

用户要求降低资源消耗、改参数继续，目标是在 Argos 上得到一个样本完整 ATAC peak 集的 PRINT-only、无 motif footprint，并实际报告时间与资源。仅处理 footprint/PR #8，ChIP BED6/PR #7 由 Claude 负责。

## V5 证据与下一参数假设

V5 已在PR #8中记录并经固定PMA审核。完整159,628 peaks、radii10/20、4 workers运行；caller 74.6396秒后因64-GiB sampled VmRSS soft-stop被SIGTERM，gate EXIT=124。最大有效采样进程组RSS求和122.38 GiB；五个结果/阶段计时文件均缺失。该值不是实际任务峰值或硬限制；V5尝试授权已耗尽。V4的16-worker尝试也在100-GiB软阈值处失败。

V6 的可检验假设：V4/V5观察到的快速高RSS增幅可能与并行workers有关。将workers从4降到1，并把采样软停止设为40 GiB，可能减少同时存在的worker内存；这是假设，不能保证结果或内存上限。按固定运行许可，本次仅改变worker数、软停止阈值、唯一run/output路径与相应配置元数据，保持完整峰集、radius10/20、输入/模型/PRINT版本和CPU-only。

## V6 配置与路径

- 节点：`rcapps3`，CPU-only，不用Mac/GPU/QSUB。
- 数据：K562 `ENCSR868FGK`，原始159,628条 `ENCFF993BAP.bed.gz` peaks。
- Caller：PRINT only，radii10/20，1 worker/CPU affinity。
- 软停止：采样进程组VmRSS总和40 GiB；不可当作硬任务内存上限。immutable Argos gate仍是每进程RLIMIT_AS 44 GiB。
- 外部日志根：`/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v6/`。
- 外部输出：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_fullpeak_rcapps3_20261020_v6/`。

## 门禁

V6 尚未远端预检/启动。代码和记录保留在同一个OPEN PR #8，不能合并。必须由固定 `PMA｜固定阶段审核` 对话对当前 exact HEAD 做 L1/L2审查，并明确批准一次V6尝试；只有全部 fresh resource/path/hash/dependency/process checks通过后，才经不可变gate启动一次。任何预检或运行失败保留证据，不重跑。此候选不授权准确度、motif、其他caller、优化、安装、ChIP/PR #7或合并。
