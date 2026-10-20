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

固定 `PMA｜固定阶段审核` 对 exact PR #8 HEAD `f54d31c6f7dc39e52eda3f21aaf099b03928e303` 给出 L1 无阻塞、L2 限制保留，并明确批准一次V6单次尝试。审核专门确认通过 `rcapps3.dfci.harvard.edu` 登录后远端自报 `rcGPUs.dfci.harvard.edu` 仍属于此次批准范围。fresh preflight 全部通过：远端 x86_64、CPU affinity 0–71、MemAvailable 969,416,036 kB、R 4.2.2/依赖可用；BED 行数159,628；BED/fragments/bias/model/PRINT source/runner/supervisor/immutable gate 哈希与审核值匹配；PRINT checkout clean；唯一V6输出路径不存在且无匹配任务。supervisor 与 R runner 被复制到外部唯一目录后，immutable gate `BG_K562_PRINT_FULLPEAK_20261020_V6` 于08:08:06 EDT启动一次。

截至08:18 EDT，PRINT在单CPU上活动；最新有效采样进程组VmRSS约26.3 GiB，仍低于40-GiB采样软停止，且近期采样稳定。尚无输出文件，不能宣称取得结果、完整耗时或实际峰值内存。单worker可能抑制并行内存，但不能证明因果，也可能延长运行。40-GiB为采样软停止，44-GiB RLIMIT_AS为每进程限制，均非任务组硬内存上限。继续只读监控当前这一次gate；不得重跑。完成后将核验exit/status、四阶段时间、track/事件行数与校验、GNU-time资源统计、watchdog最大有效RSS采样和无残留进程。

## 2026-10-20 08:34 EDT — V6 terminal result: variable peak widths break bias matrix assembly

A fresh read-only Argos check confirmed `BG_K562_PRINT_FULLPEAK_20261020_V6 EXIT=1 END=2026-10-20T08:29:05-04:00`, `stop_reason=normal_exit`, caller exit 1, and no remaining caller/gate process. PRINT failed in pinned `getPrecomputedBias()` before counts/footprint calculation: `Item 1597 has 28 columns, inconsistent with item 1 which has 100 columns`. Here `1597` is the chunk number, not a peak index: with chunk size 100 and 159,628 regions, the final chunk contains 28 regions while earlier chunks contain 100. The unchanged `getBias.R` uses `sapply()` on per-region bias slices, turns each chunk into a data frame, then combines chunk data frames. The observed mismatch is consistent with the final chunk having a different number of region columns; it does not show that peak 1597 has a 28-bp bias vector. The source peaks are variable-width, and PRINT declares/uses `regionBias` as a rectangular matrix with equal-width regions, so this failure does not by itself establish a valid variable-width input contract. This is an engineering/input-contract failure, not a biological result.

Observed resources for this failed one-worker attempt: GNU time elapsed 19:14.53, user 1096.86 s, system 31.86 s, 97% CPU, maximum RSS 26,989,772 kB (~25.74 GiB); watchdog maximum valid sampled process-group VmRSS 26,988,120 kB (~25.73 GiB), with no 40-GiB soft-stop. Preflight was 102.225 s and is not caller analysis time. No swap was used. The 40-GiB VmRSS threshold was only a sampled soft-stop, not a hard task cap. All five required track/event/timing outputs and all four stage timing rows are missing; the external output directory is empty.

Evidence paths: `/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v6/` and `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/BG_K562_PRINT_FULLPEAK_20261020_V6.*`. `summary.json` SHA-256 `fad055d28dce7cc215b4b0dfd33bc390b090fd9996a95b36b9bd2b6f64b85127`; watchdog SHA-256 `d8762843f4d6f42d3122663e0b36c9fc679aa4a2379a2def169346e965daabb9`; gate status SHA-256 `d670795260a740903f35fd5b6145b35e21b4ccbe8fd762adb40b214a00adbf27`; GNU time SHA-256 `d82eaeac0e7de39b46d11e1176584269f72ffaef355b3cdb10843549ea4396d0`.

V6's one-run authorization is consumed. Do not infer a successful runtime, footprint result, or winner from the failed attempt. No automatic retry or code change is authorized. Ask the fixed PMA reviewer to audit the record and advise whether variable-width input should be supported or the analysis contract should use fixed-width summit windows; specifically do not assume `fill=TRUE` is scientifically valid. Any V7 requires same-PR code/design review plus a new explicit single-run authorization.

## 2026-10-20 08:37 EDT — fixed-PMA approval of documentation correction

The fixed `PMA｜固定阶段审核` conversation reviewed exact PR #8 HEAD `3fa181aef66b6fac7d5217a32a44b85bc57e8889`: L1 no blocking issue, L2 finding closed. It confirmed the 1,597/28/100 interpretation is correctly described as chunk-level shape, not peak-width evidence; exact intermediate object shape remains unverified. The review did not authorize code changes, synthetic validation, remote access, or V7. No compute or remote access occurred.
