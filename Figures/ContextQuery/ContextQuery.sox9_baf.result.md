# Context Query v0.1 — HT29 SOX9–BAF × PMA (Result v0.1)

- 日期：2026-10-30
- 分支：`task_20261030_context_atlas_sox9baf`（基于 `task_20261030_hotspot_followup`）
- 设计来源：`UDE/design/history/Context-conditioned Regulatory Evidence Atlas-v1.0.md`（GPT，§八 "PMA Context Query v0.1 — SOX9–BAF"）
- 代码：`scripts/04a_chipatlas/45–49`（45 counts，46 PMA evidence，47 DESeq2，48 tests，49 figure；SGE 提交脚本 `45_47_context_query_jobs.sh`）
- 结果：`DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/context_query_ht29_sox9baf_v1/`（Argos 同路径，`counts/` 和 `pma/` 的大文件只在 Argos）
- 图：`…/context_query_ht29_sox9baf_v1/figures/ContextQuery_SOX9BAF.{pdf,png}`（A–J）
- 状态：探索性 application，**不是 L3 验收**；没有改 G1（HOLD，HD-11）和 FG-1 进度。

## 0. 问题与回答（一句话）

**问题（设计文档 §七）：** SOX9 依赖的染色质可及性变化，是否优先发生在有 BAF 相关调控证据的位点上？

**回答：不是，方向相反。** 在 SOX9 结合位点中，HT29 自己测到的 SMARCC1（BAF）占据与 D4 ATAC 丢失**负相关**（校正 OR 0.39，95% CI 0.32–0.47）。PMA 的跨 context BAF 证据在校正开放度、P 等协变量后没有关联（OR 1.26，CI 0.87–1.83）。真正能从 PMA 证据中挑出 SOX9 依赖位点的是 **SOX 家族本身的跨 context 占据**（SOX10、SOX8、SOX9、SOX13、SOX5，校正 OR 2.7–9.8，FDR < 1e-19），排在全部 810 个 PMA 靶点的前 12 名以内。另外有一个机制线索：在同时有 SOX9 和 SMARCC1 的位点上，SOX9 降解后 SMARCC1 也下降，D4 时比只有 SMARCC1 的位点多降约 0.48 log2；在 ATAC 丢失的位点降得最多。

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

**时间设计是推断出来的，需要你确认。** SOX9 CUT&RUN 信号（library-size 归一化，SOX9 位点中位 log2FC）为 D2 −1.12、D4 −2.14、D7 −1.50、D10 −0.37、D13 0.00。所以本文把 D2–D4 当作"降解期"、D7–D13 当作"恢复期"（可能是 D4 洗脱 dTAG）。实际给药和洗脱方案需要你确认。

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

### 3.4 机制线索：SOX9 缺失时，SOX9 位点上的 SMARCC1 也一起下降（Fig. A, H）

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
3. **有用的是同识别特异性的跨 context 占据（SOX 家族）**（3.5）。它在校正 motif 后仍有增益，说明 PMA 的 ChIP 证据携带了 PWM 之外的"真实可结合位点"信息。这一点值得作为 Context Query 的核心卖点继续检验。
4. **机制层的增量信息来自 context 内动态数据**（3.4）。PMA 适合用来提出和排序假说，验证必须依赖 context-matched 扰动数据。

## 5. 局限

- 时间设计（降解 / 洗脱）是从数据推断的，需要确认。
- CUT&RUN 的 spike-in 失效，绝对占据变化无法确定，只做位点组间比较。CUT&RUN 文库小（0.2–0.5 M 片段），单位点估计噪声大，DESeq2 在 CUT&RUN 上几乎没有单位点显著结果。
- "SOX9 结合"用的是 DMSO HA-SOX9 CUT&RUN 两个重复都有峰，约 6k 个区域。依赖性判定只基于 D4 vs DMSO 一个比较，DMSO 只有 D13 一个时间点的对照。
- 区域全集限于 HT29 开放染色质，不评估 SOX9 让关闭区域打开的情形；D4 时 SOX9 位点有 121 个上升。
- PMA BAF 证据很宽：54% 的 HT29 开放区域有 `pma_baf`，因为 SMARCA4 有 348 个实验。二元定义的区分度有限；分级结果见 Fig. C、F。
- 排序（T5）中的 SOX9 一行包含 HT-29 公共 ChIP，不完全外部。
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

## 7. 需要你决定 / 确认

1. dTAG 方案：D4 洗脱、D7–D13 恢复，这个推断对吗？
2. 主假设（BAF-associated → SOX9-dependent）已被否定。下一步方向三选一：
   - (a) 把"SOX9 依赖的 BAF 占据变化"（3.4）作为新的机制问题，需要更深的 SMARCC1 / ARID1A CUT&RUN 或可靠的 spike-in；
   - (b) 把"同家族跨 context 占据"（3.5）推广为 Context Query 的通用检验，换其他 TF 或细胞系；
   - (c) 加入 RNA-seq 和 ARID1A/B KD ATAC，做 BAF 扰动方向的对称分析。
3. 是否发给 GPT 审阅。建议审阅重点：3.3 的协变量选择，以及 3.4 在没有 spike-in 时的解释边界。
