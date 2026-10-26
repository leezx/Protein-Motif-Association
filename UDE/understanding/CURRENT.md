# Understanding：已确立、证据、假说与缺口

**版本：UNKNOWN。** 没有独立接受的人类 UDE Understanding 版本；本页只做来源分类，不表示任何科学结论已被批准。ID 用于以后做变更影响分析。

## 1. 已确立的项目定义

| ID | 内容 | 来源 |
|---|---|---|
| U-01 | 创始问题：能否用可校准统计和可复现占据证据，系统绘制并量化人类染色质相关蛋白组的 protein–motif genomic association？ | [章程](../../docs/PROJECT_CHARTER.md) Part 1；[冻结 v0.2](../../design/PMA_pseudo_figures_v0.2.md) |
| U-02 | 两个互补估计目标：genomic association（相对匹配背景的富集）与 protein-specific association（同一 biosample 内相对其他蛋白的特异性）；二者不可互相替代。 | 冻结 v0.2 §一 |
| U-03 | 边界：这是 association reference，不是 recruitment-mechanism 研究。Non-goals 包括 recruitment grammar、perturbation、ASB 作为主要验证、ChIP-exo/nexus、RARB 主图、绑定 CancerRegAtlas、把重处理原始 ChIP 当创新、Fig. 3+（在结果证明前）。 | 章程 Part 1 non-goals |

## 2. 已报告的工程证据

下列数值均来自仓库文档的**报告**，本索引未重跑或独立复核；引用时保留"报告"限定。

| ID | 报告内容 | 来源 |
|---|---|---|
| E-01 | Step 1 pilot：Codebook 2026（1,685 PWM / 1,421 TF）与 JASPAR 2026 CORE vertebrates non-redundant（1,019 motifs）；759/762 JASPAR 人类 TF 被 Codebook 覆盖；同 TF motif 匹配率 66%（q<0.05 时 105 个无匹配）。 | [Step 1 结果](../../docs/STEP1_MOTIF_PILOT_RESULTS.md)；[Figure 1 结果](../../Figures/Figure1/Figure1.motif_reference.result.md) |
| E-02 | motif v0.3：472,964 条 raw records → 211,457 条通过 QC → 211,431 个可聚类节点 → 101,228 个 unique motif（99,133 单体 + 2,095 复合）→ 24,194 个 core motif。500/1,000/2,000 hub 分别覆盖 66%/79%/90% core，N-challenge 同簇率 <2%；剩余问题为 19–25% hub 两两高度相似。 | [Step 3b 设计](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md)；[Figure 1 结果](../../Figures/Figure1/Figure1.motif_reference.result.md) |
| E-03 | Step 4a：39,099 个 in-scope ChIP-Atlas 实验（38,566 SRX / 312 ERX / 221 DRX），MACS2 q<1e-5；38,795 个实验有峰，443,029,514 行，0 行被拒。构建记录称 2026-10-17 23:14 built，closure check 未完成。 | [Step 4a 设计](../../docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md)；[CODEX_HANDOFF](../../docs/CODEX_HANDOFF.md) |
| E-04 | Step 4b 外部运行多次在 setup/smoke 前失败（gDNA chrY 索引、RGT/numpy.mat、离线 conda），**未产生 benchmark 结果**；失败记录本身不构成方法优劣证据。 | [Worklog](../../Worklog.md) 2026-10-17 至 2026-10-18 条目 |
| E-05 | 2026-10-26 观察：PR #5–#9 均 OPEN；研究分支 `task_20261019_bed6_independent_verify`、`task_20261020_chipatlas_light_bed`、`task_20261020_fpbench_v2`、`task_20261021_footprint_db_tracks`、`task_20261021_repo_data_links` 未合并。 | GitHub + `git branch -r` |
| E-06 | 外部 KB 档案 `2026-GPT-Project-PMA.md`（sha256 `ff50036f…`）是 GPT 对话记录，无仓库提交、无人类接受、无 PR 审核；其中 29,778 motif 计数早于 v0.3 结果。 | 文件指纹 + [设计层](../design/CURRENT.md) §2 |

## 3. 工作假说（全部未验证）

| ID | 假说 | 来源 | 状态 |
|---|---|---|---|
| H-01 | 无 motif 的 ATAC footprint 能为 motif 发现和 association 解释提供增量价值。 | [Step 4b 设计](../../docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md) | 未证明；benchmark 未产生结果 |
| H-02 | 以固定 hg38 区域为行、持续叠加注释的 locus-centric reference，比 motif-centric 数据库更能解释"某个位置的 DNA recognition 证据"。 | KB §PMA Human Regulatory Region Reference；§saturation | 提案；未做可用性/统计比较 |
| H-03 | DNA recognition pattern 相对保守，但读取这些 pattern 的蛋白网络高度依赖细胞状态（癌症情境）。 | KB §genome biology架构 central hypothesis | 提案；未检验 |
| H-04 | 现有 ChIP-seq 覆盖在 genomic / protein / cellular context 三层接近饱和。 | KB §PMA整体重大进展 | 未检验；原文亦承认定义困难 |
| H-05 | 代表 motif 压缩（500/1,000/2,000 hub）保留主要生物学结论。 | [Step 3](../../docs/STEP3_MOTIF_CLUSTERING_DESIGN.md)；KB §6 | 部分报告（core 覆盖率），缺 full-raw vs representative 下游 benchmark |
| H-06 | 多模型 Tn5 bias annotation 比流程内预校正提供更多可解释的不确定性。 | KB §PMA的footprint部分重大创新 | 提案；与 D-04 语义冲突 |

## 4. 未知与待决问题

| ID | 问题 | 影响 |
|---|---|---|
| Q-01 | Step 4a 的逐实验峰产物（D-03）与 PR #6–#7 的坐标唯一 BED6（D-05）应接受、替换还是并存？ | 阻塞 Step 4a closure 与后续 association 输入 |
| Q-02 | Step 4b/4c 的工具排名、调用范围和 atlas 层定义是否足以支撑交付？后续分支结果未审。 | 影响 D-04 与 footprint 证据是否可用 |
| Q-03 | 关联统计框架、跨实验/样本复现与证据分级的正式设计与验收尚未建立。 | 章程列为 Immediate next step，是 100% 的关键路径 |
| Q-04 | 若采纳 region-centric 模型，region 如何定义、如何避免跨边界重复计数、如何匹配背景？ | 决定 P-01 是否可行 |
| Q-05 | pan-cancer、BAF case study、DBD–motif、DL 模块是 PMA 的一部分，还是独立项目？ | L3 范围决定；影响 Fig. 3+ 与章程 non-goals |
| Q-06 | 原 checkout 中未跟踪的 `Figures/`、`benchmark/`、`design/protein_binding_resources.md` 归属、来源与数据边界由谁确认？ | 影响证据可用性与仓库边界 |
| Q-07 | Step 4a 的"built"与"closure check pending"之间的验收标准是什么？ | 影响 X-01 能否算完成 |
| Q-08 | 项目进度以哪个数字为准：Worklog tracker 20%、CODEX_HANDOFF 33%，还是重新核算？ | 影响对外报告，不影响科学验收 |

## 5. 明确不提升为事实的材料

- KB 中的 29,778 motif 计数（历史值，与 v0.3 的 101,228 unique / 24,194 core 不一致）。
- "region-centric 更有价值"、"ChIP 覆盖接近饱和"、"pan-cancer 是规模优势"等判断，均为对话中的论证，不是本项目已获得的证据。
- `design/protein_binding_resources.md` 在原 checkout 中为未跟踪文件，未移入本层，也未提升为已接受知识。
