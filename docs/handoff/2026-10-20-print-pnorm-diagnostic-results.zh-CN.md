# PRINT pnorm 诊断结果交接 — 2026-10-20

## 范围与执行

仅在 Argos `rcGPUs` 对既有 PRINT V5 八个 K562 peak 缓存做了一次只读评分重放，用来定位此前验证中出现的 `pnorm(...): NaNs produced`。没有重建 BAM/fragments/counts，没有扩增 peak，也未修改 PRINT 评分、历史 track、event 或缓存。固定 PMA 项目对话批准了精确 HEAD、stage 集合和一次 gate 调用；本次 fresh preflight 通过后执行一次，one-shot 已消耗。

- Gate ID：`BG_K562_PRINT_PNORM_DIAG_20261020_V1`
- Gate：`EXIT=0`，开始 `2026-10-20T14:43:26-04:00`，结束 `2026-10-20T14:43:58-04:00`，墙钟约 32 秒。
- 执行：单个已允许 CPU；已知 BLAS/OpenMP 线程数设为 1；CUDA 禁用；gate 设置每进程 `RLIMIT_AS=44 GiB`；没有记录 RSS 峰值，不能报告实际峰值内存。
- 结束后未发现仍运行的诊断进程。

## 可核验观察

128 个评分上下文 = 8 peaks × 2 radii × 2 scorer paths × 2 replay passes × 2 flanks。

- 28 个上下文调用报告 pnorm warning；这与历史 V5 的数字相同，但历史 warning 的路径/分组上下文不同，不能据此声称重现了历史 warning。
- 记录了 292 条异常位置记录；全部预测标准差为负，`pnorm` 结果为 `NA`，原生零覆盖 mask 均为 FALSE。未知 mask 为 0；未分类 warning 为 0。
- 重放的 before/after 输入哈希相同。诊断代码断言并通过 16 个原有 peak-radius 比较（16 个 exact-bias-match）和 r10/r20 native-event 数 14/17；原有输出未改写。
- 当前回放门禁为 `BLOCKED_UNMASKED_ANOMALY`；全量门禁为 `BLOCKED_HISTORICAL_CONTEXT_NOT_REPRODUCED`。

这说明当前评分上下文里存在“负预测 SD → `pnorm` NA → 未被 mask 排除”的真实异常。它不能单独证明历史最终分数如何处理了这些值，也不能证明 footprint 的生物准确度。不要 clamp SD、隐藏 warning、改写既有输出或扩增数据。下一步先在固定 PMA 项目对话请 GPT 判断负预测 SD 的合理来源与最小可证伪检查；在得到方法建议前，不做评分语义修订或新的数据运行。

## 外部证据（均不入库）

- 结果目录：`/data/sysdir/home/zz950/PMA_fetch/pma_print_pnorm_diagnostic_rcapps3_20261020_v1/`
- gate status/meta/stdout/stderr：`/home/zz950/PMA_fetch/pma_bg_pr8_20261019/BG_K562_PRINT_PNORM_DIAG_20261020_V1.*`
- manifest SHA-256：`57d682f4de5509c0565295e8480a6317c6d137c386bfff57c6754bd5e3b9573b`
- `pnorm_calls.tsv` SHA-256：`3e9927019696584d8de748ccb7c6d779cafd67b17e80405636b8bd927d06d37c`
- `pnorm_positions.tsv` SHA-256：`da87a0cc19026b55f28ae78a4b895ca267c4d0d789da643eef0f606e978b4dfc`
- Remote gate status: `EXIT=0`; gate consumes one-shot. No retry authorized.

## Review-task checkpoint

- L1：诊断交付、输入完整性和基线断言 PASS。
- L2：BLOCKED；异常未被原生 mask 排除，且没有重建历史 V5 warning 上下文。
- L3：用户接受待定；没有准确度排名、全 peak PRINT 结果或扩大运行许可。
- 对目标推进：获得了 PRINT 真实数据评分的明确工程异常证据；当前没有可报告的生物准确度结论。
- 下一验收：固定 PMA 对话对上述结果和解释方案作一次阶段评审；继续工作前要有可验证的机制说明或可证伪测试设计。
