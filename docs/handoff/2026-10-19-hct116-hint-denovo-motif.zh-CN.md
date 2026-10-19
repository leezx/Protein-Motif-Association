# HCT116 HINT motif 与 K562 TOBIAS 里程碑

## 最新状态 — 2026-10-19 15:22 EDT — 更正已推送，交接同步同 PR 进行中

PR #8 仍 OPEN。固定 PMA 对话 `PMA｜固定阶段审核` 对前一 HEAD
`25343902cd2618fff8fbea37e32b80d2ea3ef1f8` 返回 `REQUEST_CHANGES`；同一 PR 更正提交
`e1b99cf` 已推送，修复三项文档问题，并明确 B1 的确定性 QNAME-hash 深度匹配、事件 ties、
inclusive cutoff、21-bp NMS 和 fold territory。当前这份交接状态同步正在加入同一 PR；随后会在
固定对话请求完整新 tip 的 exact-head 审核。准确度排名仍不可计算：HCT116 ChIP 来源/生物学重复
未确立，四工具共同连续 score 也未建立。没有 Argos、数据访问或分析运行，没有修改环境、PR #7
或合并。下方较早条目是历史状态快照。

## 最新状态 — 2026-10-19 15:20 EDT — 固定 PMA 审核指出的文档问题正在同一 PR 修复

PR #8 仍 OPEN，远端 HEAD 为 `25343902cd2618fff8fbea37e32b80d2ea3ef1f8`。固定 PMA 项目对话
`PMA｜固定阶段审核` 对该 exact HEAD 返回 `REQUEST_CHANGES`。本轮仅在同一 PR 修订方法与交接文档：
把四工具 leader 写成候选工具相对其余三者的区间判断，同时保留六个配对比较的校正族；修正裸
gDNA 可有 Tn5 插入/切割、但没有蛋白保护 footprint 真值的表述；并冻结 B1 的 score tie、平台峰值、
inclusive cutoff、21-bp NMS、折内 territory 和 QNAME-hash 深度匹配规则。

当前这些更正仍在本地，尚未进入 GitHub。文档本身不构成分析：没有 Argos 任务、数据读取/下载、
环境变更、评分或合并；准确度排名、tool winner 和癌症全局结果仍不存在。下方 15:15 及更早章节是
当时状态快照，由本节覆盖。接下来完成 Worklog/CODEX_HANDOFF 同步、检查差异、推送同一 PR，并仅在
固定 PMA 对话请求新 HEAD 复审。

## 2026-10-19 15:15 EDT — 固定 PMA 审核会话的技术反馈已落实到同一 PR

PR #8 HEAD `069d5ccd4de99888f8fac29b93e1f1b0dd7b9ecf` 在固定 PMA 项目对话
`PMA｜固定阶段审核` 收到 `REQUEST_CHANGES`。随后在同一对话询问的统计细节已澄清：spike-in
只有在加样量、加入时点、IP 与 input 各自的 exposure 解释明确时才能用于校准；DESeq2 未收缩
交互项可用预设阈值 Wald 检验分别判定 depletion 与等效保留；不能把 edgeR QL 和未经验证的
Wald CI 拼成同一个推断方案；AP 排名采用同步区块 bootstrap，不做 score-vector swap；B1 应称
naked-DNA false-event density 而不是传统 FPR。本次已在同一 PR 的本地未提交 §4 修订中记录这些规则、
context/embargo 要求和效应区间稳定性门槛；旧的 edgeR/QL、block-swap、Holm 与 2,000 次 bootstrap
描述均为历史。

这仍只是可供审核的协议修改。HCT116 CTCF ChIP 文件/来源、足够的独立生物学重复、可解释的
spike-in、四工具共同的连续分数及严格折外执行均未建立，因此没有标签、AP、准确度排名或工具赢家。
没有 Argos 访问、数据下载、caller 计算、评分或合并。下一步核对这次同一 PR 文档 diff、更新 PR
说明，提交后在该固定 PMA 对话请求当前 exact HEAD 复审；不碰 Claude 负责的 PR #7。

## 2026-10-19 15:07 EDT — 同一 PR 的协议修订已准备复审

固定 PMA 项目对话中的 PR #8 HEAD `c5bf88f365a3e10f1cdf3ad7714f2df94518da17` 审核要求继续
补足标签、score adapter、held-out 拟合边界和配对推断定义。本轮在同一 PR 文档中加入了
可执行的 ChIP-IP/input 差异模型、当前工具 wrapper 的分数来源与可评分状态、共同 mask 限制、
训练折内适配和百分位映射、bootstrap/permutation/Holm，以及 B1 事件提取规则。`git diff
--check` 通过。当前 HANDOFF 仍表明缺少所需 ChIP 生物学重复/输入/spike-in 文件；HINT 和
TraceBIND wrapper 当前也没有可供统一 AP 的连续轨。因此准确度排名和赢家仍不可计算。
下一步只提交并推送同一 PR #8，在固定 PMA 审核对话请求新 HEAD 的 exact-head review；未获
批准和人类阶段接受前不启动 Argos 依赖分析，不触碰 PR #7，也不合并。

## 2026-10-19 15:03 EDT — 第二次 exact-head 反馈与协议细化

固定 PMA 对话 `PMA｜固定阶段审核` 审核 PR #8 HEAD
`c5bf88f365a3e10f1cdf3ad7714f2df94518da17` 后再次给出 `REQUEST_CHANGES`。本次审查只读
GitHub 和指定仓库文档，没有访问 Argos、下载/读取实验数据、运行分析或改环境。剩余方法
缺口：IDR/peak strength 与 coverage 的定义、跨条件 ChIP 的 calibrated normalization 和
差异统计；逐 caller score adapter 与共同可评分集合；拟合/归一化是否跨入 held-out fold；
AP 差值 CI、配对检验、Holm、阈值 ties 和 B1 事件定义。

同一 PR 的 §4 已进一步固定：仅用 ENCODE IDR≤0.05 的生物学重复共识峰；从 narrowPeak
列10取 summit、列7取 signalValue，按 hg38 chrom.sizes 加稳定来源 ID 去重；共同 ATAC
可调用 mask 取两个条件 ENCODE IDR peak union 减 blacklist。occupancy 变化采用 edgeR
quasi-likelihood NB 的 `~ replicate_pair + condition + assay + condition:assay` 模型，
以匹配 input 与外源 spike-in 校正，BH 在冻结的 coverage-eligible 候选全集上；depleted
需要 log2FC、BH q 和 95% CI 同时过线，retained 用 treatment IDR 支持及 90% CI 等效检验。
没有至少三个独立生物学重复对、matched input、spike-in 或通过的模型诊断则停止标签生成。
PRINT 采用当前 wrapper 的 r10 per-base aggregateScores；TOBIAS 采用默认
FootprintScores 连续轨；HINT 与 TraceBIND 当前 wrapper 只导出阈值事件，不能进入主 AP，
除非另行实现并冻结连续输出适配器；四工具若不共用完整可评分位点则不得宣布四工具赢家。
每折数据适配限于训练块、held-out 分数按训练分布百分位归一；block bootstrap 用有效样本
规则，另设预先固定的双侧 paired block-swap permutation 与 Holm 校正。新修订只定义方案，
不代表任何准确度排名或工具赢家。待同一 PR 提交后仍只在此固定 PMA 对话请求复审；未获
APPROVE 前不做依赖评分/Argos 运算，不碰 Claude 的 PR #7，不合并 PR #8。

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
