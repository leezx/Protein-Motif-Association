# Context Query v0.1 — HT29 SOX9–BAF × PMA (Result v0.2，含审核回合 1)

- 日期：2026-10-30
- 分支：`task_20261030_context_atlas_sox9baf`（基于 `task_20261030_hotspot_followup`）
- 设计来源：`UDE/design/history/Context-conditioned Regulatory Evidence Atlas-v1.0.md`（GPT，§八 "PMA Context Query v0.1 — SOX9–BAF"）
- 代码：`scripts/04a_chipatlas/45–52`（45 counts，46 PMA evidence，47 DESeq2，48 tests，49 figure；审核回合 1：50 SOX motifs，51 checks，52 figure；SGE 提交脚本 `45_47_context_query_jobs.sh`）
- 结果：`DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/context_query_ht29_sox9baf_v1/`（Argos 同路径，`counts/` 和 `pma/` 的大文件只在 Argos）
- 图：`…/context_query_ht29_sox9baf_v1/figures/ContextQuery_SOX9BAF.{pdf,png}`（A–J）；审核补充图 `ContextQuery_SOX9BAF_review1.{pdf,png}`（A–D）
- 审核：GPT 回合 1（2026-10-30）为 REQUEST_CHANGES，要求核对 dTAG 时间设计和 SMARCC1 重复一致性，并补一项 SOX 家族 ChIP vs motif 比较；批准 push，暂不合并。处理结果见 §8。
- 状态：探索性 application，**不是 L3 验收**；没有改 G1（HOLD，HD-11）和 FG-1 进度。

## 0. 问题与回答（一句话）

**问题（设计文档 §七）：** SOX9 依赖的染色质可及性变化，是否优先发生在有 BAF 相关调控证据的位点上？

**回答：不是，方向相反。** 在 SOX9 结合位点中，HT29 自己测到的 SMARCC1（BAF）占据与 D4 ATAC 丢失**负相关**（校正 OR 0.39，95% CI 0.32–0.47）。PMA 的跨 context BAF 证据在校正开放度、P 等协变量后没有关联（OR 1.26，CI 0.87–1.83）。真正能从 PMA 证据中挑出 SOX9 依赖位点的是 **SOX 家族本身的跨 context 占据**（SOX10、SOX8、SOX9、SOX13、SOX5，校正 OR 2.7–9.8，FDR < 1e-19），排在全部 810 个 PMA 靶点的前 12 名以内。审核回合 1 后：SOX 家族 ChIP 证据在控制 6 个 SOX PWM、初始 ATAC 和初始 SOX9 占据后仍有独立贡献（OR 2.22，CI 1.78–2.77），但交叉验证 AUROC 只提高约 0.005–0.015（§8.2）。v0.1 中"SOX9 位点 SMARCC1 相对下降更多"这一机制线索**没有通过 IgG 背景对照，已撤回**（§8.1）。

## 1. 数据清点（设计文档要求先确认）

HT29 dTAG-SOX9 时间序列，全部来自同一测序批次（Novogene 22CYWGLT3 L5）。

| 测定 | 时间点 | 重复 | 备注 |
|---|---|---|---|
| ATAC-seq | DMSO(D13), D2, D4, D7, D10, D13 | 2 | 每样本约 4.5–6.3 M 片段，FRiP 0.38–0.44 |
| CUT&RUN SOX9（HA） | 同上 | 2 | 每样本 0.17–0.50 M 片段；DMSO 约 13k 峰，D4 约 300 峰 |
| CUT&RUN SMARCC1 | 同上 | 2 | 每样本 0.19–0.53 M 片段；DMSO 26–39k 峰 |
| CUT&RUN IgG | DMSO×2, D4×2, D13×1 | — | |
| CUT&RUN H3K27ac / H3K4me3 | 同上 | 2 | 本轮未用（H3K27ac 峰数只有 95–4,491，质量不足） |
| RNA-seq | `rna_pipeline/` | — | 本轮未用 |

**时间设计（用户确认，2026-10-30）：D2、D4 为 SOX9 降解期，D7、D10、D13 为 SOX9 恢复期。** 这与 SOX9 CUT&RUN 信号一致（library-size 归一化，SOX9 位点中位 log2FC：D2 −1.12，D4 −2.14，D7 −1.50，D10 −0.37，D13 0.00）。项目的 sample sheet 和 notebook 里没有书面记录，以用户确认为准。SOX9 染色质占据在 D7 仍明显偏低，D10–D13 才回到基线；可及性在 D7 已基本恢复（§3.1）。所以"恢复期"指撤除降解条件后的阶段，不表示各层面同步恢复。

**Spike-in 不可用：** E. coli carry-over 在**所有** D4 CUT&RUN 文库中都约低 10 倍，IgG 也一样（例：DMSO_IgG_1 18,671 对 vs D4_IgG_1 982 对），属于文库批次效应。按 spike-in 归一化会把 SOX9 在 D4 变成"上升 +1.41"，与峰数（13k → 300）矛盾。因此 CUT&RUN 主分析用总片段数（library size）归一化，spike-in 和 median-of-ratios 只作为敏感性分析写进 `T0_depletion.tsv`。

**PMA 证据完全外部：** ChIP-Atlas 没有任何 HT-29 的 BAF 亚基实验。肠道来源的 BAF 实验只有 HCT 116（36 个）和 DLD-1（4 个）。HT-29 的公共 SOX9 ChIP（3 个）在 SOX9 证据中单独计数并排除（`pma_sox9_exp_ext`）。

## 2. 方法

- **区域全集：** 12 个 ATAC 样本各自的峰取 summit ±250 bp，合并后保留 ≥ 2 个样本支持的区域，共 250,342 个（中位宽 693 bp），去掉 blacklist 后 249,725 个。DMSO 的 SOX9 峰有 78–84%、SMARCC1 峰有 86–87% 落在这个全集里。所以本分析只覆盖 HT29 的开放染色质。
- **计数：** 每个片段计一次（proper pair，MAPQ ≥ 10，按片段中点归属）。
- **差异分析：**
  - ATAC：DESeq2 `~time`，各天 vs DMSO。
  - CUT&RUN：只在该抗体 DMSO 有峰的区域上分析，size factor = 总片段数。
- **HT29 观测（Observed）：** DMSO 两个重复都有峰。
- **PMA 证据：** 区域内有峰的实验集合（与 29 号脚本规则一致）。`pma_baf` 定义为 ≥ 1 个 BAF 亚基有 ≥ 2 个实验；BAF 亚基共 23 个，列表见 48 号脚本。
- **证据分级（设计文档 §六 要求区分 Observed / Supported / Inferred / Unknown）：**
  - BAF：Observed = HT29 SMARCC1；Supported = PMA BAF ≥ 2 个实验且 ≥ 2 种细胞类型；Inferred = PMA BAF ≥ 1 个实验；Unknown = 无证据。
- **SOX9 依赖：** D4 vs DMSO 的 padj < 0.05 且 log2FC < 0。恢复度 = 1 − LFC_D13 / LFC_D4，≥ 0.5 记为恢复。
- **协变量：**
  - DMSO ATAC log2 CPM（4 df spline）；
  - GC（3 df spline）；
  - TSS 类别；
  - cCRE 类别；
  - log1p(P_max)；
  - SOX9 motif（HOCOMOCO v14 SOX9.H14CORE.0.PS.A，P < 1e-4，24.2% 的区域有命中）。

## 3. 结果

### 3.1 SOX9 降解后有一组局部、可逆的可及性丢失（Fig. A, G）

- **丢失的规模：** D4 时全基因组 1,954 个区域 ATAC 下降（padj < 0.05），D2 时 1,469 个；D7 降到 10 个，D10 和 D13 为 0。
- **丢失集中在 SOX9 位点：** SOX9 结合区域只占全集的 2.4%，却贡献了 D4 丢失区域的约一半，可检验的 SOX9 位点中有 1,008 / 5,422 个（18.6%）丢失。非 SOX9 区域只有 0.6% 丢失。
- **SOX9 位点的 ATAC 中位 log2FC：** D2 −0.32，D4 −0.37，D7 −0.13，D10 −0.09，D13 −0.11。
- **几乎全部恢复：** D4 丢失的 SOX9 位点有 990 / 1,008（98.2%）在 D13 恢复度 ≥ 0.5（中位恢复度约 0.85）。所以"恢复动力学"（T3）在这批数据里没有可解释的变异（各 OR 的 CI 跨越 0.1–11）。

### 3.2 PMA 跨 context 证据对 HT29 占据有校准价值，但主要来自"开放 / 热点"成分（Fig. B–D）

- **SMARCC1：** PMA BAF 实验数预测 HT29 SMARCC1 占据的 AUROC 为 0.85。但这几乎与 P_max（0.84）、ChIP-Atlas ATAC 开放度（0.84）相当，HT29 自身 ATAC 强度更高（0.89）。
- **SMARCC1，校正后：** 校正开放度、P 等之后，PMA BAF 仍有独立增益（OR 1.95，CI 1.79–2.12）。非肠道和肠道来源的 BAF 证据增益相近（1.88 vs 1.80）。阴性对照 CTCF 为 0.99。
- **SMARCC1，同一 ATAC 强度内：** 命中率随 PMA BAF 实验数单调上升（Fig. C）。例如 ATAC 最高五分位中，0 个实验时为 8.0%，> 10 个实验时为 32.5%。
- **SOX9：** PMA SOX9（不含 HT-29）的 AUROC 只有 0.64，与 motif（0.63）相当，校正 OR 为 4.16（CI 3.85–4.49）。
- **小结：** 跨 context 证据可以迁移，但区分度的大头来自"这个位点在哪里都开放、都热"，而不是蛋白特异性信息。这与 hotspot 工作的结论一致：热度主要由开放度解释，R² 0.71。

### 3.3 主假设不成立：BAF 证据不能挑出 SOX9 依赖位点（Fig. E, F, J）

在 SOX9 结合位点中（n = 5,422，其中 1,008 个 D4 丢失）：

| 预测因子 | 校正 OR (95% CI) | P |
|---|---|---|
| PMA BAF（未校正） | 0.43 (0.32–0.57) | 3e-9 |
| PMA BAF（校正） | 1.26 (0.87–1.83) | 0.23 |
| HT29 SMARCC1（校正） | **0.39 (0.32–0.47)** | 3e-23 |
| PMA BAF ∣ HT29 SMARCC1 | 1.36 (0.93–1.98) | 0.11 |
| PMA EP300（对照） | 1.41 (1.06–1.88) | 0.02 |
| PMA CTCF（对照） | 0.89 (0.73–1.08) | 0.24 |
| SOX9 motif | **2.11 (1.80–2.48)** | 3e-20 |

- **SOX9 位点上 BAF 证据普遍存在：** 约 95% 的 SOX9 位点（可检验集 5,198 / 5,422）有 Observed 或 Supported 级别的 BAF 证据（Fig. J）。所以在机制分类里，"SOX9-dependent / BAF-associated"占丢失位点的 93%，但这只是基线比例，不是富集。
- **丢失率按 BAF 证据单调下降（Fig. F）：** Observed 16%，Supported 23%，Inferred 31%，Unknown 31%。
- **在同一 ATAC 强度内仍然成立：** 按 DMSO ATAC 四分位，Q2–Q4 中 SMARCC1+ 为 10–22%，SMARCC1− 为 27–40%；Q1 两组都约 2%。
- **SMARCC1 的负关联不限于 SOX9 位点：**
  - 在非 SOX9 位点同样存在（OR 0.47）；
  - 但在 SOX9 位点更强（交互项 β = −0.83，P = 9e-13）；
  - PMA BAF × SOX9 的交互项为 −0.48（P = 0.018）。
- **解读：** 被 BAF 稳定占据的 SOX9 位点更"抗"SOX9 缺失，而依赖 SOX9 才能开放的位点 BAF 基线占据反而较弱。这是关联，不是因果；另一种解释是这些位点由多个因子冗余维持（见 3.5 中 AP-1 和启动子因子的负向 OR）。

### 3.4 ~~机制线索：SOX9 缺失时，SOX9 位点上的 SMARCC1 也一起下降~~（Fig. A, H）— 审核回合 1 已撤回，见 §8.1

> 撤回原因：同一比较在 IgG 背景中也出现，而且幅度相同或更大（D4 −0.20 至 −0.29 vs SMARCC1 −0.03 至 −0.25）。所以它不是 BAF 特异的信号。下面保留 v0.1 原文作记录；Fig. A 中 SMARCC1 的曲线和 Fig. H 都只能当作描述，不能作为证据。

- **SOX9 位点降得更多：** SMARCC1 CUT&RUN（library-size 归一化）的中位 log2FC 在 SOX9+SMARCC1 位点上为 D4 −0.69、D7 −0.74，在仅 SMARCC1 的位点上为 −0.21、−0.43。两组的 Wilcoxon 检验：D4 P = 2e-18，D7 P = 6e-5。两组都在 D10–D13 回到 0 左右。
- **ATAC 丢失的位点降得最多：** 在 SOX9+SMARCC1 位点中，ATAC 丢失位点的 SMARCC1 降幅更大（中位 −1.16 vs −0.62，P = 1e-8）。不过逐位点相关很弱（Spearman ρ = 0.05），因为 CUT&RUN 文库很小，每位点计数少。
- **为什么这个比较可信：** 它是同一批文库内两组位点的相对比较，不依赖全局归一化。但绝对值（例如"SMARCC1 全局是否下降"）因为 spike-in 失效而无法确定。
- **合理的机制假说：** SOX9 参与维持（或招募）BAF 在其靶位点的占据。BAF 的这种"动态依赖"，而不是"静态占据"，才是与可及性丢失相关的量。这一点只有 context 内的扰动数据能给出，跨 context 的 PMA 证据给不出。

### 3.5 候选共调控因子排序：PMA 的 SOX 家族证据是最强信号（Fig. I）

- **排序规则：** 对在 ≥ 100 个 SOX9 位点有 ≥ 2 个实验支持的 810 个 PMA 靶点，逐个做协变量校正后的 OR。164 个显著为正、346 个显著为负（FDR < 0.05）。
- **正向前列：** SOX8（9.8）、SOX10（5.3）、SOX9（4.3；含 3 个 HT-29 公共 SOX9 实验）、MED13、ISL2、ZNF503、TBX2、SOX13（2.8）、SOX5（2.7），以及 MITF、TFAP2A、OLIG2 等神经嵴 / 黑色素细胞 TF。SOX10 和 SOX8 的证据来自黑色素瘤和神经细胞，与 HT29 没有谱系关系，但它们识别同一类 SOX motif 位点。
- **负向前列：** HCFC1、ILF3、SP2、SP3、KLF9、BRCA1、BRD3、SETD1A、MEN1 等启动子 / CpG 因子，以及 FOS、JUN、JUNB 等 AP-1。它们标记的是 SOX9 不依赖的位点。
- **BAF 亚基：** 15 个进入排序，只有 SS18 > 1（1.61）。其余 OR 在 0.40–1.10 之间，其中 SMARCA2、SMARCE1、SMARCB1、ARID1A/B 显著 < 1。
- **意义：** 这正是设计文档 §六B 要的"候选共调控因子排序"。它能从 PMA 中恢复出与扰动对象同家族、同识别特异性的因子，这是一个阳性对照。但它没有支持 BAF。

## 4. 对 Context Query 设计的含义（给 GPT / 设计层）

1. **Layer 2 的"历史占据 + 开放度 + motif"组合可以排序 context 内的占据**（3.2）。但对 BAF 这类广泛存在的辅因子，它主要编码"开放 / 热点"，蛋白特异增益只有约 2 倍 OR。
2. **静态占据（不论来自历史还是本 context）不能预测扰动依赖**（3.3）。设计文档里"BAF-associated loci 更易 SOX9 依赖"这个可检验预测在 HT29 被**否定**。按 §八 的终止标准，**不应继续叠加 BAF 证据来支持这个假说**。
3. **有用的是同识别特异性的跨 context 占据（SOX 家族）**（3.5，§8.2）。SOX9 以外的 SOX 家族 ChIP 证据（全部来自 HT-29 以外）在控制 6 个 SOX PWM、初始 ATAC 和初始 SOX9 占据后仍有独立贡献（OR 2.22），与 motif 几乎不相关（ρ 0.08）。但交叉验证判别力的增益很小（AUROC +0.005–0.015），而且只在 motif 强的位点为正。现阶段它是**候选发现**，不是已验证的通用规律。
4. **context 内的 BAF 动态信号无法从现有 CUT&RUN 中分离**（§8.1）。PMA 适合用来提出和排序假说；机制验证需要 context-matched 扰动数据，以及背景可控的占据测量。

## 5. 局限

- 时间设计由用户确认（D2、D4 降解；D7、D10、D13 恢复），没有书面 metadata（§1）。
- CUT&RUN 的 spike-in 失效，绝对占据变化无法确定，只做位点组间比较。CUT&RUN 文库小（0.2–0.5 M 片段），单位点估计噪声大，DESeq2 在 CUT&RUN 上几乎没有单位点显著结果。
- "SOX9 结合"用的是 DMSO HA-SOX9 CUT&RUN 两个重复都有峰，约 6k 个区域。依赖性判定只基于 D4 vs DMSO 一个比较，DMSO 只有 D13 一个时间点的对照。
- 区域全集限于 HT29 开放染色质，不评估 SOX9 让关闭区域打开的情形；D4 时 SOX9 位点有 121 个上升。
- PMA BAF 证据很宽：54% 的 HT29 开放区域有 `pma_baf`，因为 SMARCA4 有 348 个实验。二元定义的区分度有限；分级结果见 Fig. C、F。
- 排序（T5）中的 SOX9 一行包含 HT-29 公共 ChIP，不完全外部；§8.2 的 SOX 家族检验已排除 SOX9 本身。
- 各区域并不是独立的生物学重复：位点级 P 值（例如 v0.1 的 Wilcoxon P = 2e-18）反映的是区域数带来的统计功效，可靠性要看两个重复是否一致（§8.1）。
- 没有用 RNA-seq 和 H3K27ac，没有做 BAF 扰动（ARID1A/B KD 等数据在 `diffbind/` 里另有，未整合）。

## 6. 文件

`query/`：
- `region_evidence.tsv.gz`：设计文档 §八 的最小输出，每个 HT29 区域一行，包含 SOX9 / BAF 证据分级、ATAC 和 CUT&RUN 响应、PMA 层和机制分类。
- `T0_depletion.tsv`
- `T1_{auroc,or,rate_by_atac_baf}.tsv`
- `T2_{or,interaction,mechanism_counts,rate_by_baf_evidence}.tsv`
- `T3_{or,trajectory,recovery_by_baf}.tsv`
- `T4_smarcc1_vs_atac.tsv`
- `T5_coregulator_rank.tsv`
- `summary.json`

`counts/`：
- `manifest.tsv`
- `lib_size.tsv`
- `size_factors.tsv`
- `peaks_in_universe.tsv`
- 只在 Argos：`counts.tsv.gz`、`de_*.tsv.gz`

`pma/`：
- `annotation.tsv.gz`
- 只在 Argos：`pairs.tsv.gz`（2,541 万行）

## 7. 需要你决定 / 确认（v0.2）

1. ~~dTAG 时间设计~~：用户已确认，D2、D4 为降解期，D7、D10、D13 为恢复期。
2. GPT 回合 1 选定方向 (b)，只做一次最小 motif-adjusted 验证（已完成，§8.2），完成后收敛。(a) 和 (c) 暂不开展。
3. 合并需要 GPT 读取已 push 的源码和结果后再审。

## 8. 审核回合 1（GPT，2026-10-30）处理

### 8.1 SMARCC1 相对变化的重复一致性 + 背景对照（51，补充图 A）

方法上不使用逐位点 P 值。对每个 CUT&RUN 文库，计算 log2(SOX9+SMARCC1 区域片段 / 仅 SMARCC1 区域片段)，这个比值不依赖归一化。每天相对 DMSO 的变化分别按 4 种重复配对计算（1-1、2-2、1-2、2-1）。用 IgG 作为背景对照：IgG 只有 DMSO 2 个、D4 2 个、D13 1 个重复。

| 比较（D4 vs DMSO） | SMARCC1 | IgG 背景 | SOX9（阳性对照） |
|---|---|---|---|
| SOX9+SMARCC1 / 仅 SMARCC1 | −0.03 至 −0.25（4/4 为负） | **−0.20 至 −0.29** | −1.45 至 −1.64 |
| ATAC 丢失 / 未丢失（SOX9+SMARCC1 区域内） | −0.44 至 −0.54（4/4 为负） | −0.27 至 +0.01（重复 1 约 −0.24，重复 2 约 −0.02） | — |

- **SOX9 位点 vs 仅 SMARCC1 位点：** SMARCC1 的方向在两个重复里一致，但幅度不超过 IgG 背景。所以 v0.1 §3.4 的"SOX9 位点上 SMARCC1 相对下降更多"**不是 BAF 特异信号，撤回**。可能的原因是 SOX9 位点可及性下降后，CUT&RUN 背景片段本身就减少了。
- **ATAC 丢失 vs 未丢失：** SMARCC1 的下降在 4 种配对中一致，扣除同一配对的 IgG 后仍剩约 −0.2（重复 1）到 −0.5（重复 2）。这只能写成：*在 SOX9 降解后失去可及性的位点上，归一化后的 SMARCC1 CUT&RUN 信号相对下降更多，超出 IgG 背景的部分在两个重复中方向一致。* 它不能区分 BAF 减少是可及性丢失的原因、结果还是共同响应，也不能说明绝对 BAF 占据下降。
- **逐位点的中位数比较：** 因为每个位点计数太少（CUT&RUN 文库 0.2–0.5 M 片段），多数配对的中位数为 0，没有信息量。见 `R1_region_medians_by_pairing.tsv`。

### 8.2 SOX 家族 ChIP vs SOX motif（51，补充图 B–D）

- **SOX9 结合区域：** n = 5,422，其中 D4 丢失 1,008 个。
- **ChIP：** PMA 中 SOX9 以外的 SOX 家族靶点（全部来自 HT-29 以外），≥ 1 个靶点有 ≥ 2 个实验时记为有证据，76% 的区域满足；连续版本用 log1p(实验数)。
- **Motif：** 6 个 HOCOMOCO v14 SOX PWM（SOX9、SOX10、SOX8、SOX13、SOX5、SOX6），用最佳分数超过阈值的部分（3 df spline）加 log1p(命中数)。ChIP 与 motif 的 Spearman ρ 为 0.08。
- **协变量：**
  - B0：DMSO ATAC、GC、CpG、TSS 类别、cCRE、log1p(P_max)；
  - B1：B0 + DMSO SOX9 CUT&RUN 占据。

  初始 SOX9 占据可能是中介变量，所以两种都报告。D4 的 ATAC 和 SMARCC1 变化都不进入模型。

| 协变量 | ChIP 项 | ChIP 单独 OR | ChIP ∣ motif OR (95% CI) | LR P（联合 vs motif） | CV AUROC：协变量 / +motif / +ChIP / 联合 |
|---|---|---|---|---|---|
| B0 | 二元 | 3.42 | 2.35 (1.89–2.93) | 4e-15 | 0.799 / 0.836 / 0.818 / 0.842 |
| B0 | log 实验数 | 2.35 | 1.90 (1.70–2.11) | 3e-33 | 0.799 / 0.836 / 0.839 / 0.851 |
| B1 | 二元 | 2.96 | 2.22 (1.78–2.77) | 5e-13 | 0.825 / 0.845 / 0.837 / 0.850 |
| B1 | log 实验数 | 2.09 | 1.77 (1.59–1.98) | 2e-26 | 0.825 / 0.845 / 0.848 / 0.856 |

- **独立贡献存在：** 控制 motif 和初始 SOX9 占据后，SOX 家族 ChIP 证据仍有独立贡献，OR 约 1.8–2.2。
- **但判别力增益很小：** 在 motif 模型基础上，交叉验证 AUROC 只提高 0.005–0.015。
- **效应依赖 motif（补充图 B）：** 在 motif 最强的三分位里，有 SOX 家族 ChIP 的区域丢失率为 33% vs 24%；在中、低三分位里方向相反（15% vs 19%，7% vs 11%）。可能的解释是：跨 context 的 SOX ChIP 在强 motif 位点标记"真实可结合的 SOX 位点"，而在弱 motif 位点更多反映"热点 / 共结合"。
- **结论：** 这是一个候选发现，不是验证过的规律。按 GPT 回合 1 的要求，到此收敛，不再扩展到其他 TF 或细胞系。

### 8.3 BAF 模型的协变量敏感性（51）

在 B0 或 B1 基础上加入 6 个 SOX PWM 后：
- HT29 SMARCC1：OR 0.47（0.38–0.56）或 0.45（0.37–0.54）；
- PMA BAF：1.17（0.79–1.71）或 1.20（0.82–1.77）。

原假说不成立的结论不随协变量变化。

### 8.4 审核要求的处理汇总

| 要求 | 处理 |
|---|---|
| 核对 dTAG 时间设计 | metadata 中没有记录；用户确认 D2、D4 为降解期，D7、D10、D13 为恢复期，恢复使用 degradation / recovery 术语 |
| SMARCC1 两个重复是否一致 | 方向一致，但 SOX9 位点 vs 仅 SMARCC1 位点的比较被 IgG 背景解释，撤回 v0.1 §3.4；ATAC 丢失 vs 未丢失的比较保留为相对信号 |
| SOX ChIP vs motif vs 联合 | 完成：控制 motif 后 ChIP 仍有独立贡献，但判别力增益小，且依赖 motif 强度 |
| 区分是否控制初始 SOX9 占据 | 完成（B0 / B1） |
| Push | 已 push，不合并 |
