# HCT116 HINT motif 与 K562 TOBIAS 里程碑

## 2026-10-19 14:58 EDT — §4 细节补齐，等待固定 PMA 会话复审

根据固定 PMA 项目审核对 PR #8 HEAD `98819830e4e302c6d96148f365a2a52f9c229e74` 的
`REQUEST_CHANGES`，在同一个 PR 细化准确度协议：hg38 候选位点 tie-break 明确引用冻结的
`chrom.sizes` 顺序及稳定 peak ID；五折 hash 明确使用 block 的 0-based 起点；相邻 1-Mb
block 被分到不同 fold 时在两侧各排除 50 kb，减少邻近序列/上下文泄漏。设计文档明确
2026-10-17 的旧批准不覆盖本次 §4 实质性修改，当前 HEAD 必须重新审核。更新仍只是方案，
ChIP 文件/标签未取得、未评分、无准确度排名或赢家。所有后续 GPT 审核继续使用唯一的
`PMA｜固定阶段审核` 对话；不启动 Argos 计算、不触碰 PR #7、不合并 PR #8。

## 2026-10-19 14:55 EDT — exact-head 方法审核与只读 ChIP provenance 核验

PR #8 在审核时为 OPEN，HEAD `98819830e4e302c6d96148f365a2a52f9c229e74`。固定 PMA 项目会话
`PMA｜固定阶段审核` 对此 HEAD 返回 `REQUEST_CHANGES`。要求修正：共同候选空间与正/负/模糊 ChIP 标签；阈值前连续分数、score-to-site 规则及未调用/不可评分状态；1-Mb held-out 分块、固定 primary AP 和六组比较的校正；TraceBIND 自有 HCT116 benchmark 不可称独立验证；PR body 描述和旧 B1-first 规则也需同步。

该审查只明确批准了对 Argos 上**现有文件**做只读 provenance 核验，没有批准下载、运行分析或自动启动评分。只读检查：

- `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-19/encode_hct116_unfiltered/ENCSR328JGW_ENCSR260SWI/` 中有四个已验证的 unfiltered ATAC BAM 和 `MD5SUMS.encode.tsv`。
- 在搜索过的 PMA `raw/`、`processed/` 子树中未找到 `ENCSR059BCO`（未处理 CTCF ChIP）或 `ENCSR160GVO`（auxin CTCF ChIP）的文件/manifest。ATAC 清单不是 ChIP 真值凭证。
- Argos 当前无 footprint 任务运行；未下载文件、未读取或生成峰、未计算 footprint 分数。

据此，本地准确度标签尚不存在，不能算 AUPRC，也不能选准确度赢家。方法修订已明确这只是 HCT116 CTCF degron 的局部 retained-vs-depleted 检验：所有 candidate 均为控制条件 ChIP 共识峰，固定 control summit ±50 bp；depleted 要求 auxin/control ChIP log2FC ≤−1 且 FDR≤0.05 并有足够覆盖，retained 要求处理后有重复支持且 log2FC>−0.5，其余标为 ambiguous。所有决定必须经 provenance/replicate/QC 确认后，且先于 caller 分数。该窄目标不能代表全基因组、无 motif 总体准确度或泛癌赢家。

本次只修订现有 PR #8 的协议、handoff、审计记录和 PR 描述，完成后在同一固定 PMA 审核会话请求新 HEAD 复审。依赖性准确度评分、PRINT/TraceBIND 重跑和癌症 ATAC 全局运行继续暂停；不处理 Claude 负责的 BED6/PR #7，不合并 PR #8。

时间：2026-10-19 14:20 EDT
工作区：`/tmp/pma-hint-smoke`
PR：#8，更新前 HEAD `361e6589ce4cab9e88b381758836ea4c2bf08532`（OPEN）

## 结果

### K562 TOBIAS 速度任务

Argos 任务 `BG_K562_TOBIAS_SPEED_V1` 于 14:05:48 EDT 退出 0。固定输入为 ENCODE `ENCSR868FGK` BAM 和 77,668 个固定 1-kb 窗口。任务记录的片段数为 110,891,807；独立 read count 是 110,891,952，计数条件略有不同，最终速度归一化前需统一过滤谓词。

| 阶段 | 时间 |
|---|---:|
| ATACorrect | 2,827 秒 |
| FootprintScores | 834 秒 |
| 事件轨道转换 | 75 秒 |
| 全任务 | 1:02:16 wall |

GNU time 最大 RSS 为 1,267,312 KB。输出 3,319,912 个事件，events BED SHA-256：`de8267471ad662be0122662d903e5b3cfb01e578690536eec1c7ad358c67e178`；footprints bigWig SHA-256：`970835ad182d020f1e5485288236c851a3096b5d2e07c47bf15dd7440787326b`。K562 的 ENCODE 记录有 NFR QC 警告，所以这个样本只作时间测量，不作准确度真值。HINT 使用 32 分块、TOBIAS 使用 16 cores，原始 wall 不能直接选速度赢家。

### HCT116 HINT→STREME

ctrl 和 aux 任务分别于 14:08:43、14:07:44 EDT 退出 0。每组从最高分 HINT footprint/窗口提取 50-bp 序列，并与同一窗口、GC 差不超过 0.1 的背景配对；背景排除模式为 `selected_only`。配对数 ctrl/aux 为 90,387 / 88,444。两组 STREME 都报告 10 个 motif 且各 E<0.05。

- ctrl 输入 HINT events SHA-256：`ea2b730c79e82637a63bf18f0493b689d3ad40f8f6c81b011ebeaee8660225d`
- aux 输入 HINT events SHA-256：`eb08834325ee1119b832f2f0bc132bfa26a9b726511fc77149812500127eb517`
- ctrl STREME 文本 SHA-256：`7d1085d2fd3ace2a61bef448606d2fbc5d60ff2959f0d12911e9d523a6a32804`
- aux STREME 文本 SHA-256：`9085a2c4a06f135ad774dd04be5441dd99ca50d2e92d0d93eb22f9c09e089180`

这只是探索性 HINT motif 结果。`selected_only` 背景可能包含其他 HINT 事件，因此富集会受影响；E-value 不证明准确度、TF 身份、独立复现或 CTCF 降解响应。不得据此发布 motif reference 或认定 HINT 为赢家。

## 阶段判断与后续

- L1：任务退出码、输入/输出和哈希可核验；通过。
- L2：准确度排名与公平速度比较仍阻塞。尚无留出 ChIP AUPRC、匹配灵敏度 B1、扰动 B2 或正交 B3。
- 方向：结果对旧的 footprint→motif 路线有帮助，但 HINT motif 探索先于工具赢家选择，偏离用户当前的 accuracy-first 优先顺序。
- 真实进展：HINT 在两种 HCT116 条件下产生可复现保存的候选 motif 输出；没有工具赢家或广泛癌种结论。
- 持久 GPT 对话目前仍显示旧 PR #6 请求及 `systemError`；PR #8 当前 exact-head review 和人工阶段接受均未获得。

在 PR #8 当前 HEAD 获得审查、且人类接受阶段结论前，不启动依赖性准确度评分、全 TraceBIND 校准、PRINT 重跑或癌症 ATAC 全局新运行。放行后优先验证独立 HCT116 CTCF ChIP 标签，并按冻结共同位点集执行分块留出 AUPRC、B1–B3。所有分析产物均留在 Argos 外部目录；仓库仅记录摘要、参数与校验哈希。
