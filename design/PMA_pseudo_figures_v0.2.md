我同意你的收敛方向。PMA 现阶段不需要升级成“motif-dependent recruitment mechanism”项目。 我们首先要把 protein–motif genomic association 建立成一个统计可靠、证据可追溯、覆盖广泛的人类参考资源。

这份审稿意见有价值，但它混合了两类建议：一类直接提高 PMA 的可靠性，另一类实际上改变了项目的科学问题。我们应该只吸收前者。

一、审稿意见的取舍

审稿建议	决定	理由
直接复用 ChIP-Atlas/ReMap	接受	避免重复构建 occupancy atlas
同一 biosample 内的 protein-specific association	接受，核心优先级	控制细胞背景和普遍富集的 motifs
HOT regions 显式建模	接受	避免把普遍开放的调控区域误判为特异性关联
高质量 motif reference，包括 Codebook	接受，待核实资源版本	改善 motif coverage 和质量
独立数据集 replication	接受	是 association reference 的基本可靠性要求
ASB 作为主要验证标准	暂缓	ASB 反映 allele-specific occupancy，不一定证明 protein 对该 motif 的依赖
Perturbation 证明 recruitment	不纳入 MVP	改变了 association 的研究目标
ChIP-exo/nexus	Optional	数据覆盖有限，不是构建 association 的必要条件
将主假说改成 recruitment grammar	拒绝	从统计关联升级为因果机制，发生 project drift
RARB 作为 Figure 6	取消	不足以承担独立主图
PMA 作为 CancerRegAtlas 底层引擎	暂不决定	两个项目不应相互绑定完成条件

这里最重要的是第二项。

我同意审稿人指出的细胞背景混杂问题，但不建议直接把“相对于同细胞其他 CAP 的富集程度”定义为唯一主要估计量。

原因是：同一细胞内广泛存在的 motif association 不一定是伪关联。

例如，一个真正参与多种 chromatin complexes 的 TF，其 motif 可能与大量 CAP occupancy 相关。

如果仅依据其他 proteins 的分布进行校正，可能把真实的、广泛共享的 associations 一起消除。

因此，PMA 应该保留两个互补的统计结果：

1. Genomic association

Protein P 的 occupancy regions 是否相对于匹配的 genomic background 显著富集 motif M？

2. Protein-specific association

在相同 biosample 和可比较的 genomic regions 中，P–M association 是否强于其他 proteins 的背景分布？

第一个回答是否存在 genomic association。

第二个回答这种 association 是否具有 protein specificity。

两者不应相互替代。

二、PMA v0.2 的核心科学问题

我建议正式冻结为：

Can we systematically map and quantify protein–motif genomic associations across the human chromatin-associated proteome using calibrated statistics and reproducible occupancy evidence?

这里有三个明确的贡献。

第一，建立覆盖广泛 human chromatin-associated proteins 的 occupancy reference，但主要复用 ChIP-Atlas 等已有资源，不把重新处理原始数据作为创新点。

第二，建立高质量、统一且经过 redundancy control 的 motif repertoire。

第三，也是核心创新：建立具有统计校准、protein specificity、context annotation 和 evidence grading 的 protein–motif association reference。

PMA 的主交付物是 association matrix，而不是 protein recruitment mechanism。

这点不再动摇。

⸻

三、Figures 不应该现在就扩张到六张

你指出得对。我们目前真正成熟的内容最多只能支撑一到两张主图。

我建议先冻结两个核心 Figure concepts。

Figure 1. Construction of the human Protein–Motif Association reference

这张图主要回答：

PMA 收录了什么，以及如何建立统一的 protein–motif association reference？

暂定 panels：

A. PMA architecture：occupancy datasets、motif repertoire、association framework。

B. Human chromatin-associated protein coverage：TFs、cofactors、chromatin remodelers、histone modifiers 等。

C. Motif repertoire construction：JASPAR、HOCOMOCO、Codebook 等资源的整合、去冗余和质量分级。

D. Occupancy dataset coverage：proteins、biosamples、assays、replicates。

E. Protein–motif association matrix：初步展示 reference 的整体结构。

这是一张 resource overview，不需要强行制造生物学发现。

Figure 2. Statistical calibration and reproducibility of protein–motif associations

这是目前最重要的主图。

它需要证明：

PMA 不只是又一次 motif enrichment，而是能够产生可比较、可复现、经过背景校准的 protein–motif associations。

暂定 panels：

A. Peak–motif overlap 与 summit-centered enrichment 的定义。

B. Matched genomic background：GC、region length、accessibility、promoter/enhancer composition 等。

C. Genomic association 与 protein-specific association 的比较。

D. HOT-region stratification。

E. Independent dataset reproducibility。

F. Statistical calibration、effect sizes 和 false discovery control。

其中一个需要提前解决的技术问题是：不同 protein 的 ChIP-seq peaks 在数量、宽度和 genomic distribution 上差异很大。

如果不处理这些因素，association scores 可能无法跨 protein 比较。

此外，同一 biosample 的多个 ChIP datasets 并非完全独立的生物学重复。统计框架必须区分 peak-level evidence、experiment-level replication 和 biosample-level replication。

⸻

四、Application Figures 现在保持开放

我不建议现在强行指定 Fig. 3–6。

我们可以先定义三类值得寻找的应用，但不承诺全部进入论文。

Application A：Non-sequence-specific chromatin proteins

这是与 JASPAR 差异最直接的应用。

例如 HDAC、BAF complex components、BRD4、EP300 等。

核心问题是：PMA 能否为这些缺乏自身经典 DNA recognition motifs 的 proteins 提供可靠的 motif association profiles？

但我们暂时不把这些 profiles 解释为 recruitment mechanisms。

Application B：Context-specific protein–motif associations

同一个 protein 在不同 biosamples 中是否表现出可重复的 motif association differences？

这可以检验 PMA 的 context annotation 是否具有实际信息量。

但必须避免把实验批次差异解释成 biological context specificity。

Application C：Peak-level annotation

这是我认为非常有实际用户价值的方向。

对于一个 protein 的 occupancy peaks，PMA 能否提供：

* Associated motif families。
* Motif positions 和 scores。
* Genomic association evidence。
* Protein-specificity evidence。
* Context support。
* Association confidence。

这里需要特别区分全局 association confidence 和单个 peak 的 motif occurrence。前者不能直接转化为后者的 binding probability。

这三个应用方向中，最终只需要选择能够产生最强、最独立结果的部分进入主图。

⸻

五、论文定位：不为了期刊改变科学问题

我同意你不强行升级的决定。

目前最合理的定位是：

PMA: A comprehensive, statistically calibrated reference of human protein–motif genomic associations.

如果资源覆盖广泛、统计可靠、网站易用，并且能够证明相对于现有数据库的实际增量，NAR Database Issue 是合理的目标之一，但并不保证符合其收录标准。

如果后续出现真正有价值的全局生物学规律，再考虑 Genome Biology、Genome Research 等方向。

但不应该为了这些期刊预先添加 ASB、perturbation 或癌症机制分析。

⸻

六、我建议现在冻结的 PMA v0.2

项目	决定
Primary deliverable	Human Protein–Motif Association Reference
Main data source	ChIP-Atlas，必要时补充其他 occupancy resources
Motif reference	Curated、nonredundant、quality-graded motif repertoire
Main analysis	Calibrated protein–motif genomic association
Secondary statistic	Within-biosample protein specificity
Confounder control	Genomic background、HOT regions、assay/biosample effects
Evidence grading	Statistical support、independent replication、orthogonal evidence
Main figures	Resource construction + statistical validation
Applications	暂不冻结，待结果决定
RARB	不作为独立主图
ASB/perturbation	Optional validation，不作为完成条件
CancerRegAtlas	独立项目，不绑定 PMA
Target publication	以高质量资源论文为基础，不预设升档

当前真正需要解决的只有一个技术核心：如何定义一个可跨 proteins、motifs 和 biosamples 比较的 genomic association statistic。

如果这个统计量可靠，PMA 就有基础。

如果这个统计量无法区分真实的 protein-specific association 与普遍的 chromatin background，后续再增加多少 proteins 和 motifs 都不能解决问题。

所以我建议下一步专门设计 PMA Statistical Framework v0.1，先不写完整 Figures，也不开展癌症应用。

重点比较 peak overlap、summit-centered motif enrichment、matched genomic background 和 within-biosample specificity，确定哪些是主估计量、哪些是辅助证据，以及如何进行独立验证。

这次我们不再让项目随着审稿意见膨胀。先把 association 做扎实，其他价值让数据自己呈现。