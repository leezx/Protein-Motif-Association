# Figure 1G result — 区域层面：20 类占据组合，稳定性和研究支持因类而异

> **文档性质：** 内部分析结果稿（非投稿版本）
> **当前版本：** v0.1，2026-10-21（对应分析 v1 → v1.2）
> **对应图位：** Figure 1G。这是三层聚类中的区域层面；蛋白层面见 1E，实验层面见 1F。
> **代码：** 分支 `task_20261020_chipatlas_light_bed`。分类用 `scripts/04a_chipatlas/14_region_classes.py`，稳定性检验用 `21_region_stability.py`，研究影响度用 `20_study_influence.py`，作图用 `22_figure1_clustering_panels.py`。设计见 §15 和 §17。
> **结果边界：** k = 20 是预先设定的选择规则下的结果，并不意味着基因组中天然存在 20 种离散的调控类别。

![Figure 1G](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1G_region_classes.png)

图文件：[PNG](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1G_region_classes.png) / [PDF](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1G_region_classes.pdf)

## Result overview

- 至少被 3 个蛋白占据的 1,531,237 个 500 bp 区间，按蛋白组合分成 20 类。大多数类对应已知的调控程序：
  - CTCF–黏连蛋白绝缘子；
  - AP-1–TEAD–BAF 增强子；
  - HNF4；
  - AR–FOXA1–HOXB13；
  - TAL1–GATA1；
  - PU.1–IRF8；
  - HOT 启动子。
- 整体中等稳定：换随机种子、做子抽样或去掉 HOT 区间后，ARI 在 0.63–0.76 之间。
- 各类之间稳定性差别很大。C11（CTCF–黏连蛋白）最稳定，C17 和 C15 不稳定。
- C07（HMGA1）和 C09（PPARA）在计算上稳定，但几乎完全由单一研究驱动。

## 1. 区域分类

### 为什么做

蛋白层面回答“哪些蛋白经常一起出现”；区域层面回答“哪些区域有相似的蛋白组合”。后者可以直接转成基因组注释，以 BED 和 bigBed 格式发布。

### 做了什么

1. 取 Figure 1E 中的“蛋白 × 500 bp 区间”占据矩阵，保留至少被 3 个蛋白占据的区间。
2. 每个区间先按其蛋白数归一化，再做 TF-IDF 加权和 SVD（30 维），最后用 MiniBatch k-means 分别取 k = 10、20、30。
3. 预先设定的规则：除非另一个 k 的 silhouette 系数比 k = 20 高出 0.05 以上，否则取 k = 20。
4. 各类按区间数从多到少编号，并列出在本类中富集的蛋白。

### 得到什么结果

20 类及其最富集的蛋白如下（图 1G-A，括号内为区间数）。

| 类 | 主要蛋白（区间数） |
|---|---|
| C01 | HAND2–PHOX2B–EBF3，神经嵴（106,287） |
| C02 | JUNB–YAP1–FOSL1，AP-1–TEAD–BAF（102,829） |
| C03 | HOT 启动子（102,104），每区间中位数 80 个蛋白 |
| C04 | HNF4A（89,410） |
| C05 | AR–HOXB13–FOXA1（85,670） |
| C06 | SOX10–MITF（85,530） |
| C07 | HMGA1（85,352） |
| C08 | 多能性：POU5F1–SOX2–NANOG（85,048） |
| C09 | PPARA（82,502） |
| C10 | PU.1–IRF8–LYL1（77,738） |
| C11 | CTCF–黏连蛋白（76,933） |
| C12 | NR1D1–PRC2（73,502） |
| C13 | CEBP（70,766） |
| C14 | BATF–IRF4–RELB（67,407） |
| C15 | MAF–TP63（64,664） |
| C16 | NCOA3–GRHL2（62,386） |
| C17 | PBX1–MYB–TCF3（61,899） |
| C18 | OTX2–NEUROD1（59,488） |
| C19 | TAL1–GATA1–CBFA2T3（49,475） |
| C20 | MAF 小蛋白–NFE2（42,247） |

- C11 是唯一以结构蛋白/黏连蛋白为主的类。C12 中组蛋白修饰酶和转录机器的比例较高。
- 绝大多数类以序列特异 TF 为主，这与纳入的蛋白以 TF 为主一致。

## 2. 稳定性与研究支持（图 1G-B、C）

### 为什么做

k-means 的结果依赖随机种子、k 的取值和输入区间。每一类的生物学解读需要先确认这个类本身是稳定的。另外，在计算上稳定的类，也可能只是反映了某一个研究的数据。

### 做了什么

1. 跨分辨率比较：k = 10 与 20、k = 20 与 30 之间的 ARI 和 NMI。
2. 另取 5 个随机种子，重新做 SVD 和 k-means。
3. 做 5 次 80% 区间子抽样。
4. 去掉 HOT 区间后重新聚类。
5. 每一类在上述 11 次重跑中找到最佳匹配类，计算两者的 Jaccard，报告中位数和最小值。
6. 标记“单一研究驱动”：一个类的主导蛋白在本类区间中的占据比例 ≥ 0.9，并且该蛋白的研究影响度 ≥ 0.9（见 Figure 1E-F）。

### 得到什么结果

**整体稳定性（图 1G-C）**

| 比较 | ARI |
|---|---|
| 5 个随机种子 | 0.69–0.74 |
| 5 次 80% 子抽样 | 0.64–0.76 |
| 去 HOT | 0.63 |
| k = 20 与 30 | 0.68 |
| k = 10 与 20 | 0.39 |

**各类稳定性（图 1G-B，11 次重跑最佳匹配 Jaccard 的中位数）**

- **最稳定：** C11 CTCF–黏连蛋白（0.96，最小值 0.84）。
- **稳定：**

  | 类 | 中位数 | 最小值 |
  |---|---|---|
  | C20 | 0.95 | 0.09 |
  | C05 | 0.91 | 0.61 |
  | C13 | 0.89 | 0.15 |
  | C02 | 0.87 | 0.62 |
  | C06 | 0.86 | 0.34 |
  | C19 | 0.86 | 0.29 |
  | C16 | 0.85 | 0.20 |

  其中不少类中位数高、最小值低，说明它们在个别重跑中会被合并或拆开。
- **不稳定：** C17（0.27）、C15（0.45）、C01（0.46）、C08（0.48）、C14（0.53）。
- **单一研究驱动：**
  - C07 HMGA1：23 个实验中 18 个来自 SRP467379；
  - C09 PPARA：11 个实验中 6 个来自 SRP278993。

  去掉这两个研究后，对应蛋白的占据区间几乎完全改变（影响度 0.999）。按上面的规则，被标记的只有这两类。

### 结论

- 区域类别能对应已知的调控程序，但 20 类不是天然的离散类别，每一类的可信度需要单独标注。
- **计算上稳定不等于生物学可信。** C07 和 C09 应标为“单一研究驱动”，不作调控程序注释。
- C15 和 C17 不应单独解释。
- C11（CTCF–黏连蛋白）、C05（AR–FOXA1–HOXB13）、C02（AP-1–TEAD–BAF）、C19（TAL1–GATA1）既稳定，又对应已知生物学，是最可靠的几类。

对应证据：
- 区域类别 BED（bigBed，可在 IGV 中查看）：[`region_classes_v1/region_classes.bb`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/region_classes_v1/region_classes.bb)
- 各类组成：[`region_classes_v1/classes.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/region_classes_v1/classes.tsv)；富集蛋白：[`class_proteins.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/region_classes_v1/class_proteins.tsv)；silhouette 系数：[`silhouette.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/region_classes_v1/silhouette.tsv)
- 稳定性：[`validation_v1_2/region/region_stability.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/region/region_stability.tsv)、[`summary.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/region/summary.json)
- 研究影响度：[`validation_v1_2/study/protein_study_influence.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/study/protein_study_influence.tsv)

## 讨论

1. **作为 PMA 的注释层：** 区域类别可以直接用于 peak 注释（设计文档中的 Application C），例如说明“这个 peak 落在 CTCF–黏连蛋白类区域”。发布时应同时附上每类的稳定性和研究支持标签。
2. **区间的成员身份：** 区间属于哪一类，很大程度上取决于“在哪些细胞里测过哪些蛋白”。所以类别反映的是现有数据覆盖下的组合模式，不是完整的调控图谱。
3. **待做（L2/L3，待审阅和用户决定）：**
   - 在区域 BED 中加入每类的稳定性分数和 `single_study_driven` 标签；
   - 做启动子、增强子和染色质状态的注释富集；
   - 检验区间大小改变后，类别是否保持。

## 版本记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-10-21 | 汇总 v1（20 类）与 v1.2（跨分辨率、随机种子、子抽样、去 HOT 的稳定性，以及单一研究标记） |
