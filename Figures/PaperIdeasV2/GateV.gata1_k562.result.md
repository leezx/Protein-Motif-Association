# Gate V result — PMA occupancy architecture improves prediction of GATA1-CRISPRi accessibility loss in K562（GO，独立体系复现 Gate B）

> **文档性质：** 内部分析结果稿，非投稿版本。
> **版本：** v0.2，2026-10-31。v0.2 按 GPT 终审（`UDE/design/paper_ideas_v2_gateV_final_review.md`，APPROVE / GO）修改措辞。
> **设计：** `UDE/design/paper_ideas_v2_gateV_contract_v0.1.md` + 预检修订 v0.2（`paper_ideas_v2_gateV_preflight_review1.md`）+ `paper_ideas_v2_gateV_model_contract_v0.2.md`；预检三轮（review1 FAIL → `paper_ideas_v2_gateV_preflight_fix.md` → review2 结局 PASS、代码两项修复 → review3 PREFLIGHT PASS）。计算前冻结。
> **数据：** GSE168851 Spear-ATAC K562 LargeScreen peak matrix（用户批准下载，MD5 记录在 `raw/2026-10-30_gse168851/`）。
> **代码：** 分支 `task_20261030_paper_ideas_v2`，`scripts/06_gates/74–80`；正式运行用的 `79_gateV_model.R` md5 `bf1f39d5…`（Argos `code_real/`）。
> **结果目录：** `DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateV_gata1_k562_v1/`（本地：model、outcome_v2、figures、code；大矩阵只在 Argos）。
> **结果边界：** 模型在 K562 标签上重新训练，不是 HT29 模型的零样本迁移。说明的是"同一框架在第二个 TF / 细胞系 / 扰动方式中复现增量预测力"。GATA1 结合来自外部 ChIP，不是同实验测量；peak 由 ArchR 在全部（多靶点 CRISPRi 池）细胞上调用。

![Gate V](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateV_gata1_k562_v1/figures/GateV_gata1_k562.png)

图文件：[PNG](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateV_gata1_k562_v1/figures/GateV_gata1_k562.png) / [PDF](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateV_gata1_k562_v1/figures/GateV_gata1_k562.pdf)

## Result overview

**预注册判定：GO（5/5 条判据满足）。**

1. **主比较：** 在 NT ATAC、外部 ATAC 先验、序列与 GATA motif、GATA1 ChIP 支持、K562 H3K27ac / H3K4me3 支持以及 PMA 占据蛋白数和覆盖度（B2）之上，加入 PMA 20 维占据结构（B3，剔除全部 2,402 个 K-562 实验），GATA1 CRISPRi 后 ATAC 丢失的 out-of-fold AP 从 0.622 升到 0.652，**ΔAP = +0.0295（染色体 bootstrap 95% CI +0.0245 到 +0.0350）**；AUROC 0.850 → 0.860。数值上与 Gate B（+0.027）接近，但两者 universe、阳性比例与基线特征不同，不能作为同质效应合并。
2. **增益来自蛋白特异的占据模式：** 按染色体 × NT ATAC 三分位 × 蛋白数五分位 × promoter 置换占据行（每次约 96% 的区域换了来源，跨染色体交换 0），200 次的 ΔAP 范围 −0.0010 到 +0.0037，第 95 百分位 +0.0024，全部低于观察值（置换 p = 0.005，即 200 次下的最小值）。
3. **三个不同的 GATA1 sgRNA 方向一致：** 用合并模型的 OOF 预测、各 guide 自己可检验的区域评价，ΔAP 分别为 +0.031（CI +0.017 到 +0.044）、+0.026（+0.008 到 +0.042）、+0.028（+0.014 到 +0.044）。guide 标签与合并标签共享 NT 细胞和数据，不是独立实验复制。
4. **稳健：** 逐一剔除染色体后 +0.028 到 +0.031；单条染色体分别计算时 23 条中 22 条为正（chr20 −0.005）。只保留 ≥ 2 个 ChIP-Atlas K-562 ATAC 实验覆盖的 peak（17,106 个，独立于本筛选）后 ΔAP +0.0295，结果对外部可及性证据筛选稳健（这些区域仍来自 pooled-called peak，不能证明完全不受 pooled peak calling 影响）。
5. **连续结局方向一致：** 合并 log2FC 的 held-out R² 0.26 → 0.31，Spearman 0.53 → 0.58。
6. **亚组（次要）：** promoter +0.038、proximal +0.022、distal +0.030；GATA motif 低 / 中 / 高 +0.036 / +0.032 / +0.025，增益不局限于 motif 强的区域。

**结论（GPT 审定措辞）：** In K562 cells, a PMA-derived protein occupancy representation constructed without K562 experiments improved the prediction of GATA1-CRISPRi-associated chromatin accessibility loss beyond baseline accessibility, DNA sequence motifs, external GATA1 occupancy, K562 histone-mark evidence, and overall protein occupancy density. The improvement in out-of-fold average precision was 0.0295 (95% chromosome-cluster bootstrap CI, 0.0245–0.0350), exceeding the preregistered minimum effect threshold and a chromosome-preserving conditional occupancy permutation null. Positive predictive gains were observed when the pooled model was evaluated against the outcomes of each of three distinct GATA1-targeting sgRNAs, although these evaluations shared underlying data and controls. The gain was also robust to chromosome exclusion and restriction to peaks supported by an independent K562 accessibility reference. Together with the HT29 SOX9 degradation results, these findings support the reproducibility of incremental predictive information from PMA-derived occupancy patterns across two transcription factors, cellular contexts, and perturbation modalities, using context-specific model retraining. These results do not establish zero-shot transfer, direct physical protein assemblies, causal cofactors, or gene-level transcriptional response prediction.

**GPT 终审：** APPROVE / GO（5/5）。核验基于执行端记录（代码 md5、1,010 次隔离审计、200 次置换完整性），未独立重跑。SVD20 也可能编码 B2 未完全控制的染色质状态、蛋白组合偏好或实验来源结构，因此只说"占据模式携带增量预测信息"。

## 1. 结局与 universe

### 为什么做

需要第二个 TF / 细胞系 / 扰动方式检验 Gate B 是否只是 HT29 SOX9 的特例。GPT 收尾审核只授权这一个外部验证（HD-16）。

### 做了什么

- **细胞：** 作者高置信分配 `sgAssignFinal`；按原论文剔除 5 个异常 NT guide（sgNT-5/6/8/11/12），保留 NT 1,187 个细胞（9 个 guide），GATA1 230 个细胞（3 个 guide）。
- **伪 bulk：** (组, 10x lane) 求和；DESeq2 `~lane + group`，median-of-ratios，`alpha = 0.05`；Y1 = padj < 0.05 且 log2FC < 0。
- **Universe：** NT 伪 bulk CPM ≥ 1（只由 NT 细胞决定）→ 168,995 个 peak（"NT-accessible subset of pooled-called ArchR peaks"）；∩ ≥ 2 个未扰动 K562 GATA1 ChIP-Atlas 实验（共 23 个）→ 23,866；可检验 17,690；去黑名单 17,689；阳性 4,236（23.9%）。

### 得到什么结果（结局可靠性，`outcome_v2/`）

| 检查 | 结果 |
|---|---|
| 逐 lane 效应（log2 CPM 差中位） | 结合区域 −0.29 到 −0.59，6 个 lane 全部为负；非结合区域 −0.01 到 +0.39 |
| NT-vs-NT 零对照（奇 vs 偶 guide，565 vs 622 个细胞） | 显著丢失 0、增加 0；结合区域 median log2FC −0.03 |
| NT 下采样到 GATA1 细胞数 | 完整分析中丢失的区域 99.98% 仍为负；log2FC r = 0.88 |
| guide 一致性（全部 17,690 个结合可检验区域） | 82–83% 为负；与合并 r = 0.81–0.82，与去该 guide 的合并 r = 0.62 |

合并 DESeq2 中非结合区域 median log2FC 约 −0.39 而逐 lane CPM 差约 0 到 +0.1；这一偏移可能来自归一化或组成效应，确切来源未经独立确认。

## 2. 特征与模型

| 臂 | 特征 | OOF AP |
|---|---|---|
| B0 | NT log2 CPM、非 K-562 ATAC 先验、GC、CpG、TSS 距离与类别、cCRE、GATA1/GATA2 motif hits/margin | 0.572 |
| B1 | + GATA1 ChIP 支持比例（n/23） | 0.575 |
| B2 | + K562 H3K27ac（128 个实验）、H3K4me3（107）支持比例 + PMA 蛋白数、覆盖度 | 0.622 |
| B3 | B2 + PMA SVD20（1,045 个蛋白，k_p 规则同 Gate B） | 0.652 |

ridge logistic，λ.min 由训练染色体分组内层 CV；外层 5 折染色体 CV（建模前冻结 `fold_assignments.tsv`）；嵌入按 fold 只在训练染色体的 NT universe peak 上拟合。隔离审计 1,010 次拟合，违规 0。

B1 − B0 只有 +0.004：主 universe 本身已限定为 GATA1 结合区域，ChIP 支持比例在其中区分度有限。B2 − B1 = +0.047 主要来自组蛋白与占据密度。

## 3. 判定

| 判据 | 要求 | 结果 |
|---|---|---|
| c1 | ΔAP ≥ 0.020 | +0.0295 ✓ |
| c2 | CI 下限 > 0 | +0.0245 ✓ |
| c3 | > NC2 第 95 百分位 | p95 +0.0024 ✓ |
| c4 | LOCO 全部 > 0 | 最小 +0.028 ✓ |
| c5 | ≥ 2 个 guide ΔAP > 0 | 3/3 ✓ |

**GO。**

## 4. 局限

1. 伪 bulk 来自单细胞（230 vs 1,187 个细胞），6 个 lane 是 10x 技术分组，未确认是独立培养；NT 细胞中位 fragments 高于 GATA1（12,579 vs 7,905）。
2. peak 由 ArchR 在多靶点 CRISPRi 池全部细胞上调用；用独立 K562 ATAC 参考的敏感性分析结果不变，但不能完全排除选择偏差。
3. GATA1 结合来自外部 ChIP-Atlas，不是本实验测量；没有基线 RNA 与辅因子 CUT&RUN，B2 比 Gate B 弱。
4. guide 层面的评价与合并标签共享数据和 NT 对照。
5. 染色体 bootstrap CI 不包含模型拟合的随机性（打乱标签 SMOKE 中 ΔAP +0.005 的 CI 也不含 0），因此 GO 依赖 NC2 与 0.02 阈值的联合判据。
6. **Gate B 的 NC2 需复核：** Gate V 复审 2 指出 NC2 分层未包含染色体会让测试染色体的占据行进入训练嵌入。Gate B 的 `64_gateB_model.R` 有同样写法（只影响零分布，不影响标签或主估计）。GPT 终审要求只按染色体保持方式重跑 Gate B NC2（200 次，不重拟合主模型），结果见 Gate B 结果稿 v0.3。

## 5. 下一步（按合同）

- Gate V 关闭，不再优化；不追加其他 TF、细胞系或模型。
- 唯一后续计算：Gate B NC2 按染色体保持方式的定向修复审计；完成后 Paper-ideas v2.0 标记 COMPLETE。
