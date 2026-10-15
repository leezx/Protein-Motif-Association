我建议 PMA 采用一条明确的路线：

以 2026 年最新的人类 TF motif reference 为基础，整合 JASPAR、HOCOMOCO、CisBP、Codebook 和 Factorbook，建立一个保留全部原始 motifs、但经过质量分级和 sequence-similarity clustering 的统一 Human Motif Reference。

关键不是把五个数据库的 PWM 简单合并，而是解决三个问题：

1. Completeness： 尽可能覆盖目前已知的人类 DNA sequence recognition patterns，包括非经典和复合 motifs。
2. Quality： 区分体外验证、体内支持、跨实验复现以及仅由 ChIP-seq 推断的 motifs。
3. Non-redundancy： 避免把几十个高度相似的 FOX、ETS、KLF motifs 当成几十种独立的 DNA-binding patterns。

我查到了一个对 PMA 非常有利的新进展：2026 年 8 月发表的 Codebook 研究，已经整理出覆盖 1,421 个人类 TF 的代表性 motif reference。

这意味着，我们不必从零开始构建 motif universe。

但我不建议只采用 Codebook。因为它的目标是 TF sequence specificity，而 PMA 还需要保留 alternative motifs、ChIP-derived motifs 和可能的 complex-associated patterns。

下面给出可以直接执行的方案。

⸻

一、先确定五个核心数据源

我建议将 motif reference 分成三个层次。

Tier 1：高质量 curated reference

这是 PMA motif collection 的基础。

Database	Version	内容	PMA 中的作用
Codebook	2026	1,421 human TFs 的代表性 motifs	Human TF coverage backbone
JASPAR	2026	Curated TF motifs、alternative profiles、部分 dimers	High-confidence motif reference
HOCOMOCO	v12	Human TF motifs、in vitro/in vivo subcollections	Motif quality 和 alternative specificity
CisBP	3.1	广泛的 TF specificity collection	补充缺失 TF 和实验 profiles

这里的 1,421 指 Codebook 论文整理的人类 TF motif 覆盖数，并不代表 1,421 个独立的 sequence patterns。

Codebook 的重要贡献是对 332 个此前缺乏充分表征的候选 TF 开展系统实验，其中 177 个获得 motifs，并扩展了约 130 种此前未知的 distinct sequence patterns。论文还提供了完整的人类 TF representative PWM collection。 

下载入口：

* ⁠Codebook 2026 论文及 Supplementary Data 1
* ⁠Codebook PWM Zenodo 数据集
* ⁠JASPAR 2026 官方下载
* ⁠HOCOMOCO v12 官方下载
* ⁠CisBP 数据库

这里有一个重要选择

Codebook 作为 backbone，但不作为唯一 motif source。

原因很简单。

Codebook 的 representative collection 追求 TF coverage 和可靠的 sequence specificity。

而 PMA 希望发现：

Protein P 的 genomic occupancy 与哪些 DNA sequence patterns 存在关联？

这个问题要求保留更多 alternative motifs。

如果只使用每个 TF 的 representative motif，就可能提前丢失我们最感兴趣的 alternative binding patterns。

因此，我建议：

* Codebook representative collection 用于建立 reference coverage。
* JASPAR CORE 提供 curated alternative profiles。
* HOCOMOCO 提供 in vitro/in vivo motif variants。
* CisBP 补充其他资源未覆盖的 experimentally determined motifs。

这些来源可以相互重叠，但不能在原始数据层面直接删除。

⸻

二、Factorbook 必须加入，但要单独管理

⁠Factorbook Human Motif Catalog

Factorbook 提供两套很有价值的 motif collections：

Collection	Motifs	TFs
ChIP-seq-derived MEME motifs	6,069	733
HT-SELEX motifs	6,700	631

这些是其公开下载页面报告的数量，实际下载时应记录版本和时间。 

为什么 Factorbook 很重要？

因为它包含大量 ChIP-seq-derived de novo motifs。

这些 motifs 不一定代表 ChIP target protein 的 intrinsic DNA-binding specificity。

但对于 PMA，它们恰恰可能是有价值的候选 DNA sequence patterns。

例如，某个 HDAC1 ChIP-seq dataset 中发现的 motif，可能是某个 DNA-binding partner 的 motif。

我们不需要在 motif collection 阶段就知道这个 partner 是谁。

先保留 sequence pattern，后续再建立 protein–motif associations。

但这里存在一个必须控制的循环论证风险。

如果 Factorbook 的某个 motif 是从 HDAC1 ChIP-seq peaks 中发现的，我们不能再用同一数据集证明 HDAC1 与该 motif 显著关联，并把它视为独立验证。

因此，每个 motif 必须保留：

* Source dataset。
* Discovery assay。
* Target protein。
* Biosample。
* Experiment accession。
* Original motif ID。

如果某些元数据缺失，就需要标记为无法进行严格独立验证。

这对后续 PMA statistical framework 非常重要。

⸻

三、不要直接合并 PWM：建立三层 motif representation

这是整个 motif reference 最关键的技术设计。

我建议 PMA 同时保留三个层次。

Level 1：Raw motif profiles

保留所有通过基本格式检查的原始 motifs。

例如：

JASPAR_MAxxxx
HOCOMOCO_xxxx
CISBP_xxxx
CODEBOOK_xxxx
FACTORBOOK_xxxx

每个 motif 都有唯一 PMA internal ID。

这里不进行 aggressive deduplication。

因为两个非常相似的 PWMs 可能来自不同实验，具有不同 evidence。

原始记录的价值不仅是 motif matrix 本身，还包括 provenance。

Level 2：Motif clusters

将相似 PWMs 聚类为 motif clusters。

例如：

PMA_CLUSTER_0001
    JASPAR motif A
    HOCOMOCO motif B
    Codebook motif C
PMA_CLUSTER_0002
    Factorbook motif D
    CisBP motif E

聚类应基于 DNA sequence pattern similarity，而不是 TF 名称。

原因是：

不同 TF 可以识别非常相似的 motifs。

同一个 TF 也可能具有多个不同的 motif patterns。

因此：

Motif cluster 不等于 TF family。

Level 3：Representative motifs

每个 cluster 选择一个或少数几个 representative motifs。

这是后续 PMA genome scanning 的主要输入。

但是，我不建议简单地对多个 PWMs 求平均。

PWM averaging 可能模糊真实的 sequence specificity，尤其当 motifs 在长度、位置或信息含量上不同时。

更好的办法是：

从 cluster 中选择一个已有高质量 PWM 作为 representative。

选择依据包括：

1. Experimental evidence。
2. Independent validation。
3. Motif information content。
4. Sequence similarity centrality。
5. Source quality。

其中 information content 不能越高越好，因为真实 motifs 也可能具有较低的信息含量。

最终得到：

Raw motifs
    ↓
Similarity clusters
    ↓
Representative motifs

同时保留：

Representative motif
    ↓
All original motifs
    ↓
All source evidence

这样既能提高计算效率，也不会丢失原始信息。

⸻

四、Motif clustering：我建议直接使用 TOMTOM

对于 v0.1，我不建议开发新的 motif similarity algorithm。

现有的  ⁠MEME Suite 已经提供 TOMTOM。

TOMTOM 可以比较 motifs，并识别相似的 sequence patterns。

建议流程：

All candidate PWMs
        |
        v
PWM normalization
        |
        v
Motif similarity (TOMTOM)
        |
        v
Similarity graph
        |
        v
Motif clustering
        |
        v
Representative selection

但这里有一个容易被忽略的问题。

TOMTOM 的显著性不能直接等同于 biological equivalence。

例如，两个 motifs 可能只共享一个很短的核心序列。

如果直接根据显著性建立连接，就可能把不同的 sequence patterns 错误聚在一起。

因此，我建议同时设置：

* TOMTOM adjusted significance。
* Alignment coverage。
* Motif overlap length。
* Information-content similarity。

初始可以使用较严格的 TOMTOM q-value，例如 0.01，作为候选相似关系的筛选条件。

但它不是已经验证的最终阈值。

还需要通过已知 motif families、alternative motifs 和不同长度的 motifs 做 sensitivity analysis。

不要使用简单的 connected components 直接生成最终 clusters。

因为 motif similarity 不具有传递性。

A 与 B 相似、B 与 C 相似，并不意味着 A 与 C 相似。

如果使用 connected components，容易形成过大的 motif clusters。

我更建议在 similarity graph 上使用层次聚类，并对 cluster 内部的最低相似度进行检查。

⸻

五、质量分级：不要把 motif 来源等同于 motif 质量

这里需要特别小心。

一个 JASPAR motif 不一定在所有 contexts 中都比 Factorbook motif 更准确。

一个 in vitro motif 也不一定比 ChIP-derived motif 更有用。

它们回答的是不同问题。

因此，我建议 PMA 将 motif quality 分成两个独立维度。

Dimension A：Sequence specificity evidence

这个 motif 是否具有可靠的 DNA sequence recognition evidence？

例如：

* HT-SELEX。
* PBM。
* SMiLE-seq。
* EMSA。
* 其他 direct DNA-binding assays。

Dimension B：Genomic occupancy support

这个 motif 是否能够解释实际的 genomic occupancy？

例如：

* Independent ChIP-seq enrichment。
* Summit-centered enrichment。
* Cross-dataset replication。
* Orthogonal assay support。

注意：ATAC-seq footprint 可以提供 context-specific occupancy 线索，但 footprint 本身不能唯一识别结合蛋白，也不应自动被视为 direct binding validation。

最终每个 motif 可以有这样的记录：

Motif	Sequence evidence	Occupancy support	PMA status
Motif A	Strong	Strong	High confidence
Motif B	Strong	Limited	High-confidence sequence motif
Motif C	Limited	Strong	Genomic pattern supported
Motif D	Limited	Limited	Exploratory

这里的 status 是我们建议的 PMA 内部定义，不是现有数据库已经提供的统一等级。

尤其不能因为一个 motif 缺少 ChIP-seq support，就直接把它认定为低质量 motif。

有些 TF 可能根本没有合适的 ChIP-seq datasets。

⸻

六、一个非常重要的决定：是否纳入所有 de novo motifs？

我的答案是：

应该纳入候选库，但不能全部进入 high-confidence scanning reference。

这是 PMA 追求 completeness 与 quality 时必须做出的区分。

我建议维护两套 collection。

PMA-CORE

用于主要 statistical analysis。

包含：

* Curated motifs。
* 具有明确实验来源的 sequence-specific motifs。
* 经过独立验证的 ChIP-derived motifs。
* 经质量控制的 alternative motifs。

PMA-EXTENDED

用于 discovery 和探索。

包含：

* 尚未充分验证的 de novo motifs。
* JASPAR UNVALIDATED。
* Factorbook 中证据不足的 profiles。
* 无法明确分配给某个 TF 的 sequence patterns。

两者共享 motif IDs 和 clustering体系。

但 CORE 和 EXTENDED 的 statistical associations 必须分别标记。

这样我们既不牺牲覆盖范围，也不会因为加入大量弱证据 motifs 而降低主要 reference 的可靠性。

⸻

七、具体执行：我建议按四个阶段完成

整个 motif reference 构建应该是一个独立、可冻结的工作包。

不要在这一阶段加入 ChIP-Atlas 全量分析。

Stage 1：下载与整理（预计 2–3 天）

下载：

1. Codebook 2026 representative PWMs 和相关 metadata。
2. JASPAR 2026 CORE vertebrates，以及 UNVALIDATED 作为扩展候选。
3. HOCOMOCO v12 human CORE、INVIVO、INVITRO。
4. CisBP 3.1 human motifs。
5. Factorbook MEME ChIP-seq 和 HT-SELEX catalogs。

统一转成 MEME motif format。

同时建立：

motif_id
source_database
source_version
source_motif_id
tf_gene_symbol
tf_ensembl_id
organism
assay
experiment_accession
biosample
motif_length
matrix
evidence_type

对没有明确 TF assignment 的 motifs，允许 tf_gene_symbol = NA。

不要强行补充一个预测 TF。

此外，JASPAR vertebrate motifs 不能全部直接标记为 human experimentally measured motifs。需要区分原始实验物种、human ortholog mapping 和实际证据来源。

Stage 2：统一格式和 QC（预计 2–4 天）

执行：

* PWM/PFM format validation。
* A/C/G/T normalization。
* Matrix probability normalization。
* Motif length filtering。
* Invalid motif removal。
* Exact duplicate detection。
* Metadata harmonization。

特别注意：

不要因为 motif information content 低就直接删除。

应该标记 low-complexity 或 low-information motifs，再评估其是否具有独立实验支持。

Stage 3：Motif similarity clustering（预计 3–5 天）

使用 TOMTOM 构建 motif similarity graph。

进行 clustering。

输出：

PMA_motifs_raw.meme
PMA_motifs_core.meme
PMA_motifs_extended.meme
PMA_motif_metadata.tsv
PMA_motif_clusters.tsv
PMA_motif_representatives.tsv
PMA_motif_evidence.tsv

同时生成 QC 报告：

* 各数据库原始 motif 数量。
* 不同来源的 overlap。
* Unique motif clusters。
* 每个 cluster 的成员数。
* Human TF coverage。
* Unassigned motif clusters。
* Motif length distribution。
* Information-content distribution。

这些将来可以直接用于 Figure 1。

Stage 4：独立质量评价与冻结（预计 3–5 天）

这里我建议做三个检查。

Check 1：Known motif recovery

已知经典 TF motifs 是否能够被正确聚类？

例如：

* FOX family。
* ETS family。
* GATA family。
* Nuclear receptors。
* bHLH family。

Check 2：Alternative motif preservation

已知具有不同 sequence preferences 的 alternative motifs 是否被错误合并？

这是避免 over-clustering 的关键。

Check 3：Source robustness

移除某一个数据库后，motif cluster structure 是否发生大幅变化？

例如：

All sources
vs.
Without Factorbook
vs.
Without CisBP

如果加入 Factorbook 后 unique motif clusters 数量暴涨，需要判断这些新增 clusters 是否主要由低信息量或弱证据 motifs 构成。

通过这些检查后，冻结：

PMA Human Motif Reference v0.1。

上述时间是工程量估计，不包含复杂的 metadata 清理、数据授权处理或大量人工审核；如果源数据库结构不一致，可能需要更长时间。

⸻

八、我认为 Codebook 2026 提供了一个更省力的选择

这里有一个值得你注意的细节。

Codebook 论文已经做过类似的 motif integration 和 clustering。

研究者从多个数据库整理 motifs，使用 pairwise motif similarity 和 hierarchical clustering，最终提供覆盖 1,421 个 human TF 的 representative motifs。

而且，他们公开了 motif cluster annotations 和相关数据。 

这意味着我们应该先下载并检查：

Codebook Supplementary Data 1 + Supplementary Table 10/11。

尤其是 Supplementary Table 11。

它可能帮助我们减少大量重复的 motif clustering 工作。

但我不建议直接将 Codebook clusters 作为 PMA 的最终 clustering。

因为 PMA 还需要纳入更广泛的 ChIP-derived motifs 和 alternative profiles。

更合理的方式是：

Codebook clustering 作为参考标准，PMA 在此基础上扩展并重新评估新增 motifs。

这样能明显降低工程成本。

⸻

九、最终交付物应该是什么？

我建议不要把目标简单定义为：

“收集最多的 PWM。”

而是：

PMA Human Motif Reference v0.1

它应该包含四个核心部分。

Deliverable	内容	用途
Raw motif collection	所有通过基础 QC 的 motifs	保证完整性和可追溯性
Nonredundant CORE	高质量 representative motifs	主要 genome scanning
EXTENDED collection	Alternative、de novo、低证据 motifs	Discovery
Evidence/cluster metadata	Source、assay、TF、cluster、quality	后续 PMA annotation

需要额外保存一个非常重要的字段：

Discovery dataset provenance。

因为下一阶段我们会使用 ChIP-Atlas 构建 protein–motif associations。

如果一个 motif 来自某个 ChIP-seq dataset，那么该 dataset 不能再被当作这个 motif 的独立验证证据。

这是从一开始就必须设计好的。

⸻

十、Go/No-Go：什么时候可以进入 PMA association analysis？

我建议设置四个完成条件。

Gate	标准
G1：Completeness	成功整合全部五个主要来源，保留可追溯 metadata
G2：Quality	CORE 中每个 motif 都有明确的纳入依据
G3：Nonredundancy	已知 motif families 聚类合理，alternative motifs 未被系统性合并
G4：Reproducibility	固定输入版本和参数后，可完全重建相同 motif reference

不建议在这个阶段预设“必须有多少个 motifs”。

因为 motif 数量越多并不一定越好。

最终我们真正应该报告的是：

* Human TF coverage。
* Number of independent sequence-pattern clusters。
* Number of alternative motifs。
* Number of experimentally supported motifs。
* Number of previously unassigned motifs。

这些指标比一个很大的 PWM 总数更有说服力。

⸻

我的最终建议

第一步，不要立即开始下载五个数据库的全部 motifs。

先做一个规模很小但决定后续架构的检查：

下载 Codebook 2026 的 representative motif collection 和 cluster annotations，再下载 JASPAR 2026 CORE。

回答三个问题：

1. Codebook 已经覆盖了 JASPAR 中多少 human TF motifs？
2. JASPAR 提供了多少 Codebook representative collection 未保留的 alternative sequence patterns？
3. Codebook 的 clustering 方法能否直接复用于 PMA？

这一步完成后，再整合 HOCOMOCO、CisBP 和 Factorbook。

我建议采用 Codebook-first、multi-source expansion、evidence-aware clustering 的方案。

这样 PMA 可以利用最新的大规模 motif characterization 成果，不重复已经完成的工作，同时保留它真正需要的 alternative 和 ChIP-derived sequence patterns。

预计约两到三周可以完成一个可用的 motif reference 初版，前提是数据可正常获取、metadata 不需要大量人工修复。

而且这项工作可以独立完成、冻结版本，不需要等待后续 ChIP-Atlas 的 protein–motif association algorithm。

PMA 的 motif reference 应该尽可能全面，但统计分析使用的 motif collection 必须经过严格质量控制。完整性和可靠性不是二选一，我们可以通过 CORE/EXTENDED 双层设计同时保留。