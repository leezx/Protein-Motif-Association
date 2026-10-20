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

## 固定 PMA 结果复核（2026-10-20 14:52 EDT）

固定 `PMA｜固定阶段审核` 对本次结果记录给出 `APPROVE`：L1 仅对有界诊断执行/完整性 PASS，L2 BLOCKED，L3 等待人类验收。该批准不涵盖修改评分方法、再次读取 Argos 模型/缓存或后续运行。用户另行授权了本地 PRINT 源码修改。

复核者检查了官方 PRINT 固定提交 `8dad7317c3a640454a191dba2acd138e6edc54ac`：dispersion predictor 的隐藏层为 ReLU，输出层为无约束线性层；反标准化的 SD 未作非负约束就传给 `pnorm`。所以模型结构允许预测负 SD，但这还不能证明 292 条异常的具体来源。特征顺序、标准化、模型导出及前向计算须用选定缓存样本重建核对。PRINT 的原生调用会将 `pnorm` 的 NA p 值替换为 1，使这些位置在调用结果中成为最不显著/背景值；这不会让底层概率计算变得有效。

下一项可证伪检查：先查已有历史日志的 warning 上下文映射，不为重现数字 28 而重复八 peak 重放。若之后获准进行一次只读缓存核验，选同一 peak/radius/flank 内一个负 SD 位置及相邻有效位置，记录五个原始特征、标准化特征、模型身份/哈希、输入与目标顺序、缩放参数、模型原始输出与反标准化结果、峰边界距离、左右插入数和原生 mask；检查这些量能否在声明容差内重建负 SD。不得 clamp SD 或改变评分。未对照训练特征范围前，不称其为分布外。292 是跨上下文重复记录，不是 292 个不同基因组位置。

目前只把机制缩小到“无约束输出允许负 SD”，异常根因、准确度排名和全 peak 可用性仍未解决。任何后续远端缓存读取或计算都需要固定 PMA 对话中的新精确范围及一次性授权；原诊断 one-shot 已消耗。

## Review-task checkpoint

- L1：诊断交付、输入完整性和基线断言 PASS。
- L2：BLOCKED；异常未被原生 mask 排除，且没有重建历史 V5 warning 上下文。
- L3：用户接受待定；没有准确度排名、全 peak PRINT 结果或扩大运行许可。
- 对目标推进：获得了 PRINT 真实数据评分的明确工程异常证据；当前没有可报告的生物准确度结论。
- 下一验收：只观察、不改评分的前向计算审计候选已加入本地诊断器：捕获标准化五特征、权重张量、隐藏层/ReLU、标准化输出及反标准化；每个负 SD 调用配一个最近正 SD 对照，并核对重建值与 `pnorm` 收到的参数。脚本 SHA-256：`8faca52a9bd02ff378190a20fd4768347a705438ac1a071b6b1d9fe532c1b165`。代码尚未执行、测试或远端暂存。当前 PR 精确版本先经固定 PMA 复核；之后另行申请一次只读 Argos 缓存核验，确定负值首次出现的步骤。若输入/标准化/权重不能对齐，维持 L2 BLOCKED，不更改评分。
