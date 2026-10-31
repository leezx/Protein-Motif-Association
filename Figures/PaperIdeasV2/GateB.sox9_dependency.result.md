# Gate B result — PMA-derived protein occupancy architecture improves prediction of SOX9-loss-associated chromatin responses in HT29 cells（GO，预测性）

> **文档性质：** 内部分析结果稿，非投稿版本。
> **版本：** v0.3，2026-10-31。v0.2 按 GPT 结果审核（`UDE/design/paper_ideas_v2_gateB_review1.md`，APPROVE / GO，预测性而非机制性）修改措辞并补充 QA；v0.3 加入 NC2 按染色体保持的修复审计（§7，GPT Gate V 终审要求），**GO confirmed**。
> **设计：** `UDE/design/paper_ideas_v2_plan_v0.2.md`（GPT 原文）+ `paper_ideas_v2_plan_v0.2_impl.md`，计算前冻结；预检两轮（review1 FAIL → `paper_ideas_v2_preflight_fix.md` → review2 PASS）。
> **代码：** 分支 `task_20261030_paper_ideas_v2`，`scripts/06_gates/62–66, 68`；正式运行用的 `64_gateB_model.R` md5 `5507a62f…`（Argos `code_real/`）。
> **结果目录：** `DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateB_sox9_dependency_v1/`（本地与 Argos；大文件只在 Argos）。
> **结果边界：** 只有一个扰动体系（HT29 dTAG-SOX9）。染色体交叉验证说明的是 HT29 内未见过的基因组位点上的增量预测力，不能说明跨细胞系泛化。Y1 阴性的意思是"未被判为显著丢失"，不是"未受影响"。

![Gate B](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateB_sox9_dependency_v1/figures/GateB_sox9_dependency.png)

图文件：[PNG](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateB_sox9_dependency_v1/figures/GateB_sox9_dependency.png) / [PDF](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateB_sox9_dependency_v1/figures/GateB_sox9_dependency.pdf)

## Result overview

**预注册判定：GO（6/6 条判据满足）。**

1. **主比较：** 在已有 ATAC、motif、RNA、SOX9/SMARCC1/H3K27ac/H3K4me3 CUT&RUN 以及 PMA 占据蛋白数和覆盖度（B2）之上，加入 PMA 的 20 维蛋白占据结构（B3，不含任何 HT-29 实验），D4 ATAC 丢失的 out-of-fold AP 从 0.631 升到 0.659，**ΔAP = +0.027（染色体 bootstrap 95% CI +0.012 到 +0.044）**，超过预注册最小值 0.020。
2. **增益来自蛋白特异的占据模式，而不只是占据数量：** 在 ATAC × 占据蛋白数 × promoter 层内置换区域的占据行（保持蛋白数与可及性，打乱是哪些蛋白），200 次全部低于观察值（置换 p = 0.005，第 95 百分位 −0.0006）。原 NC2 未限定染色体；按染色体保持重跑 200 次后第 95 百分位 +0.0012、最大 +0.0053，仍全部低于观察值（p = 0.005，§7）。保持每个蛋白广度的打乱参考（20 次）全部 ≤ −0.0003。SVD20 也可能编码未测量的染色质状态或细胞类型相关的占据特征，因此这里只说"蛋白特异的占据模式携带增量预测信息"，不说"蛋白身份决定 SOX9 依赖"。
3. **稳健：** 去掉相距 < 2 kb 的近邻区域 +0.029；5 种其他染色体分组 +0.023 到 +0.031；逐一剔除染色体后 +0.025 到 +0.032。单条染色体分别计算时方向并不一致：≥ 5 个阳性的 20 条染色体中 13 条为正（单染色体阳性少，AP 不稳定）。
4. **连续结局方向一致：** D4 log2FC 的 held-out R² 0.39 → 0.47，Spearman 0.59 → 0.65。
5. **只用肠道背景的 PMA 没有增益（+0.004，CI −0.006 到 +0.013）。** 完整参考优于肠道限定参考；但两者的数据规模、蛋白覆盖和实验数都不同，不能据此区分"参考广度"与"细胞背景多样性"的贡献。
6. **没有单个蛋白被选出：** 逐蛋白弹性网（探索性）在 lambda.1se 下所有蛋白系数为 0。增益分布在占据结构上，目前不能归到某个具体辅因子。

**结论（GPT 审定措辞）：** In HT29 cells, a PMA-derived protein occupancy representation improved prediction of chromatin accessibility loss following SOX9 degradation beyond baseline accessibility, sequence motifs, gene expression, experimentally measured SOX9 occupancy, chromatin-associated CUT&RUN signals, and overall protein occupancy density. The increase in out-of-fold average precision was 0.027 (95% chromosome-cluster bootstrap CI, 0.012–0.044), exceeding the preregistered minimum effect threshold. Conditional occupancy permutations abolished the incremental predictive gain, supporting the contribution of protein-specific occupancy patterns rather than occupancy density alone. Continuous accessibility changes showed concordant improvements in predictive performance. These results establish incremental predictive value for PMA-derived occupancy architecture within one HT29 perturbation system. They do not establish direct physical protein assemblies, identify causal cofactors, or demonstrate generalization across cellular contexts.

## 1. 区域与结局

### 为什么做

GPT v0.2 要求只有扰动前的信息能决定哪些区域进入分析。Context Query 的共识区域用了 12 个 ATAC 样本（含 D2–D13），不满足这一点。

### 做了什么

- **区域：** 只用 DMSO 两个重复的 ATAC peak（summit ±250 bp，合并，两重复都需支持）→ 90,983 个区域（Context Query 为 250,342）。所有计数、DESeq2、PMA 证据、SOX motif 都在新区域上重跑。
- **主 universe：** DMSO SOX9 CUT&RUN 两重复都有 peak、不与黑名单重叠，且 D4 padj 不为 NA。
- **Y1：** DESeq2 `~time`，median-of-ratios，`results(alpha = 0.05)`，D4 vs DMSO padj < 0.05 且 log2FC < 0。
- **NA 处理：** 5,290 个 SOX9 结合区域中 866 个 padj 为 NA（独立过滤 863、全零 3、Cook's 0），主分析排除；NA 记 0 作为敏感性分析。

### 得到什么结果

| 项 | 数 |
|---|---|
| 主 universe | 4,424 |
| D4 丢失（Y1 = 1） | 721（16.3%） |
| 其中 distal / promoter / proximal | 647 / 25 / 49 |
| 全 baseline universe 中 D4 丢失 | 1,304 |

## 2. 嵌套模型（图 B-A、B-B）

### 做了什么

全部模型臂用同一算法：ridge（glmnet α = 0），λ 由训练染色体内分组 CV 选 lambda.min。外层 23 条染色体分 5 折（按区域数和阳性数平衡，建模前写出）。

| 臂 | 加入的特征 |
|---|---|
| B0 | DMSO ATAC、外部 ATAC 先验（剔除 HT-29）、GC、CpG、TSS 距离与类别、cCRE 类别、6 个 SOX PWM、最近基因 DMSO 表达 |
| B1 | + DMSO SOX9 CUT&RUN 信号、SOX9 peak 强度、IgG |
| B2 | + DMSO SMARCC1、H3K27ac、H3K4me3、PMA 占据蛋白数、PMA 实验覆盖度 |
| B3 | + PMA SVD 20 维（1,042 个非 HT-29 蛋白/抗原，TF-IDF，每折只在训练染色体的 baseline 区域上拟合） |
| GUT | B2 + 只用消化道非 HT-29 实验的 SVD 20 维（224 个） |

### 得到什么结果

| 比较 | ΔAP | 95% CI |
|---|---|---|
| B1 − B0（SOX9 CUT&RUN） | +0.067 | +0.047 到 +0.083 |
| B2 − B1（染色质 + PMA 数量） | +0.045 | +0.027 到 +0.065 |
| **B3 − B2（PMA 蛋白身份，主）** | **+0.027** | **+0.012 到 +0.044** |
| B3 − B1 | +0.072 | +0.047 到 +0.101 |
| GUT − B2 | +0.004 | −0.006 到 +0.013 |

AUROC：B2 0.881，B3 0.893。

## 3. 阴性对照与稳健性（图 B-C、B-D）

| 对照 | 结果 |
|---|---|
| NC2 占据行置换（200 次，每次每折重新嵌入并重拟合） | 均值 −0.006，第 95 百分位 −0.0006，最大 +0.003；观察值 +0.027，p = 0.005 |
| NC3 保持蛋白广度的打乱参考（20 次） | 均值 −0.008，最大 −0.0003 |
| NC4 去近邻（< 2 kb） | +0.029（n = 4,356） |
| NC4 5 种染色体分组 | +0.023 到 +0.031 |
| 逐一剔除染色体 | +0.025 到 +0.032 |
| Embedding 隔离审计 | 1,155 次拟合，测试染色体行进入拟合 0 次 |

**解读：** 打乱"哪些蛋白"、保留"多少蛋白"和可及性后，增益完全消失，甚至略为负（多出 20 个无信息维度的代价）。这说明增益来自蛋白身份的组合，而不是 HOT 程度或覆盖度。

## 4. 次要分析（图 B-E、B-F）

- **亚组：** 所有预设亚组 ΔAP 都为正。SOX motif 低/中三分位（+0.040 / +0.046）大于高三分位（+0.021），提示 motif 弱的位点上 PMA 补充的信息可能更多；但三组阳性率与基线 AP 不同，绝对 ΔAP 不能直接比较，只作支持性观察。Promoter +0.083 只有 25 个阳性，不作解读。
- **Y2 的增益没有独立的不确定性区间**，只作支持性证据。
- **Y2：** R² 0.39 → 0.47，Spearman 0.59 → 0.65，MAE 0.68 → 0.63。
- **全 baseline universe（不限 SOX9 结合，90,734 个，阳性 1,304）：** ΔAP +0.038。这里 padj 为 NA 的区域（独立过滤 44,091 个）记为阴性，是 NA → 0 的敏感性分析，AP 不能与主分析直接比较（QA-1）。
- **NA → 0（5,290 个）：** ΔAP +0.029。

## 5. 局限

1. 只有一个细胞系和一个扰动；不能声称跨背景泛化。
2. PMA 参考按 ChIP-Atlas "TFs and others" 类定义，1,042 列中有 20 列不是单一蛋白（Epitope_tags、Biotin、Cas9、G-quadruplex、5-mC、RNA Pol II/III 等）。只保留 HGNC 蛋白的事后敏感性分析（§6）结果不变。
3. 没有单个蛋白被选出，所以这一结果不能直接转化为"某个辅因子决定 SOX9 依赖"。
4. Y1 依赖 DESeq2 独立过滤；低计数区域不在主分析内。
5. 外部 ATAC 先验和 PMA 都剔除了 HT-29，但其他肠道细胞系仍在参考中（GUT 臂无增益，说明不是近亲细胞系驱动）。

## 6. 事后敏感性：只保留 HGNC 蛋白

此分析在主结果之后添加（`code_posthoc/`，环境变量 `HGNC_ONLY=1`，50 次置换），不改变判定。去掉 20 个非单一蛋白列（1,022 列保留），其余流程不变。

| 项 | 主分析（1,042 列） | 只保留 HGNC 蛋白（1,022 列） |
|---|---|---|
| ΔAP(B3 − B2) | +0.027（+0.012 到 +0.044） | +0.027（+0.012 到 +0.043） |
| NC2 置换 p | 0.005（200 次） | 0.020（50 次；可达最小值 1/51） |
| NC3 最大值 | −0.0003 | −0.003 |
| NC4 范围 | +0.023 到 +0.031 | +0.023 到 +0.031 |
| 隔离审计 | 1,155 次，0 违规 | 405 次，0 违规 |

结论：增益不依赖非蛋白抗原列。

## 7. 审核与下一步

- GPT 结果审核：APPROVE / GO（6/6），认定为预测性 GO，不是机制性 GO。审核基于提交的结果，没有独立复跑代码（分支未 push）。
- Y3（基因层面 RNA 响应）：批准立项设计，正式运行前需提交冻结合同。
- Gate C、Virtual ChIP-seq 继续 HOLD。

## 7. 修复审计：NC2 按染色体保持（2026-10-31）

### 为什么做

Gate V 预检复审 2 指出：NC2 分层不含染色体时，测试染色体区域的占据行可被换到训练染色体，进入该 fold 的 SVD 拟合。这不泄漏 Y1 标签，但置换零分布的特征隔离与主分析不一致。Gate B 的 `64_gateB_model.R` 有同样写法；GPT Gate V 终审（`UDE/design/paper_ideas_v2_gateV_final_review.md` §3）要求只重跑 NC2，并预先规定：观察值仍超过新 NC2 第 95 百分位 → GO confirmed；否则降为 CONDITIONAL；审计不完整 → NOT EVALUABLE。

### 做了什么

`scripts/06_gates/81_gateB_nc2_chrom.R`（md5 `568fa750…`，Argos `code_real/`）：与 64 相同的特征、universe、臂、fold、嵌入和 ridge；读取冻结的 OOF 预测与 fold 划分并断言一致；分层改为染色体 × ATAC 三分位 × 蛋白数五分位 × promoter，200 次，每次重新按 fold 嵌入并重拟合 B3；每次置换独立审计文件。原模型输出与原 NC2 不改动（`64` md5 `5507a62f…`）。结果在 `model/nc2_chrom_correction/`。

### 得到什么结果

| 项 | 原 NC2 | 按染色体 NC2 |
|---|---|---|
| 第 95 百分位 | −0.0006 | +0.0012 |
| 最大值 | +0.0026 | +0.0053 |
| 观察 ΔAP（冻结） | +0.0275 | +0.0275 |
| 置换 p | 0.005 | 0.005 |

QA：489 个 strata（单元素 94，中位大小 6）；每次置换实际改变来源的区域中位 88.9%（最小 87.9%）；跨染色体交换 0；1,000 次嵌入拟合，隔离违规 0。

### 结论

**Gate B GO confirmed。** 按染色体保持后零分布略上移，但观察值仍比 200 次置换的最大值高约 5 倍。主估计、CI、Y1 与判定阈值都未改动。

