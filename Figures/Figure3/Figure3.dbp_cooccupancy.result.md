# Figure 3 result — DNA 结合蛋白的全基因组共占据：已知复合物的找回、研究层面验证与稳健性

> **文档性质：** 内部分析结果稿，非投稿版本。
>
> **当前版本：** v0.1，2026-10-21。对应分析版本 v1 → v1.1 → v1.2。
>
> **对应图位：** Figure 3（暂定）。`design/PMA_pseudo_figures_v0.2.md` 中 Fig. 3–6 是待定的应用图，Figure 2 留给 protein–motif 统计校准。本图是 ChIP-Atlas 占据参考（Figure 1D）的一个应用分析。
>
> **代码：** 分支 `task_20261020_chipatlas_light_bed`，脚本 `scripts/04a_chipatlas/12–21`。设计见 `docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md` §13–§17，均在计算前提交。
>
> **审阅：** GPT 审阅 v1 为 REVISE；审阅 v1.1 为局部 REVISE，并批准开始 L2；v1.2 待审。
>
> **结果边界：** 分析对象是跨实验、跨细胞汇总的 peak 共占据，不等于同一细胞内的共同结合，更不等于物理复合物。输出统一称为 DBP 共占据模块。目前**不提名**高可信新模块。

## Result overview

如果 ChIP-Atlas 占据参考的质量足够好，属于同一蛋白复合物或同一调控程序的蛋白，应该在全基因组上占据相似的区域。我们从同一个“蛋白 × 500 bp 区间”占据矩阵出发，在三个层面做聚类：

| 层面 | 聚类对象 | 回答的问题 |
|---|---|---|
| 蛋白 | 蛋白 | 哪些蛋白经常占据同一批区域？能否找回已知复合物？ |
| 实验 | ChIP 实验 | 结合模式的差异主要来自蛋白身份、细胞背景，还是技术因素？ |
| 区域 | 基因组区间 | 哪些蛋白组合会在同样的区域反复出现？ |

然后经过两轮验证，检验结论是否经得起研究来源、测序深度、统计背景和参数选择的考验。

主要结果：

1. **已知复合物能从共占据中找回，而且结果稳健。** 808 个蛋白中，用 Jaccard 区分同一 Complex Portal 复合物的蛋白对和其他蛋白对，AUROC = 0.811（按蛋白重抽样的 95% CI 为 0.766–0.849）。PR-AUC 是随机基线的约 15 倍。广度匹配后，FDR ≤ 0.05 的复合物有 172/373（去冗余后 115/298）。换区间大小（250–1000 bp）和占据阈值（2.5–10%），这些结果基本不变。
2. **很多看起来很强的共占据其实来自单一研究。** 在 Complex Portal 未收录、共占据最高的 300 个蛋白对中，只有 47 对同时满足三项条件：跨研究一致、去掉任何一个研究后仍稳定、在同一细胞类型中由独立研究重复。它们都是已知的功能伙伴，例如 CTCF–黏连蛋白、AP-1、AP-1–BAF、TEAD–YAP、OCT4–SOX2、NELF–SPT5。
3. **实验层面约一半的结构来自同一研究或相同测序深度。** 两者都控制后，蛋白 κ 从 0.43 降到 0.25，细胞类型 κ 从 0.46 降到 0.23。Hep G2 内部按蛋白分开的结构、CTCF 按细胞类型分开的结构，在控制后几乎消失。
4. **区域层面的 20 类中等稳定。** 换随机种子、子抽样或去掉 HOT 区间，ARI 在 0.63–0.76。其中有两类（C07 HMGA1、C09 PPARA）在计算上稳定，但几乎完全由单一研究驱动。

## 1. 共同表示：蛋白 × 区间占据矩阵

### 为什么做

三个层面的分析需要同一个输入，结论之间才能比较。

### 做了什么

- 以 Figure 1D 的实验级 BED（TF 和其他蛋白 + RNA 聚合酶）为输入，只保留注释为 6 个功能类别的蛋白。
- 把基因组切成 500 bp 区间，去掉 ENCODE 黑名单。
- 一个蛋白占据某个区间，要求至少有 k_p = max(2, ⌈0.05 n_p⌉) 个不同实验在此有 peak，其中 n_p 是该蛋白的实验数。这样，单个实验的偶然 peak 不会被计入。
- 只保留占据 ≥ 500 个区间的蛋白。
- 被最多蛋白占据的前 1% 区间定义为 HOT 区间。

### 得到什么结果

- 808 个蛋白，对应 27,240 个实验、2,901 个 SRA 研究。研究来源由 ENA 查得，覆盖 100%。
- 共 3,477,832 个被占据区间，去 HOT 后 3,442,930 个。HOT 阈值是 143 个蛋白。
- 蛋白类别：序列特异 TF 556、转录机器 104、组蛋白 writer/eraser 60、组蛋白 reader 38、染色质重塑因子 31、结构蛋白/黏连蛋白 19。
- 每个蛋白的实验数中位数为 9。

对应证据：
- 蛋白清单：[`cooccupancy_v1/all/proteins.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/all/proteins.tsv)
- 研究来源：[`validation_v1_1/study_provenance.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_1/study_provenance.tsv)
- 覆盖率：[`validation_v1_2/study/provenance_coverage.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/provenance_coverage.json)

## 2. 蛋白层面：共占据能找回已知复合物

### 为什么做

这是最直接的“阳性对照”：已知复合物成员的共占据是否显著高于随机蛋白组合。如果找不回来，未知模块的提名就没有基础。

### 做了什么

- 对每对蛋白计算 Jaccard（共同占据的区间数除以合并后的区间数）。以 Complex Portal 人类复合物作独立基准。
- 区分能力：用 Jaccard 区分同复合物蛋白对和其他蛋白对，报告 AUROC 和 PR-AUC。蛋白对之间不独立，所以 CI 按蛋白重抽样计算。
- 每个复合物的显著性：
  - 统计量为成员两两 Jaccard 的中位数；
  - 背景分布把每个成员换成同一“占据广度”十分位中的随机蛋白，抽 10,000 次；
  - 对 373 个复合物做 BH 校正；
  - Complex Portal 中成员完全相同的变体合并为 298 组，每组取 p 最小的条目，再做一次 BH 校正。
- 为分清各因素的影响，同一批复合物还在三种设置下计算：全区间 + 大小匹配、去 HOT + 大小匹配、去 HOT + 广度匹配。

### 得到什么结果

| 指标（去 HOT，500 bp，5%） | 值 |
|---|---|
| AUROC | 0.811（0.766–0.849） |
| PR-AUC（随机基线） | 0.026（0.0017） |
| FDR ≤ 0.05 的复合物：全部 / 去冗余 | 172/373 / 115/298 |

HOT 去除和背景模型各自的贡献（FDR ≤ 0.05，全部 / 去冗余）：

| 设置 | 全部 | 去冗余 |
|---|---|---|
| 全区间 + 大小匹配 | 79 | 46 |
| 去 HOT + 大小匹配 | 139 | 94 |
| 去 HOT + 广度匹配 | 172 | 115 |

FDR 显著的物理复合物包括：
- 有丝分裂黏连蛋白、GBAF、NELF、SIN3A、PRC2.1；
- MBD2/NuRD 和 MBD3/NuRD、CoREST、TFIID；
- 核心 Mediator，但只检测到 13 个亚基中的 3 个。

阴性对照：减数分裂黏连蛋白（RAD21L1、REC8 变体）不显著（p ≈ 0.6），符合体细胞数据的预期。

CTCF 不是黏连蛋白复合物的成员，因此单独作为功能关联报告。它与 5 个黏连蛋白亚基的 Jaccard 为 0.49–0.70，与 RAD21 为 0.704，高于黏连蛋白亚基之间的中位数 0.558。这与 CTCF 在环挤出中锚定黏连蛋白的已知机制一致。

两种细胞系用同一套 183 个蛋白比较：

| | K-562 | Hep G2 |
|---|---|---|
| AUROC | 0.779（0.698–0.857） | 0.605（0.493–0.744） |
| 前 50 对中的已知复合物对 | 6 | 6 |
| 两者前 50 对的重合 | 2 对（CTCF–RAD21、HDAC1–HDAC2） | |

Hep G2 中 BAF 亚基之间几乎没有共占据（Jaccard 0.006）。质控显示，Hep G2 的 BAF 实验 peak 数很低：111–3,522，中位数约 400，每个亚基只有一个研究。K-562 中同类实验为 2,000–46,000 个 peak。

### 结论

已知复合物的成员确实在全基因组上共占据。这种信号在控制占据广度后、FDR 校正后、改变区间大小和阈值后都成立，可以作为 PMA 占据参考质量的阳性对照。但 PR-AUC 绝对值只有 0.026，说明共占据有富集能力，却**不能**单独用来预测物理复合物。

两种细胞系各自能找回一部分已知复合物，但找回的不是同一批。Hep G2 较弱，最可能的原因之一是部分复合物的实验产出低，不能直接解释为生物学差异。

对应证据：
- 全部实验的 Jaccard 热图：[`cooccupancy_v1/all/heatmap_jaccard.png`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/all/heatmap_jaccard.png)
- [K-562 热图](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/K_562/heatmap_jaccard.png)、[Hep G2 热图](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/Hep_G2/heatmap_jaccard.png)
- 每个复合物的 p 和 FDR：[`validation_v1_2/sensitivity/b500_k05/complex_recovery.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/sensitivity/b500_k05/complex_recovery.tsv)
- 汇总，含同一套蛋白比较和前 50 对：[`validation_v1_2/sensitivity/b500_k05/summary.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/sensitivity/b500_k05/summary.json)
- 复合物成员覆盖：[`validation_v1_1/protein/complex_coverage.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_1/protein/complex_coverage.tsv)
- BAF 质控：[`validation_v1_2/study/baf_hepg2_k562_qc.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/baf_hepg2_k562_qc.tsv)

## 3. 研究层面验证：大量“共占据”来自单一研究

### 为什么做

ChIP-Atlas 中，同一研究的多个实验往往共用抗体、流程和 peak calling，它们不是独立证据。v1 的候选蛋白对排名靠前的，有不少可能只是同一个研究的批次特征。

### 做了什么

- 从 ENA 获取每个实验的 SRA 研究编号：132,923 个实验中查到 132,859 个。
- 候选对：565 个 Complex Portal 同复合物对，加上 300 个共占据最高的未收录对。
- 每一对做三项检验，每个子集都按自己的实验数重算占据阈值：
  1. **跨研究：** 只用 A 在没做过 B 的研究里的实验，对比 B 在没做过 A 的研究里的实验。
  2. **留一研究：** 逐个去掉一个研究，取最小 Jaccard。
  3. **同一细胞背景内重复：** 在同一细胞类型内重复第 1 项。
- 分层：
  - 高可信：跨研究 Jaccard ≥ 全量的一半且 ≥ 第 95 百分位（0.074），同时留一最小值 ≥ 全量的一半；
  - 中等：只满足跨研究条件；
  - 覆盖不足：有一方只有一个研究；
  - 依赖研究：其余。
- 第 2 项是在看到 CTCF–ESR1 的案例后补加的，属于事后标准，报告中已注明。
- 另外，对每个蛋白计算“研究影响度”：1 − Jaccard（全部实验的占据，去掉某一研究后的占据），取所有研究中的最大值。

### 得到什么结果

| 候选来源 | 高可信（其中同背景重复） | 中等 | 覆盖不足 | 依赖研究 |
|---|---|---|---|---|
| Complex Portal（565） | 83（45） | 37 | 67 | 378 |
| 未收录的高共占据对（300） | 63（**47**） | 43 | 106 | 88 |

三项都通过的未收录蛋白对（括号内为重复所在的细胞类型和 Jaccard），全部是文献中已知的功能伙伴：
- CTCF–RAD21（HAP1，0.65）、CTCF–STAG1/SMC1A（HMEC）；
- AP-1 二聚体：FOSL1–JUNB、JUN–JUNB、FOS–JUNB；
- AP-1 与 BAF：JUN–SMARCA4、JUNB/FOSL2–SMARCA2/4；
- TEAD4–YAP1（MCF-7）、POU5F1–SOX2（hESC H9）、NELFCD–SUPT5H（DLD-1）、BRD2–BRD4、BRD4–MED1（MM.1S，0.52）、GATA1–TAL1（K-562）。

被正确排除的单研究假象：
- ZNF34–ZNF781–ZNF697 的 Jaccard 为 0.65–0.69，但每个蛋白都只有 1 个研究；
- CTCF–ESR1 的全量 Jaccard 为 0.366，但只要去掉 SRP158854，就降到 0.025。SRP158854 是 MCF-7 中 ESR1 的时间序列，58 个重复、每个约 56,000 个 peak，而 ESR1 实验的中位数是 5,334。仅这一个研究就决定了 ESR1 一半的占据区间。“跨研究”检验只排除两个蛋白共有的研究，所以漏掉了这一例；留一检验抓到了。

研究影响度主要取决于蛋白的研究数：

| 研究数 | 蛋白数 | 影响度中位数 |
|---|---|---|
| 2 | 182 | 0.92 |
| ≥ 10 | 147 | 0.35 |

研究数 ≥ 10 的蛋白中，有 32 个被单一研究显著改变（影响度 ≥ 0.5）。

### 结论

实验数多不等于证据独立。研究来源是 ChIP-Atlas 共占据中最强的混杂因素之一。共占据候选必须同时通过跨研究检验和留一研究检验，最好还能在同一细胞背景中被独立研究重复。按这一标准，目前留下的未收录候选全部是已知的功能关联：这说明标准有效，也说明暂时还没有发现可靠的新模块。

对应证据：
- 每对的分层和同背景重复：[`validation_v1_2/study/pair_tiers.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/pair_tiers.tsv)
- 留一检验和跨研究检验：[`validation_v1_1/protein/pair_study_validation.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_1/protein/pair_study_validation.tsv)
- 研究影响度：[`validation_v1_2/study/protein_study_influence.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/protein_study_influence.tsv)
- SRP158854 元数据：[`validation_v1_2/study/SRP158854_experiments.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/SRP158854_experiments.tsv)

## 4. 实验层面：约一半的结构来自同一研究或相同测序深度

### 为什么做

把每个 ChIP 实验看作一个全基因组占据向量，可以问：结合模式的差异主要由什么决定？如果相近的实验只是同一研究或相同测序深度，那么“按蛋白”或“按细胞类型”分开的结构就不能作为生物学解释。

### 做了什么

- 对 29,900 个实验做 TF-IDF 加 SVD（50 维），每个实验取余弦距离最近的 10 个实验作为近邻。
- 统计近邻中与自身标签相同的比例，并与随机期望比较：κ = (观察 − 期望) / (1 − 期望)。
- 5 种近邻限制：
  - V0：原始；
  - V1：去掉第 1 主成分；
  - V2：近邻限同一 peak 数十分位；
  - V3：近邻限不同研究；
  - V4：V2 和 V3 同时施加。
- 随机期望按每个实验自己的可选近邻集合计算，不用全局标签频率。
- 置换检验：在 peak 数十分位内打乱标签，近邻图固定，共 200 次。

### 得到什么结果

| 变体 | 蛋白 κ | 细胞类型 κ |
|---|---|---|
| V0 原始 | 0.43 | 0.46 |
| V1 去掉第 1 主成分 | 0.43 | 0.46 |
| V2 同一 peak 数十分位 | 0.33 | 0.35 |
| V3 不同研究 | 0.30 | 0.28 |
| V4 = V2 + V3 | 0.25 | 0.23 |

所有置换 p 都在下限 0.005。

细分视角（V0 → V4 的 κ）：

| 视角 | V0 | V4 | 解读 |
|---|---|---|---|
| K-562 内，按蛋白 | 0.26 | 0.09 | 减弱 |
| Hep G2 内，按蛋白 | 0.09 | 0.013（p = 0.01） | 只剩弱信号 |
| CTCF 内，按细胞类型 | 0.19 | 0.024 | 只剩弱信号 |
| MCF-7 内，按蛋白 | 0.50 | 0.29 | 保留 |
| ESR1 内，按细胞类型 | 0.64 | 0.41 | 保留 |
| FOXA1 内，按细胞类型 | 0.65 | 0.39 | 保留 |
| AR 内，按细胞类型 | 0.43 | 0.16 | 减弱 |

### 结论

- 蛋白身份和细胞背景确实塑造了全基因组结合模式。但未经控制的近邻统计会把约一半的“结构”错误地归给生物学因素，其中研究来源的影响比测序深度更大。
- Hep G2 和 CTCF 的强结论不成立。这只说明在当前数据中没有检测到稳定的结构，**不能**反过来推出“CTCF 跨细胞完全保守”。
- MCF-7、ESR1 和 FOXA1 的结构在严格控制后仍然存在，值得在后续的背景特异性分析中继续追踪。

对应证据：
- t-SNE 图（按蛋白类别和细胞类型着色）：[`experiment_clustering_v1/tsne.png`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/experiment_clustering_v1/tsne.png)
- 全部变体和视角：[`validation_v1_2/experiment/experiment_confounder_sensitivity.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/experiment/experiment_confounder_sensitivity.tsv)

## 5. 区域层面：20 类占据组合，稳定性因类而异

### 为什么做

蛋白层面回答“谁和谁一起出现”，区域层面回答“哪些区域有相似的蛋白组合”。后者可以直接变成基因组注释。

### 做了什么

- 取至少被 3 个蛋白占据的 1,531,237 个区间，做 TF-IDF 和 SVD（30 维），再用 k-means 聚类。k = 20 是预先设定的选择规则。
- 稳定性检验：
  - k = 10 / 20 / 30 之间的一致性；
  - 另取 5 个随机种子；
  - 5 次 80% 子抽样；
  - 去 HOT 后重新聚类。
- 每一类的稳定性：11 次重跑中，与原类最佳匹配的 Jaccard 取中位数。

### 得到什么结果

整体一致性：

| 比较 | ARI |
|---|---|
| 换随机种子 | 0.69–0.74 |
| 80% 子抽样 | 0.64–0.76 |
| 去 HOT 后重新聚类 | 0.63 |
| k = 20 与 k = 30 | 0.68 |

各类按稳定性分组：

| 稳定性 | 类别 |
|---|---|
| 最稳定 | C11 CTCF–黏连蛋白（0.96） |
| 稳定 | C05 AR–FOXA1–HOXB13（0.91）、C02 AP-1–TEAD–BAF（0.87）、C19 TAL1–GATA1（0.86）、C20 MAF 小蛋白–NFE2（0.95） |
| 中等 | C03 HOT 启动子（0.76）、C04 HNF4（0.65）、C10 PU.1–IRF8（0.62） |
| 不稳定 | C17 PBX1–MYB–TCF3（0.27）、C15 MAF–TP63（0.45）、C01 神经嵴（0.46）、C08 多能性（0.48） |

C07（HMGA1，0.88）和 C09（PPARA，0.88）在计算上稳定，但由单一研究驱动：
- HMGA1 的 23 个实验中有 18 个来自 SRP467379；
- PPARA 的 11 个实验中有 6 个来自 SRP278993；
- 去掉该研究后，两者的占据区间几乎完全改变（影响度 0.999）。

### 结论

区域类别能对应已知的调控程序：CTCF–黏连蛋白绝缘子、AP-1–TEAD 增强子、雄激素受体–FOXA1、红系 TAL1–GATA1 等。但 20 类不是天然的离散类别，各类的可信度需要逐类标注。**计算上稳定不等于生物学可信**：C07 和 C09 应标为“单一研究驱动”，C15 和 C17 不应单独解释。

对应证据：
- 区域类别 BED（bigBed，可在 IGV 中查看）：[`region_classes_v1/region_classes.bb`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/region_classes_v1/region_classes.bb)
- 各类组成：[`region_classes_v1/classes.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/region_classes_v1/classes.tsv)
- 稳定性：[`validation_v1_2/region/region_stability.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/region/region_stability.tsv)、[`summary.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/region/summary.json)

## 6. 参数敏感性：结论不依赖区间大小和阈值

### 为什么做

500 bp 的区间和 5% 的占据阈值都是人为选定的。需要确认主要结论不是这组参数的产物。

### 做了什么

用 250 / 500 / 1000 bp 的区间和 2.5% / 5% / 10% 的阈值，共 5 种组合，重算蛋白层面的全部指标。

### 得到什么结果

| 设置 | AUROC（CI） | FDR ≤ 0.05：全部 / 去冗余 | CTCF–RAD21 |
|---|---|---|---|
| 250 bp，5% | 0.809（0.769–0.851） | 165 / 119 | 0.693 |
| 500 bp，5% | 0.811（0.766–0.849） | 172 / 115 | 0.704 |
| 1000 bp，5% | 0.808（0.767–0.847） | 167 / 113 | 0.713 |
| 500 bp，2.5% | 0.798（0.749–0.838） | 166 / 107 | 0.659 |
| 500 bp，10% | 0.819（0.781–0.857） | 193 / 131 | 0.728 |

11 个指定物理复合物中，10 个在所有设置下 FDR 都 ≤ 0.05。唯一的例外是核心 Mediator（只有 3 个亚基），在 10% 阈值下 FDR 为 0.057。

### 结论

复合物找回对区间大小和阈值都稳健。Mediator 的证据最弱，应表述为“检测到的 Mediator 亚基有共占据富集”。

对应证据：
- [`validation_v1_2/sensitivity/<variant>/summary.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/sensitivity/)

## 讨论

1. **这一部分对 PMA 的意义首先是质量验证。** 从 ChIP-Atlas 汇总的占据参考能够在全基因组尺度上重现已知的蛋白复合物和功能伙伴关系。这说明 Figure 1D 的占据数据保留了真实的生物学结构，可以作为 protein–motif association 的输入。
2. **最重要的方法学教训是研究来源。** v1 中许多看似最强的结果，包括排名最高的非复合物蛋白对、Hep G2 和 CTCF 的实验层面结构、C07 和 C09 两个区域类别，都在控制研究来源后减弱或消失。Figure 2 的 protein–motif 统计校准需要沿用同一原则：证据以独立研究为单位计数，并区分实验层面和生物样本层面的重复。
3. **共占据 ≠ 复合物。** PR-AUC 只有 0.026，通过严格检验的未收录候选又全部是已知的功能关联，这说明共占据更适合作为已有知识的定量参考和质量对照，而不是发现新复合物的工具。在新模块提名之前，至少还需要：
   - Complex Portal 注释审核，区分物理复合物和功能关联；
   - 启动子、增强子和染色质状态的注释富集；
   - 同一细胞背景内的独立重复。
4. **局限：**
   - 汇总的是跨细胞的 peak 共占据，没有单细胞或同一样本内的共结合信息；
   - 研究来源只能识别 SRA 研究，无法识别同一批原始 reads 在不同研究下的重复提交；
   - 广度匹配只控制了占据区间数，没有控制启动子或增强子偏好；
   - 很多复合物只有少数成员被 ChIP 测过，例如 Mediator 只有 3/13。
5. **下一步（待审阅和用户决定）：**
   - 把 v1.2 送 GPT 审阅；
   - 在区域 BED 中加入每类的稳定性和“单一研究驱动”标签；
   - 决定 SRP158854 和 Hep G2 BAF 实验的处理方式，目前都只做了标记。

## 版本记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-10-21 | 汇总分析 v1（三层聚类）、v1.1（研究来源、广度匹配 + FDR、留一研究、实验混杂）和 v1.2（分层、同背景重复、按条件的期望、区间大小与阈值、区域稳定性） |
