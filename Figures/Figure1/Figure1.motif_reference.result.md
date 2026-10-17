# Figure 1 result — PMA motif repertoire 的构建、去冗余与三档代表性 motif 参考

> 文档性质：内部分析结果稿（非投稿版本）
> 当前版本：v0.1，2026-10-17
> 对应图位：Figure 1C「Motif repertoire construction」（见 `design/PMA_pseudo_figures_v0.2.md`）
> 覆盖范围：Step 1 Codebook-first pilot、Step 2 多来源导入与校准 benchmark、Step 2c de novo 来源整合（raw layer v0.3）、Step 3b 相似度校准、去冗余、unique-motif 图与三档代表性 motif（进行中）
> 结果边界：本文只汇总已完成的分析。§7 的 core-set 三档仍在运行，数字会在后续版本更新。所有“match / 无 match”标签都依赖所述判定规则，不是生物学上“存在 / 不存在”的结论。

## Result overview

PMA 需要一个统一、非冗余、证据分级的 motif 参考，作为后续 protein–motif association 的“字典”。目标不是挑一个数据库作为标准，而是把体外测定（Codebook、HT-SELEX）、人工整理数据库（JASPAR、HOCOMOCO、CisBP）、ChIP 来源 motif（Factorbook、Cistrome）以及模型推断 motif（ENCODE BPNet/ChromBPNet/ProCapNet、HDMA）放在同一个坐标系里，保留每条记录的来源和证据，再压缩为可用于扫描和解释的代表集。

Pilot 显示 Codebook 几乎覆盖了 JASPAR 人类 TF（759/762），但在 motif 层面只重现约 2/3 的 JASPAR 模式，复合位点和部分长 motif 没有全长匹配，因此保留多来源 raw layer 设计。随后的 v0.2.1 raw layer 汇总 30,781 条记录（1,771 个 HGNC TF）；加入 de novo 来源后的 v0.3 raw layer 有 472,964 条记录，其中 211,457 条通过 QC 进入聚类池。

我们定义了对齐相似度 s，并用 TOMTOM 统计匹配校准出代表覆盖阈值 τ = 0.825。按 PI 指示，先对几乎相同的 motif 做去冗余（s ≥ 0.99），211,431 个聚类节点压缩为 101,228 个 unique motif（内部编号 PMU_*），所有来源记录均保留并挂在对应 unique ID 下。

在全部 unique motif 上直接做 ~500 / 1,000 / 2,000 三档聚类，得到 531 / 888 / 1,551 个簇，但 hub 只代表 7–32 % 的成员，所有档位都未通过预设质量标准。诊断表明这是结构性问题：82 % 的 unique motif 只来自单一记录（主要是 de novo），即使在 s ≥ 0.85 下贪心覆盖也需要约 26,000 个中心。PI 因此选择 core-set 方案：只从有体外/整理证据或 ≥ 2 个独立实验支持的 24,194 个 unique motif 中选 hub，其余 motif 分配到最相似的 hub 并标注代表程度。该方案正在运行。

## 1. Codebook 覆盖 TF，但不能单独代表 motif 模式

### 为什么做

在整合所有来源之前，需要先回答 Codebook 2026 这一新的大规模体外数据能否作为骨架，以及其他数据库是否仍然提供 Codebook 之外的模式。这决定了后续是只收 Codebook，还是保留多来源 raw layer。

### 做了什么

用 TOMTOM（Pearson）把 JASPAR 2026 CORE 脊椎动物非冗余集（1,019 个 motif，857 个人类）逐一比对到 Codebook 2026 的 1,685 个代表 PWM（1,421 个 TF），每个 query 单独做 BH 校正，主判定为 q < 0.01 且对齐重叠 ≥ 较短 motif 的 60 %。同时比较 Codebook Supp. Table 10 的聚类与 TOMTOM 相似图的一致性。

### 得到什么结果

- TF 层面：JASPAR 中 762 个人类 TF，有 759 个在 Codebook 中有代表 PWM，732 个有直接体外证据。
- Motif 层面：857 个人类 JASPAR motif 中 565 个（66 %）匹配同一 TF 的 Codebook PWM；115 个只匹配其他 TF；177 个在主判定下无匹配，其中 105 个在 q < 0.05 下仍无全长匹配。
- 105 个无匹配中，69 个为 ≤ 10 bp 的短 motif（检验效能受长度限制），18 个为复合异源二聚体，18 个为 > 10 bp 的单蛋白 motif（可能是 Codebook 代表集未保留的替代模式，未验证）。
- 匹配率依赖长度：≤ 8 bp 的 motif 无匹配比例为 27 %，> 15 bp 为 12 %。
- 两种相似度定义在小簇上高度一致（每簇匹配比例中位数 1.0），在大簇上分歧明显（> 50 个成员的簇为 0.21）。

### 结论

Codebook 适合作为 TF 覆盖骨架，但不能代替多来源 motif 集合；PMA 需要在自己的 motif 集合上独立聚类，并把 Codebook / HOCOMOCO 的聚类作为外部 benchmark，而不是直接继承。

对应证据：

- [Step 1 结果说明](../../docs/STEP1_MOTIF_PILOT_RESULTS.md)
- [按长度的覆盖率](../../results/01_motif_pilot/q1_coverage_by_length.tsv)
- [判定阈值敏感性](../../results/01_motif_pilot/sensitivity_grid.tsv)
- [105 个 q < 0.05 仍无匹配的人类 motif](../../results/01_motif_pilot/q2_human_no_match_at_q005_motifs.tsv)

## 2. 多来源 raw layer 与证据模型：保留记录，不提前合并

### 为什么做

不同数据库之间大量复制同一批实验（例如 Yin 2017 / Jolma 2013 HT-SELEX 被 CisBP、Codebook、HOCOMOCO、Factorbook 各自收录），如果直接合并或直接计数，会把“同一证据被多次收录”误当成“独立重复”。因此需要一个保留来源、实验身份和证据类型的 raw layer。

### 做了什么

导入 Codebook、JASPAR（CORE + UNVALIDATED）、HOCOMOCO v14（H14CORE，v0.2.1 补入 INVITRO/INVIVO）、CisBP 3.10 人类、Factorbook ChIP-seq 和 HT-SELEX，统一格式与归一化，记录直接结合证据、实验 accession、`derived_from` 关系和完全重复组（只标记，不合并）。同时建立一个预先固定的校准 benchmark：19 对 P-high（Codebook Table 13 一致）、500 对 P-provisional（同 TF 不同来源）和 500 对 N-challenge（不同 superclass 但共享 5-mer）。

### 得到什么结果

- v0.2.1 raw layer：30,781 条记录，29,778 条有矩阵，覆盖 1,771 个 HGNC TF。
- 完全相同的归一化矩阵 1,502 条；按四位小数取整后 4,519 条记录落在 2,184 个重复组中，最大的跨库组是 CisBP + Codebook（1,347）。
- 在 v0.1 规则下，P-provisional 的连接率为 0.71（either）/ 0.65（both），N-challenge 为 0.048 / 0.024。短 motif 同时导致两种弱点：≤ 8 bp 时 N-challenge 连接率 0.15，P-provisional 漏掉 44 %。
- 500 对 P-provisional 中 464 对无法确认实验独立；同一出版物来源的连接率高于不同出版物（0.76 vs 0.60），提示共享实验可能抬高一致率。

### 结论

跨库“一致”很大程度上是同一实验被重复收录，不能作为独立重复证据；raw layer 必须保留实验身份，证据计数以独立实验为单位。没有人工标注时，v0.1 规则继续作为操作性规则，benchmark 数字只作描述。

对应证据：

- [Step 2 结果说明](../../docs/STEP2_MOTIF_IMPORT_RESULTS.md)
- [按来源的证据类型](../../results/02_motif_import/evidence_by_source.tsv)
- [按长度的 benchmark 连接率](../../results/02_motif_import/benchmark_v01_by_length.tsv)
- [P-provisional 的实验独立性](../../results/02_motif_import/benchmark_v01_pprov_by_independence.tsv)
- [跨库重复组](../../results/02_motif_import/duplicate_groups_by_sources.tsv)

## 3. De novo 来源把 motif 记录扩大到约 47 万条，其中约 21 万条通过 QC

### 为什么做

整理数据库主要收录已知 TF 的经典模式。基于染色质可及性和 ChIP 的深度学习模型（BPNet/ChromBPNet）以及大规模 ChIP de novo 发现（Cistrome）可能补充细胞类型特异、共结合或尚未注释的模式，这是 PMA 要回答“还有哪些模式”的前提。

### 做了什么

下载并解析 ENCODE BPNet、ChromBPNet、ProCapNet 模型的 TF-MoDISco motif、Cistrome DB2 的 de novo motif 以及 HDMA motif。每类来源使用其自身的质量信息过滤：

- ENCODE：只用 counts head 和正向 pattern，并通过 MotifCompendium 逐 pattern 索引（按 annotation、head、pattern、posneg 连接）去除 `flag_remove` 的 pattern；
- Cistrome：样本 QC 至少通过 6 项中的 5 项且 peaks 通过，并要求 −log10 p ≥ 10、z < 0；
- HDMA：使用作者的 508 个合并 motif；ProCapNet 只作注释。

MoDISco PFM 只在两端连续 IC < 0.25 的位置修剪。每条记录按证据 v2 标注为体外直接、整理参考、ChIP 模型、ChIP de novo、可及性模型、转录模型等类型。

### 得到什么结果

- v0.3 raw layer 共 472,964 条记录，211,457 条进入聚类池。
- 进入聚类池的记录：ENCODE ChromBPNet 46,895、ENCODE BPNet 12,281、Cistrome DB2 116,250、HDMA 6,253，其余为 v0.2.1 来源（CisBP 6,431、Factorbook 17,177、HOCOMOCO 2,435、JASPAR 2,050、Codebook 1,685）。
- 主要排除原因：profile head 182,162、MotifCompendium `flag_remove` 149,664、negative pattern 62,134、Cistrome peaks 未通过 25,393、Cistrome 样本 QC 不足 23,291。
- 证据 v2：可及性模型 213,861、ChIP de novo 147,569、ChIP 模型 80,311，而体外直接证据只有 13,176、整理参考 1,164。

### 结论

De novo 来源在数量上占绝对多数，但单条记录的证据强度低，且没有直接结合证据（可及性模型 motif 不对应特定蛋白）。这决定了后续必须先去冗余，并在选代表时区分证据层级。

对应证据：

- `processed/v0.3_raw_layer/import_summary.json`（Argos 数据根目录下）
- `processed/annotations/evidence_v2/summary.json`
- [Step 2c 设计](../../docs/STEP2C_DENOVO_SOURCES_DESIGN.md)

## 4. 对齐相似度 s 与代表覆盖阈值 τ = 0.825

### 为什么做

TOMTOM 的 per-query q 值不对称且依赖背景集合，不适合在数十万 motif 上构建对称的图，也不能直接回答“一个 hub 能否代表某个成员”。需要一个对称、可精确计算的相似度，并把它校准到已有的统计匹配规则上。

### 做了什么

定义 s(A, B)：在两条链和所有偏移（重叠 ≥ 5 位）中，取列间 Pearson 相关均值（截断到 [0, 1]）乘以重叠长度 / 较长 motif 长度的最大值。用 18,543 个 query、约 870 万对 motif 校准：以 `statistical_match_v0.1`（either direction）为标签，选择使一致率 ≥ 95 %（主要分层 ≥ 90 %）的最小 τ。

### 得到什么结果

τ = 0.825（unrounded 一致率在 τ = 0.80 时为 0.9499，未达到 0.95）。困难负样本几乎不会达到 s ≥ 0.85（第 99 百分位 0.805）。原先的 both-direction 标签会给出 τ = 0.95（网格上限），因为 73 % 未通过 both-direction 的高相似对只在一个方向上通过；0.95 保留为严格敏感性阈值。

### 结论

s ≥ 0.825 作为“hub 足以代表该成员”的操作性定义，s ≥ 0.95 作为严格版本。标签修正发生在任何聚类结果出现之前，两条曲线都保留。

对应证据：

- `result/step3b_v03/tau_calibration/tau.json`、`curve.tsv`
- [设计 §13](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md)

## 5. 在全部节点上直接分档的三种尝试均失败

### 为什么做

PI 要求三档代表性 motif（约 500 / 1,000 / 2,000，数量近似即可），每簇选 hub。我们首先尝试在全部约 21 万个节点上直接聚类。

### 做了什么与结果

1. k-mer 亲和图 + Seurat Louvain：三档 542 / 995 / 2,059 个簇，hub 覆盖率 0.48 / 0.56 / 0.65，跨簇 hub 冗余 0.53 / 0.59 / 0.70，全部未通过。MEDIUM 中 HOCOMOCO、Codebook 成员的覆盖率只有 0.13、0.18。
2. PCA 近邻候选图 + 精确 s：候选集对已知匹配的召回率只有 0.13。原因是中位节点有 151 个已知匹配，top-100 近邻在结构上无法容纳。
3. 精确全对全 s：单体分区在 s ≥ 0.65 下有 3.13 亿条边，图过密，统计步骤被 PI 叫停。

### 结论

三种方法失败的共同原因是节点高度冗余：同一模式在多个来源、多个模型中重复出现，使相似图极其稠密，簇和 hub 都被重复拷贝主导。这一负结果直接导向 §6 的去冗余。

对应证据：`result/step3b_v03/tiers/`（§14）、`result/step3b_v03/align/`（§15、§15b）；[设计 §14–§15b](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md)

## 6. 去冗余：211,431 个节点压缩为 101,228 个 unique motif

### 为什么做

PI 指示：多个数据库中完全相同的 motif 应合并成一条 unique 记录，保留全部来源和注释，赋予内部 ID，然后再聚类。

### 做了什么

在每个分区内用 CD-HIT 式贪心去冗余：节点按证据（体外 / 整理优先）、独立实验数、总 IC、节点 ID 排序；未分配的节点成为代表，吸收所有与其 s ≥ 0.99 的未分配节点（无链式传递，每个成员都在代表 0.99 以内）。t 由 PI 在 0.85–0.99 的扫描中选定。

### 得到什么结果

- 211,431 个可聚类节点 → 101,228 个 unique motif（单体 99,133，复合 2,095），ID 为 `PMU_M*` / `PMU_C*`。
- 19,495 个 unique motif 合并了 ≥ 2 条记录，3,658 个跨越 ≥ 2 个数据库（最多 7 个）。
- 单体中 81,731 个 unique motif 只来自单一记录。
- 压缩曲线：t = 0.95 时单体 56,818，t = 0.85 时 26,048。
- unique motif 之间 s ≥ 0.65 的单体边为 4,150 万条；1,274 个单体和 203 个复合 motif 没有任何 s ≥ 0.65 的伙伴（isolated）。

### 结论

s ≥ 0.99 的去冗余把数据量减半，同时完整保留了每条来源记录与 unique ID 的对应关系。剩余的 unique motif 仍以单记录 de novo 模式为主。

对应证据：

- `result/step3b_v03/dedup/PMA_unique_motifs_t0.99.tsv`（每个 unique motif 的来源与 TF 注释）
- `result/step3b_v03/dedup/PMA_motif_to_unique_t0.99.tsv.gz`（每条记录 → unique ID）
- `result/step3b_v03/dedup/scan.tsv`（各 t 的压缩率）
- `result/step3b_v03/unique/graph_summary.json`

## 7. 在全部 unique motif 上分三档：簇数可达，代表性不足

### 为什么做

检验去冗余后能否直接在 unique-motif 图上得到 PI 的三档代表集。

### 做了什么

在连通的 unique motif 上构建 s ≥ 0.65 的加权图，按 PI 决定将 isolated motif 单列。LOW 使用全图 Louvain（分辨率 0.2）；全图簇数随分辨率增长极慢（0.2 → 2 只从 425 增至 472），因此 MEDIUM / HIGH 改为在每个 LOW 簇内部再聚类（嵌套子聚类）。每簇 hub 为覆盖成员最多的 unique motif（s ≥ τ）。sub_r2 因 Louvain 在一个大簇上不收敛而被剔除（其余分辨率均 < 30 秒）。

### 得到什么结果

| 档位 | 簇数 | hub 覆盖（τ） | 严格覆盖（0.95） | hub 冗余 | N-challenge 同簇率 | AMI Codebook / HOCOMOCO |
|---|---|---|---|---|---|---|
| LOW | 531 | 0.074 | 0.014 | 0.000 | 0.382 | 0.40 / 0.40 |
| MEDIUM | 888 | 0.195 | 0.031 | 0.007 | 0.170 | 0.58 / 0.61 |
| HIGH | 1,551 | 0.325 | 0.058 | 0.060 | 0.106 | 0.59 / 0.63 |

三档均标记为 `low_fidelity; possible_overmerging`（预设标准：覆盖 ≥ 0.90，N-challenge ≤ 0.05，冗余 ≤ 0.15）。hub 之间冗余已经很低，相比 §5 有明显改善；问题集中在“一个 hub 无法代表一个大簇”。MEDIUM → LOW 完全嵌套（purity 1.0），HIGH → MEDIUM 的平均 purity 为 0.92（两者都是 LOW 内部的子聚类，但分辨率不同，并不强制嵌套）。

### 结论

这一失败是数据结构决定的，而不是参数问题：约 10 万个 unique motif 中大多数是彼此相距较远的单记录模式，几百到两千个 hub 在数学上不可能在 s ≥ 0.825 下覆盖它们（s ≥ 0.85 的贪心覆盖都需要约 26,000 个中心）。因此三档必须改变“代表谁”，而不是继续调分辨率。

对应证据：

- `result/step3b_v03/align_tiers/tier_qc.tsv`、`tier_mapping.tsv`、`final_tier_{LOW,MEDIUM,HIGH}.tsv.gz`
- `result/step3b_v03/unique/tier_choice.json`（各分辨率的簇数）
- [设计 §17](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md)

## 8. Core-set 三档（进行中）

### 为什么做

PI 选择 core-set 方案：hub 只从证据可靠的 motif 中选，使三档成为“可靠模式的代表集”，其余 motif 不丢弃，而是挂到最相似的 hub 上并标注代表程度。

### 做了什么

Core 定义：任一记录有体外或整理证据（证据 v2 tier ≤ 2），或由 ≥ 2 个独立实验支持。在 core motif 的子图上重复 §7 的流程（同一阈值、Louvain、嵌套子聚类、hub 规则），目标仍为 500 / 1,000 / 2,000。非 core motif 被分配给 s 最高的 hub（s ≥ 0.65），按 s 是否 ≥ τ 标注 covered；没有任何 hub 在 0.65 以内的标记为 unassigned。

### 当前结果

- Core 集合 24,194 个 unique motif（单体 23,888，复合 306）；其他定义作为参考：只用高证据 9,227，≥ 2 条记录 17,680，≥ 2 个数据库 3,658。
- Core 子图：单体 23,318 个连通节点、259 万条 s ≥ 0.65 边（全图的 6 %）；570 个单体、43 个复合 core motif 在 core 内部孤立。
- 全图 Louvain 簇数：单体 285（分辨率 0.2）到 361（分辨率 4），复合 42–54；MEDIUM / HIGH 将同样需要嵌套子聚类。
- Hub 覆盖、N-challenge 和非 core motif 的分配率待更新。

对应证据：`result/step3b_v03/unique_core/core_definition.json`、`scan_*.tsv.gz`；[设计 §18](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md)

## Discussion

这部分工作的主要发现是一个负结果加一个结构性解释：在 de novo 来源占绝大多数的统一 motif 宇宙中，“约 2,000 个 hub 忠实代表所有模式”的目标无法实现。原因不是聚类算法不够好，而是绝大多数 de novo motif 只出现一次，彼此之间相似度又不足以被同一个代表覆盖。§5 和 §7 的连续失败从不同角度指向同一点：重复拷贝会让图过密（去冗余前），长尾单例会让代表不足（去冗余后）。

这对 PMA 的定位有两点含义。第一，代表集应当回答“可靠模式有哪些”，而不是“所有出现过的模式有哪些”；单记录 de novo 模式应以“已分配 / 未分配 + 与 hub 的相似度”的形式保留，作为候选新模式的来源，而不是被强行并入某个代表。第二，证据计数必须以独立实验为单位：Step 2 显示大量跨库一致其实是同一实验的重复收录，core 定义中的“≥ 2 个独立实验”正是为此设计。

需要注意的局限：

- τ 来自 TOMTOM 统计匹配的校准，而不是人工标注的真值；短 motif（≤ 8 bp）在 s 和 TOMTOM 中都处于劣势。
- 覆盖率是在同一数据上优化 hub 后得到的工程保真度指标，不是独立的预测性能。
- Louvain 在大而稠密的子图上存在不收敛的分辨率（sub_r2），稳定性（种子 / 子采样）尚未评估。
- 可及性模型 motif 没有对应蛋白，HDMA 和 ProCapNet 的实验独立性无法解析，这会影响 core 定义中“独立实验”的计数。
- “isolated”“unassigned”都是操作性标签，不等于“新 motif”。

## 下一步

1. 完成 core-set 三档（嵌套子聚类、hub、QC、非 core 分配），更新 §8。
2. 种子 / 子采样稳定性；每档的簇注释（TF 家族、来源构成）和代表 PWM 导出。
3. 绘制 Figure 1C 面板：来源 → QC → 去冗余 → core → 三档的数量流（Sankey/漏斗），以及各档覆盖率与簇数关系。
