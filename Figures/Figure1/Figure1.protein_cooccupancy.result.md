# Figure 1E result — 蛋白层面共占据：找回已知复合物，候选对必须经过研究层面检验

> **文档性质：** 内部分析结果稿，非投稿版本。
> **当前版本：** v0.1，2026-10-21。对应分析版本 v1 → v1.1 → v1.2。
> **对应图位：** Figure 1E。三层聚类中的蛋白层面；实验层面见 1F，区域层面见 1G。占据参考本身见 1D（`Figure1.chipatlas_occupancy.result.md`）。
> **代码：** 分支 `task_20261020_chipatlas_light_bed`，脚本 `scripts/04a_chipatlas/12, 16, 18, 19, 20`。作图脚本是 `22_figure1_clustering_panels.py`，只读取已有结果表，不重新计算。
> **设计：** `docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md` §13、§16、§17，均在计算前提交。
> **审阅：** GPT 审阅 v1 为 REVISE；审阅 v1.1 为局部 REVISE，并批准开始 L2；v1.2 待审。
> **结果边界：** 分析的是跨实验、跨细胞汇总的 peak 共占据。它不是同一细胞内的共同结合，更不是物理复合物。目前不提名高可信新模块。

![Figure 1E](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1E_protein_cooccupancy.png)

图文件：[PNG](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1E_protein_cooccupancy.png) / [PDF](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1E_protein_cooccupancy.pdf)

## Result overview

如果 ChIP-Atlas 占据参考保留了真实的生物学结构，同一复合物的成员应在全基因组上占据相似的区域。我们得到以下结果：

1. **区分能力：** 用 Jaccard 区分 Complex Portal 同复合物的蛋白对和其他蛋白对，AUROC = 0.811（95% CI 0.766–0.849）。
2. **复合物层面：** 广度匹配后 FDR ≤ 0.05 的复合物有 172/373 个，按成员组合去冗余后为 115/298。
3. **稳健性：** 区间取 250–1000 bp、占据阈值取 2.5–10%，以上结果基本不变。
4. **局限：** PR-AUC 只有 0.026，共占据不能单独预测复合物。
5. **研究来源的影响：** Complex Portal 未收录、共占据最高的 300 对中，只有 47 对通过了跨研究、留一研究、同细胞背景重复三项检验，而且全部是已知的功能伙伴。

## 1. 共同表示：蛋白 × 500 bp 区间占据矩阵

### 为什么做

蛋白、实验、区域三个层面需要同一个输入，结论之间才能比较。

### 做了什么

- **输入：** Figure 1D 的实验级 BED（TF 和其他蛋白，加上 RNA 聚合酶）。只保留 6 个功能类别的蛋白，并去掉 ENCODE 黑名单区域。
- **占据的定义：** 蛋白 p 占据某个 500 bp 区间，要求至少有 k_p = max(2, ⌈0.05 n_p⌉) 个不同实验在该区间有 peak，其中 n_p 是蛋白 p 的实验数。
- **蛋白筛选：** 只保留占据区间数 ≥ 500 的蛋白。
- **HOT 区间：** 被占据蛋白数排前 1% 的区间。
- **相似度：** 两个蛋白的 Jaccard 相似度，在去 HOT 后的区间上计算。

### 得到什么结果

| 项目 | 数量 |
|---|---|
| 蛋白 | 808 个 |
| 实验 | 27,240 个 |
| SRA 研究（研究来源 100% 可查） | 2,901 个 |
| 被占据的区间 | 3,477,832 个 |
| 去 HOT 后的区间 | 3,442,930 个 |
| HOT 阈值 | 143 个蛋白 |

热图上有清楚的块状结构（图 1E-A）。

## 2. 已知复合物能被找回，且不依赖参数（图 1E-B、C、D）

### 为什么做

找回已知复合物是阳性对照。如果找不回来，后面提名未知模块就没有基础。

### 做了什么

- **配对层面：** 以 Complex Portal 为独立基准，计算 AUROC 和 PR-AUC。置信区间按蛋白重抽样得到，因为同一个蛋白参与多个蛋白对，蛋白对之间不独立。
- **复合物层面：**
  - 统计量是复合物成员两两 Jaccard 的中位数。
  - 背景分布：把每个成员换成占据广度在同一十分位的随机蛋白，抽 10,000 次。
  - 对全部条目做 BH 校正；成员组合完全相同的条目只保留 p 最小的一个，再做一次 BH 校正。
- **背景模型和 HOT 去除的作用：** 同一批复合物在三种设置下各算一次，看显著数如何变化。
- **参数敏感性：** 5 组参数，即区间大小 250 / 500 / 1000 bp，占据阈值 2.5% / 5% / 10%。

### 得到什么结果

**参数敏感性（图 1E-B）**

| 设置 | AUROC（CI） | PR-AUC（随机基线） | FDR ≤ 0.05：全部 / 去冗余 |
|---|---|---|---|
| 250 bp，5% | 0.809（0.769–0.851） | 0.026（0.0017） | 165 / 119 |
| **500 bp，5%** | 0.811（0.766–0.849） | 0.026（0.0017） | 172 / 115 |
| 1000 bp，5% | 0.808（0.767–0.847） | 0.024（0.0018） | 167 / 113 |
| 500 bp，2.5% | 0.798（0.749–0.838） | 0.025（0.0017） | 166 / 107 |
| 500 bp，10% | 0.819（0.781–0.857） | 0.029（0.0017） | 193 / 131 |

**背景模型和 HOT 去除的作用（图 1E-C）**

| 设置 | FDR ≤ 0.05：全部 / 去冗余 |
|---|---|
| 全部区间 + 大小匹配背景 | 79 / 46 |
| 去 HOT + 大小匹配背景 | 139 / 94 |
| 去 HOT + 广度匹配背景 | 172 / 115 |

广度匹配背景的中位数更高，但分布更窄，所以显著的复合物反而更多。它的设定更合理，但并不更保守。

**指定的 11 个物理复合物（图 1E-D）**

- 有丝分裂黏连蛋白（STAG1、STAG2 两种变体）、GBAF、NELF、SIN3A、PRC2.1、MBD2/NuRD、MBD3/NuRD、CoREST、TFIID：在 5 组参数下 FDR 都 ≤ 0.05。
- 核心 Mediator 只检测到 13 个亚基中的 3 个，10% 阈值下 FDR = 0.057。
- 阴性对照：减数分裂黏连蛋白不显著（p ≈ 0.6），符合体细胞数据的预期。

**CTCF 与黏连蛋白**

CTCF 不是黏连蛋白复合物的成员，因此单独作为功能关联报告。CTCF 与 5 个亚基的 Jaccard 为 0.49–0.70，其中与 RAD21 为 0.704，高于黏连蛋白亚基之间的中位数 0.558。

**K-562 与 Hep G2：用两者共有的 183 个蛋白比较（图 1E-B 红色）**

| 细胞系 | AUROC（CI） |
|---|---|
| K-562 | 0.779（0.698–0.857） |
| Hep G2 | 0.605（0.493–0.744） |

两个细胞系各取前 50 对，只重合 2 对（CTCF–RAD21、HDAC1–HDAC2）。Hep G2 的 BAF 实验 peak 数很低（111–3,522），每个亚基只有一个研究；K-562 的同类实验为 2,000–46,000 个 peak。

### 结论

- 已知复合物的成员在全基因组上共占据。这一信号在控制占据广度、FDR 校正、改变区间大小和阈值之后都成立，可以作为占据参考质量的阳性对照。
- PR-AUC 的绝对值低，说明共占据有富集能力，但不能单独用来预测物理复合物。
- 两种细胞系各自找回的是不同的一批复合物。Hep G2 较弱，一个可能的原因是部分复合物的实验产出低。
- 广度匹配背景并不比大小匹配背景更严格。v1.1 报告中“更严格”的说法有误，已更正。

对应证据：
- [Jaccard 热图](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/all/heatmap_jaccard.png)，以及 [K-562](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/K_562/heatmap_jaccard.png) 和 [Hep G2](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/cooccupancy_v1/Hep_G2/heatmap_jaccard.png) 单独的热图
- 每个复合物的 p 值和 FDR：[`validation_v1_2/sensitivity/b500_k05/complex_recovery.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/sensitivity/b500_k05/complex_recovery.tsv)
- 5 组参数的汇总：[`validation_v1_2/sensitivity/`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/sensitivity/)
- 复合物成员覆盖：[`validation_v1_1/protein/complex_coverage.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_1/protein/complex_coverage.tsv)
- BAF 质控：[`validation_v1_2/study/baf_hepg2_k562_qc.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/baf_hepg2_k562_qc.tsv)

## 3. 研究层面验证：大量“共占据”来自单一研究（图 1E-E、F）

### 为什么做

同一研究里的多个实验通常共用抗体、实验流程和 peak calling 方法，它们不是独立证据。所以，排名靠前的候选对可能只是同一研究的批次特征。

### 做了什么

- **研究编号：** 从 ENA 获取每个实验所属的 SRA 研究编号。
- **候选对：** Complex Portal 同复合物对 565 对，加上 Complex Portal 未收录、共占据最高的 300 对。
- **三项检验：** 每个子集都按自己的实验数重新计算占据阈值。
  1. 跨研究：只用 A 在没做过 B 的研究中的实验，与 B 在没做过 A 的研究中的实验比较。
  2. 留一研究：每次去掉一个研究重算，取最小的 Jaccard。
  3. 同细胞背景重复：在同一种细胞类型内重做第 1 项。
- **分层：**

  | 层级 | 条件 |
  |---|---|
  | Tier 1 | 跨研究 Jaccard ≥ 全量的一半且 ≥ 第 95 百分位（0.074），同时留一最小值 ≥ 全量的一半 |
  | Tier 2 | 只满足跨研究条件 |
  | 覆盖不足 | 两个蛋白中有一个只有 1 个研究 |
  | 依赖研究 | 其余 |

  留一条件是看到 CTCF–ESR1 的案例后补加的事后标准，报告中已注明。
- **研究影响度：** 对每个蛋白，计算 1 − Jaccard（全部实验的占据集合，去掉某一个研究后的占据集合），在所有研究中取最大值。

### 得到什么结果

**候选对分层（图 1E-E）**

| 候选来源 | Tier 1（其中同背景重复） | Tier 2 | 覆盖不足 | 依赖研究 |
|---|---|---|---|---|
| Complex Portal（565） | 83（45） | 37 | 67 | 378 |
| 未收录（300） | 63（**47**） | 43 | 106 | 88 |

三项检验都通过的未收录对全部是已知的功能伙伴，例如：
- CTCF–RAD21（HAP1，Jaccard 0.65）、CTCF–STAG1/SMC1A；
- AP-1 二聚体：FOSL1–JUNB、JUN–JUNB、FOS–JUNB；
- AP-1 与 BAF：JUN–SMARCA4、JUNB/FOSL2–SMARCA2/4；
- TEAD4–YAP1、POU5F1–SOX2、NELFCD–SUPT5H、BRD2–BRD4、BRD4–MED1（MM.1S，0.52）、GATA1–TAL1。

被正确排除的单研究假象：
- **ZNF34–ZNF781–ZNF697：** Jaccard 0.65–0.69，但每个蛋白都只有 1 个研究。
- **CTCF–ESR1：** 全量 Jaccard 0.366，去掉 SRP158854 后降到 0.025。SRP158854 是 MCF-7 中的 ESR1 时间序列，有 58 个重复，每个约 56,000 个 peak；ESR1 全部实验的 peak 数中位数是 5,334。这一个研究就决定了 ESR1 一半的占据区间。

**研究影响度（图 1E-F）**

- 研究影响度主要取决于研究数：只有 2 个研究的蛋白，影响度中位数为 0.92；有 ≥ 10 个研究的蛋白为 0.35。
- 在 ≥ 10 个研究的蛋白中，有 32 个的影响度 ≥ 0.5。
- 几个代表蛋白：

| 蛋白 | 研究数 | 影响度 |
|---|---|---|
| CTCF | 271 | 0.07 |
| SMARCA4 | 75 | 0.16 |
| ESR1 | 147 | 0.48 |
| HMGA1 | 4 | 0.999 |
| PPARA | 5 | 0.999 |

### 结论

- 实验数多不等于证据独立。研究来源是 ChIP-Atlas 共占据分析中最强的混杂因素之一。
- 共占据候选必须同时通过跨研究和留一研究检验，最好还要在同一细胞背景中被独立研究重复。
- 按这一标准，目前留下的未收录候选全部是已知的功能关联。这说明标准有效，也说明目前还没有可靠的新模块。

对应证据：
- 候选对分层和同背景重复：[`validation_v1_2/study/pair_tiers.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/pair_tiers.tsv)
- 留一研究和跨研究检验：[`validation_v1_1/protein/pair_study_validation.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_1/protein/pair_study_validation.tsv)
- 研究影响度：[`validation_v1_2/study/protein_study_influence.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/protein_study_influence.tsv)
- SRP158854 的实验列表：[`validation_v1_2/study/SRP158854_experiments.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/SRP158854_experiments.tsv)

## 讨论

1. **PMA 的质量验证：** 汇总后的占据参考能在全基因组尺度上重现已知的复合物和功能伙伴关系，可以作为 protein–motif association 的输入。
2. **研究来源这条教训要延续到 Figure 2：** 在 protein–motif 统计校准中，证据应以独立研究为单位计数，并区分实验层面的重复和生物样本层面的重复。
3. **共占据 ≠ 复合物：** 共占据更适合作为已有知识的定量参考和质量对照，而不是发现新复合物的工具。提名新模块之前，至少还需要三件事：
   - 审核 Complex Portal 注释，区分物理复合物和功能关联；
   - 做启动子、增强子和染色质状态的注释富集；
   - 在同一细胞背景中找到独立研究的重复。
4. **局限：**
   - 没有同一细胞或同一样本内共同结合的信息。
   - 研究来源只能识别到 SRA 研究，识别不出同一批原始 reads 在不同研究下的重复提交。
   - 广度匹配只控制了占据区间的数量，没有控制启动子或增强子偏好。
   - 很多复合物只有少数成员被测过。

## 版本记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-10-21 | 汇总 v1（蛋白层面聚类）、v1.1（研究来源、广度匹配加 FDR、留一研究）和 v1.2（分层、同背景重复、区间大小与阈值敏感性、HOT 与背景模型的分解）；作图 commit 见脚本 `22` |
