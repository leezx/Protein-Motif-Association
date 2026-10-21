# Figure 1F result — 实验层面聚类：约一半的结构来自同一研究或相同测序深度

> **文档性质：** 内部分析结果稿，非投稿版本。
>
> **当前版本：** v0.1，2026-10-21，对应分析版本 v1 → v1.1 → v1.2。
>
> **对应图位：** Figure 1F，是三层聚类中的实验层面。蛋白层面见 1E，区域层面见 1G。
>
> **代码：** 分支 `task_20261020_chipatlas_light_bed`，脚本为 `scripts/04a_chipatlas/13_experiment_clustering.py` 和 `17_experiment_sensitivity.py`；作图脚本为 `22_figure1_clustering_panels.py`。设计见 §14、§16、§17。
>
> **结果边界：** 近邻统计只描述实验之间结合模式的相似性，不能拆解出各因素各自解释了多少方差。

![Figure 1F](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1F_experiment_clustering.png)

图文件：[PNG](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1F_experiment_clustering.png) / [PDF](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/figure1_clustering_v1_2/Figure1F_experiment_clustering.pdf)

## Result overview

我们把每个 ChIP 实验看作一个全基因组占据向量，检验结合模式的差异主要由什么决定：蛋白身份、细胞背景，还是研究来源和测序深度这类技术因素。

- **未加控制：** 实验最近的 10 个邻居中，同蛋白和同细胞类型的比例都远高于随机期望，κ 分别为 0.43 和 0.46。
- **加控制后：** 把近邻限定在同一 peak 数十分位、且来自不同研究，κ 降到 0.25 和 0.23。
- **细分背景：**
  - Hep G2 内按蛋白、CTCF 内按细胞类型的结构，控制后只剩很弱的信号；
  - MCF-7 内按蛋白、ESR1 内和 FOXA1 内按细胞类型的结构，控制后大体保留。

## 1. 实验嵌入与近邻统计

### 为什么做

在实验层面，我们要回答结合模式的差异主要来自哪里。要是相似的实验往往只是同一研究或测序深度相近的实验，那么“按蛋白”或“按细胞类型”分开的结构就不能当作生物学解释。

### 做了什么

- **嵌入：** 对 29,900 个实验的区间占据做 TF-IDF 和 SVD（50 维）。每个实验按余弦距离取最近的 10 个实验作为邻居。
- **统计量：** 计算邻居中与自身标签相同的比例，再算 κ = (观察 − 期望) / (1 − 期望)。随机期望按每个实验自己可选的邻居集合计算，不用全局标签频率。
- **5 种邻居限制：**

| 变体 | 邻居范围 |
|---|---|
| V0 | 不限制 |
| V1 | 去掉 SVD 第 1 成分后重新取邻居 |
| V2 | 限同一 peak 数十分位 |
| V3 | 限不同研究 |
| V4 | 同时满足 V2 和 V3 |

- **置换检验：** 在 peak 数十分位内打乱标签，邻居图保持不变，重复 200 次（p 值最小为 0.005）。

### 得到什么结果

**t-SNE（图 1F-A）**
- CTCF/黏连蛋白类实验跨细胞类型聚成一个大岛。
- Hep G2、K-562、MCF-7 等各自形成以细胞类型为主的区域。

**全体实验（图 1F-B，κ 基于条件期望）**

| 变体 | 蛋白 | 细胞类型 | 蛋白类别 | 组织 |
|---|---|---|---|---|
| V0 | 0.43 | 0.46 | 0.54 | 0.62 |
| V1 | 0.43 | 0.46 | 0.54 | 0.62 |
| V2 | 0.33 | 0.35 | 0.44 | 0.52 |
| V3 | 0.30 | 0.28 | 0.37 | 0.45 |
| V4 | **0.25** | **0.23** | 0.33 | 0.39 |

所有变体的置换 p 值都是 0.005。

**细分背景（图 1F-C，κ 从 V0 到 V4）**

| 背景 | 统计的标签 | V0 | V4 | V4 的 p | 解读 |
|---|---|---|---|---|---|
| K-562 | 蛋白 | 0.26 | 0.086 | 0.005 | 减弱 |
| Hep G2 | 蛋白 | 0.09 | 0.013 | 0.01 | 只剩弱信号 |
| MCF-7 | 蛋白 | 0.50 | 0.29 | 0.005 | 保留 |
| CTCF | 细胞类型 | 0.19 | 0.024 | 0.005 | 只剩弱信号 |
| AR | 细胞类型 | 0.43 | 0.16 | 0.005 | 减弱 |
| ESR1 | 细胞类型 | 0.64 | 0.41 | 0.005 | 保留 |
| FOXA1 | 细胞类型 | 0.65 | 0.39 | 0.005 | 保留 |

**计算口径的更正**
- 期望改为按条件计算后，整体 κ 几乎不变，例如 V4 下蛋白 κ 为 0.251，原来的全局期望给出 0.261。
- 但 v1.1 报告中“Hep G2 内蛋白类别 κ = −0.30”是全局期望造成的假象，按条件期望重算为 −0.002。

### 结论

- 蛋白身份和细胞背景确实塑造了全基因组的结合模式。但如果不加控制，近邻统计会把大约一半的“结构”错误地归给生物学因素。
- 两种技术因素里，研究来源的影响大于测序深度：单独限制不同研究（V3），κ 就下降 0.13–0.18。
- 去掉 SVD 第 1 成分几乎没有影响。所以即使第 1 成分代表测序深度，它也没有决定近邻结构。
- Hep G2 和 CTCF 的强结论不成立。这只说明当前数据中检测不到稳定的结构，**不能**反过来推出“CTCF 跨细胞完全保守”。
- MCF-7、ESR1 和 FOXA1 的结构在严格控制后依然存在，可以作为后续背景特异性分析的候选。

对应证据：
- t-SNE 图：[`experiment_clustering_v1/tsne.png`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/experiment_clustering_v1/tsne.png)；SVD 成分与 peak 数的相关：[`svd_depth_correlation.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/experiment_clustering_v1/svd_depth_correlation.tsv)
- 全部变体和视角：[`validation_v1_2/experiment/experiment_confounder_sensitivity.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_2/experiment/experiment_confounder_sensitivity.tsv)
- 研究来源：[`validation_v1_1/study_provenance.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/validation_v1_1/study_provenance.tsv)

## 讨论

1. **对 PMA 的意义：** 做背景特异性分析时（例如设计文档中的 Application B），必须把研究来源当作混杂因素控制。否则，把实验批次的差异解释成细胞背景的差异，风险很大。
2. **近邻 κ 的局限：** 近邻 κ 只是描述性统计。限制邻居范围会改变可比较的实验集合，不能把 κ 的下降直接换算成方差的比例。
3. **组织标签覆盖不足：** 很多实验没有组织标签。例如 CTCF 视角下，V4 只有 39 个实验同时有组织标签和满足条件的邻居，所以组织相关的结果不作结论。
4. **下一步（待审阅）：** 在同一细胞背景内比较不同研究对同一蛋白的测定，把“背景特异性”和“研究特异性”进一步分开。

## 版本记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-10-21 | 汇总 v1（嵌入与标签归因）、v1.1（5 种邻居限制）和 v1.2（条件期望、置换检验、有效邻居数） |
