# PMA ChIP-Atlas 占据图谱：hg38 与 mm10 总说明

更新日期：2026-11-02。本文档汇总目前用 ChIP-Atlas 做了哪些处理和分析、生成了哪些文件、分别是怎么做的。
细节以各处的原始记录为准：

- 设计：`docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md`。§1–§18 是 hg38，§19 是 mm10。完整版在分支
  `task_20261030_chipatlas_mm10` 上；main checkout 当前分支上的副本是只到 §9 的旧版。
- 数据记录：`DATA/2.PROJECTS/PMA/occupancy_chipatlas/link.md`（hg38）和
  `DATA/2.PROJECTS/PMA/occupancy_chipatlas_mm10/link.md`（mm10）。
- 结果稿：`Figures/Figure1/*.result.md`、`Figures/ContextQuery/`。

## 0. 总览

| | hg38 | mm10 |
|---|---|---|
| 数据根目录（Argos） | `/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas` | `/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas_mm10` |
| Mac 上的副本 | `processed/light_v1/`（sha256 已核对）、`result/` 大部分 | 仅 `link.md` |
| 原始数据 | `raw/2026-10-17/` | `raw/2026-10-30/` |
| 发布名 | `PMA_ChIPAtlas_hg38_20260926peaks_20261014meta_v1` | `PMA_ChIPAtlas_mm10_20260926peaks_20261014meta_v1` |
| 基因命名 | HGNC | MGI |
| TF/CAP 分类 | 人工整理（用户原始版 + v1.1） | GO 规则自动分类（草稿，待复核） |
| 构建代码 | 提交 `68b6ad1`（v1），light 和轨道 `fe44a44` / `6c6d1a6` | 提交 `eb182f4`（分支 `task_20261030_chipatlas_mm10`） |
| 下游分析（`result/`） | 共 30 多个目录，见第 4 节 | 未做 |

两个基因组用的是同一套代码，用环境变量 `PMA_GENOME=hg38|mm10` 切换（`scripts/04a_chipatlas/genome_config.py`）。
在 hg38 上，改动后的代码和原来的输出逐字节一致。

## 1. 输入数据

ChIP-Atlas 的两个文件：

- `allPeaks_light.<genome>.05.bed.gz`：ChIP-Atlas 对每个实验统一用 MACS2 调用的 peak，阈值 q < 1e-5，版本 2026-09-26。
  hg38 文件 21.4 GB，mm10 为 15.4 GB。
- `experimentList.tab`：元数据，版本 2026-10-14。每行对应一个（实验，基因组）组合，同一实验在不同基因组下各占一行。

参考文件：

| 用途 | hg38 | mm10 |
|---|---|---|
| 基因命名 | HGNC `hgnc_complete_set.txt` | MGI `MRK_List1.rpt`（含已撤销的符号） |
| TF 列表 | Lambert 2018 TF_names v1.01 | GO:0003700 及其下级术语（GO Consortium 的 `mgi.gaf.gz` + `go-basic.obo`） |
| 黑名单 | ENCODE hg38 blacklist v2 | ENCODE mm10 blacklist v2 |
| 染色体长度 | UCSC `hg38.chrom.sizes` | UCSC `mm10.chrom.sizes`（已与 `~/reference` 中 10x `.fai` 的 22 条主染色体核对） |
| 抗原名例外表 | `config/chipatlas_antigen_exceptions.tsv` | `config/chipatlas_antigen_exceptions.mm10.tsv` |

原始目录只追加、不修改。每个原始目录都有 `README.source.md`，里面记录下载地址、日期和 MD5。

## 2. 怎么做的：构建流程

所有计算都在 Argos 的 SGE 上运行，Mac 只负责写代码和存小文件。脚本都在 `scripts/04a_chipatlas/`。

### 2.1 核心实验级 BED（Step 4a，设计 §1–§9）

| 步骤 | 脚本 | 做什么 |
|---|---|---|
| 实验表 | `01_experiments.py` | 选出当前基因组下的 TF/others 和 RNA polymerase 实验。抗原名统一为 HGNC/MGI 官方符号，`chipatlas_rules.map_antigen` 会记录映射方法；同时规范抗体和细胞背景字段，并分出 `target_category`（TF / CAP / Pol 等） |
| peak | `02_peaks.py` | 流式读取 peak 归档，给每个 peak 附上实验元数据，写成 BED6+18。只加 QC 标记，不删任何行：例如 `blacklist_majority_overlap`；染色体不在 sizes 文件中的行会被拒绝并记录 |
| 压缩和索引 | `run_4a.sh` | bgzip 压缩、tabix 建索引，并在几个已知位点抽查 |
| 收尾 | `03_finalize.py` | 写出实验表、`.as`、`schema.json`、`MANIFEST.json` 和 `reconciliation_report.json`。对账内容包括：每个实验的 peak 数与元数据一致、行数守恒、排序正确 |

对组蛋白、ATAC-seq 和 DNase-seq 也用同一流程，分别得到 `histone_v1/`、`atac_v1/`、`dnase_v1/` 三个实验级 BED。

### 2.2 去冗余 light BED（设计 §10，`04_light_bed.py`，`run_light.sh`）

对每个靶标，把所有实验中重叠或首尾相接的 peak 串联合并成一个区域。BED6 第 5 列 score 取 min(1000, 支持该区域的实验数)。
每个区域由哪些实验支持，记录在 `detail.tsv.gz` 里。protein 和 histone 各输出一套。

### 2.3 证据轨道（设计 §11–§12，`05_occupancy_tracks.py`、`run_tracks.sh`）

所有轨道都由 peak 累计计数得到，不是 reads 覆盖度，也不代表结合强度。

| 轨道 | 含义 |
|---|---|
| `experiments` | 该位置被多少个实验的 peak 覆盖 |
| `proteins` | 被多少种蛋白覆盖 |
| `tf` / `cap` | 分别只计 TF 类、只计非 TF 的染色质相关蛋白（CAP） |
| `rnapol2/3_experiments` | 只计 Pol II 或 Pol III 实验 |
| `histone_experiments` | 组蛋白实验数 |
| `histone_modifications` | 修饰种类数 |
| `histone_H3K4me1` 等 6 条 | 6 种核心修饰各一条 |
| `atac/dnase_experiments` | 开放染色质实验数 |
| `atac/dnase_celltypes` | 开放染色质细胞类型数 |

每条轨道都同时输出 `.bw` 和 `.bedGraph.gz`（带 `.tbi`），并按恒等式做 QC，结果写在 `qc.json`。

配套步骤：

- `06_split_by_class.py`：把 protein light BED 按 8 个蛋白类别拆开，存到 `protein_by_class/`。
- `08_histone_labels.py`：规范组蛋白标签。
- `09_igv_session.py`：生成 3 个 IGV session。
- `10_mask_blacklist.py`：把每套轨道拆成 `_noBlacklist`（去掉黑名单区域）和 `_blacklistOnly`（只保留黑名单区域）两个版本。
- `11_experiment_filter.py`：实验过滤，规则见下表。

**实验过滤**的规则：ATAC 和 DNase 要求 peak 数 ≥ 10,000、不是单细胞实验、不是非开放染色质实验；组蛋白只去掉单细胞实验。

| | hg38 保留 / 总数 | mm10 保留 / 总数 |
|---|---|---|
| ATAC-seq | 18,651 / 48,776 | 19,438 / 46,073 |
| DNase-seq | 2,086 / 4,604 | 1,151 / 1,662 |
| 组蛋白 | 37,762 / 40,444 | 46,490 / 46,528 |

ATAC 被剔除的主要原因是 peak 太少：hg38 有 25,629 个只因 peak 少被剔除，另有 4,217 个同时是单细胞且 peak 少；mm10 分别是 15,609 和 10,824 个。
hg38 过滤前的轨道放在 `light_v1/preFilter/`。

### 2.4 蛋白分类

- **hg38**：`PMA_chipatlas_hg38_protein_class_annotation.csv` 是用户的原始分类，`.v1_1.csv` 是修订版。
- **mm10**：`29_go_class_annotation.py`（只在 mm10 分支上）按 MGI 的 GO 注释，依次套用以下规则，命中第一条即定类：
  1. TF（GO:0003700）
  2. 组蛋白修饰写入/擦除酶
  3. 转录机器
  4. 组蛋白读取蛋白
  5. 染色质重塑蛋白
  6. 架构/黏连蛋白（CTCF 和 CTCFL 直接归入此类）

  一条都不匹配的归为 `Other/ambiguous`。在人和小鼠都有的同名基因上，这套规则和 hg38 v1.1 人工分类的一致率是 81.6%（559/685）。

## 3. 生成了哪些文件（processed）

### 3.1 核心发布 `processed/v1/`

| 文件 | 说明 |
|---|---|
| `PMA_chipatlas_<g>_occupancy.bed.gz` + `.tbi` | BED6+18，每个实验的每个 peak 一行 |
| `PMA_chipatlas_<g>_experiments.tsv.gz` | 实验表，包括没有 peak 的实验 |
| `PMA_chipatlas_<g>_occupancy.as`、`schema.json` | 列定义 |
| `reconciliation_report.json` | 对账报告 |
| `MANIFEST.json` | 版本、代码提交和计数 |

| 计数 | hg38 | mm10 |
|---|---|---|
| peak 行数 | 443,029,514 | 272,929,396 |
| 实验数（有 peak 的） | 39,099（38,795） | 28,085（26,288） |
| 被拒行 / 排序错误 | 0 / 0 | 0 / 0 |
| 标记 `blacklist_majority_overlap` 的行 | 27,838,422 | 15,868,314 |
| peak 数与元数据不一致的实验 | 9 | 0 |
| 染色体 / contig 数 | 194 | 66 |

### 3.2 其他实验级 BED

`processed/{histone_v1,atac_v1,dnase_v1}/PMA_chipatlas_<g>_{histone,atac,dnase}_occupancy.bed.gz`（各带 `.tbi`）。
磁盘占用：hg38 分别为 20 GB、20 GB、2.9 GB；mm10 分别为 12 GB、17 GB、0.97 GB。

### 3.3 `processed/light_v1/`（hg38 79 GB，mm10 33 GB）

| 子目录 / 文件 | 内容 |
|---|---|
| `protein/PMA_chipatlas_<g>_protein_nr.*` | `.bb`、`.bed.gz` + `.tbi`、`.detail.tsv.gz` + `.tbi`（每个区域的支持实验）、`.experiments.tsv.gz`、`.targets.tsv`、`.qc.json`、`MANIFEST.json` |
| `histone/PMA_chipatlas_<g>_histone_nr.*` | 文件结构与 protein 相同 |
| `protein_by_class/` | 8 个类别各一套 `.bb` + `.bed.gz`；`split_qc.json` |
| `tracks/` | `experiments`、`proteins`、`tf`、`cap` |
| `tracks_rnapol/` | `rnapol2_experiments`、`rnapol3_experiments` |
| `tracks_histone/` | `histone_experiments`、`histone_modifications`，以及 H3K4me1、H3K4me3、H3K27ac、H3K27me3、H3K36me3、H3K9me3 |
| `tracks_atac/`、`tracks_dnase/` | `*_experiments`、`*_celltypes` |
| `tracks*_noBlacklist/`、`tracks*_blacklistOnly/` | 上面每套轨道的黑名单拆分版本，附 `mask_qc.json` |
| `PMA_chipatlas_<g>_experiment_filter.tsv` | 每个实验是否保留及原因 |
| 分类 / 标签表 | hg38：`*_protein_class_annotation{,.v1_1}.csv`；mm10：`*_protein_class_annotation.go_v1.csv`、`*_histone_marks.tsv`。两者都有 `*_histone_label_annotation.tsv` |
| `PMA_occupancy_evidence{,.noBlacklist,.blacklistOnly}.igv_session.xml` | IGV session |
| `preFilter/` | 仅 hg38：过滤前的 ATAC、DNase、组蛋白轨道 |
| `raw_accessions/` | 仅 hg38：纳入的 ATAC（18,651 个实验 / 30,265 个 run）和 DNase（2,086 / 4,758）的 run 列表，附 ENA FASTQ 地址 |

| 计数 | hg38 | mm10 |
|---|---|---|
| protein light 区域 / 靶标数 | 70,878,901 / 1,865 | 41,669,817 / 919 |
| histone light 区域 / 标签数 | 15,994,563 / 144 | 11,113,403 / 130 |

### 3.4 仅 hg38 有的文件

- `processed/unique_bed6_v1_d84d98b/`：坐标去重的 BED6，共 1,024,044,914 个区域，合并了 TF、Pol 和组蛋白。构建端自检和独立复核都是 PASS。
  同级的 `unique_bed6_v1/` 和 `unique_bed6_v1_retry_a3c0c68/` 是失败的候选版本，**不要用**。
- `*_work/` 目录：中间表和日志，不对外使用。

## 4. hg38 下游分析（`occupancy_chipatlas/result/`）

除特别说明外，以下分析都只基于 hg38。

### 4.1 共占据与聚类（设计 §13–§17，2026-10-20/21）

| 分析 | 问题与方法 | 目录 / 脚本 | 主要结论 |
|---|---|---|---|
| 蛋白共占据（Fig 1E） | 构建蛋白 × 500 bp 区间的占据矩阵，算 Jaccard；用 Complex Portal 做基准（AUROC，广度匹配背景置换）；候选蛋白对再过跨研究、留一研究、同背景三项检验 | `cooccupancy_v1/`、`validation_v1_1/`、`validation_v1_2/`；脚本 12、16、18–20 | 808 个蛋白，AUROC 0.811。FDR ≤ 0.05 的复合物 172/373。未收录的 300 对中有 47 对通过三项检验 |
| 实验聚类（Fig 1F） | 对 29,900 个实验做 TF-IDF + SVD，取 kNN；用 κ 比较不同邻居限制，并在 peak 数十分位内做置换 | `experiment_clustering_v1{,_1}/`；脚本 13、17 | 按蛋白和按细胞类型的 κ 分别从 0.43/0.46 降到 0.25/0.23，说明研究来源和测序深度的混杂很大 |
| 区域类别（Fig 1G） | 对被 ≥ 3 个蛋白占据的 1,531,237 个区间做 k-means，k = 20；用 ARI 评估稳定性，并标出受单一研究驱动的类 | `region_classes_v1/`；脚本 14、20、21 | ARI 0.63–0.76。C11（CTCF–黏连蛋白）最稳定；C07、C09 由单一研究驱动 |
| Figure 1E–G 作图 | — | `figure1_clustering_v1_2/`；脚本 22 | — |

### 4.2 热点（设计 §18，2026-10-21 起）

| 分析 | 问题与方法 | 目录 / 脚本 | 主要结论 |
|---|---|---|---|
| 阈值 | 把基因组切成 6,176,550 个 500 bp 区间，统计 protein/ATAC/DNase 的分布 | `hotspot_thresholds_v1/`；脚本 23、24 | — |
| 热点区域 | 在非零区间中按分位数分为 top20/10/5/1 四层；开放热点要求 ATAC 和 DNase 同时达标；相邻区间合并 | `hotspot_regions_v2/`（v1 已被取代）；脚本 25；副本在 `Figures/Tables/` | top1 区间被 ≥ 244 种蛋白占据，共 27,521 个区域；91–94.5% 的开放热点同时是蛋白热点 |
| motif 富集 | 用 HOMER 生成匹配对照（G/A/S 三类），用 SEA 检验 JASPAR 2026 和 PMA 三档 motif 库 | `hotspot_motif_v1/`；脚本 26–28 | 远端热点以 AP-1 为主；CTCF 富集比最高；启动子热点以 ETS 为主。控制开放程度后 AP-1 大幅减弱 |
| 蛋白支持 | 统计热点内有 ≥ 2 个独立实验支持的蛋白和 DBP 数 | `hotspot_protein_support_v1/`；脚本 29\*、30 | top1 每个区域的蛋白数中位数为 277，其中 DBP 179 |
| 注释与背景 | 注释 TSS、cCRE、CpG 和 GC；用协变量分层找残余热点；比较 21 种细胞类型 | `hotspot_annotation_v1/`、`hotspot_context_v1/`、`hotspot_matched_v1/`；脚本 31–36 | top1 中 PLS 占 43.1%；协变量解释 R² ≈ 0.71；残余热点 4,887 个，其中 73.7% 是 dELS |
| HT29 ATAC 对照 | 双向比较 HT29 的 ATAC peak 和热点的重叠，画覆盖度–召回曲线 | `hotspot_ht29_atac_v1/`；脚本 37–42 | 最强的 20k 个 peak 有 98.6% 落在 top20 热点内；top1 中有 79.0% 在 HT29 开放 |
| HG1 普遍性 | 计算覆盖度调整后的 context 广度、主导度和留五保留率 | `hotspot_universality_v1/`；脚本 43、44 | 预设判定：**混合**（留五保留率 78.7% < 80%） |
| HG2 开放程度 | 用 HGB 嵌套模型和染色体留出，检验残差在两半实验间能否重复 | `hotspot_accessibility_v1/`；脚本 45、46 | 预设判定：**有独立信息**（R² 0.69，ρ_res 0.46） |
| HG3 motif 多样性 | 用 MOODS 扫 JASPAR 2026，看 motif 多样性能额外解释多少 R² | `hotspot_motif_diversity_v1/`；脚本 47、48 | 预设判定：**部分支持，接近不支持**（ΔR² 0.0053） |

HG1–HG3 的汇总见 `Figures/Figure1/Figure1.hotspot_reference_boundaries.result.md`。最终把热点定义为跨 context 的累计蛋白占据热点，
热点机制这条支线已于 2026-10-30 关闭（HD-12）。

### 4.3 其他探索（2026-10-30 至 11-02）

| 分析 | 目录 / 脚本 | 结论 |
|---|---|---|
| 带符号的蛋白模块 PM1–PM4：在 K-562 中按 MH 分层估计蛋白对之间的正负关联，用 Leiden 划分模块 | `signed_protein_modules_v1/`；脚本 49–51 | **STOP**：负关联只有 0.8%，且不能重复 |
| POM Phase A（G0–G3）：在 K-562 中验证 20 个区域类别 | `pom_phaseA_v1/`；脚本 52、53 | **PASS**（C02 AP-1、C19 TAL1–GATA1）。NMF 需要用户授权 |
| Context Query：HT29 dTAG-SOX9 时间序列与 PMA 证据的交叉 | `context_query_ht29_sox9baf_v1/` | 探索性：SMARCC1 占据与 ATAC 丢失负相关（OR 0.39）；PMA 的 BAF 证据无关联 |
| G1 泄漏控制：ENCODE 真值标签与 ChIP-Atlas SRX 的对应表 | `g1_leakage_v1/`；`scripts/05_g1/` | 直接对应 463 个，加上同研究近重复共 608 个；G1 拟合目前暂停 |

### 4.4 论文方向的应用（分支 `task_20261030_paper_ideas_v2` 等；各有独立的结果稿）

- **Gate A**：锚定 DBP 的共占据基准。判定 CONDITIONAL，已关闭。目录 `gateA_cooccupancy_benchmark_v1/`。
- **Gate B**：预测 HT29 中 SOX9 降解后的 ATAC 丢失。判定 GO。目录 `gateB_sox9_dependency_v1/`。
- **Gate V**：用 K562 GATA1 CRISPRi 重复 Gate B。判定 GO，5/5。目录 `gateV_gata1_k562_v1/`。
- 相关目录：`y3_sox9_rna_prediction_v1/`、`paper_ideas_v2_crosssystem_v1/`。
- **N01**：占据嵌入与 Sei 序列模型的多任务比较。判定 T2_GO / T3_NOT_ESTABLISHED。目录 `n01_multitask_v1/`。
- **N02**：占据的可重复性和校准。目录 `n02_calibration_v1/`。
- **N03**：跨 TF 的元件脆弱性。不可行，已终止。目录 `n03_fragility_v1/`。
- **发布和作图**：
  - `pma_release_v1/`：发布 manifest 和环境；
  - `main_figures_v1/`、`main_figures_v2/`：正文图和补充图，以及冻结输入的 manifest；
  - `revision_v2/`：修订分析。

这些分析的原始数据在 `raw/2026-10-20_ena`、`2026-10-21*`、`2026-10-30_*`、`2026-10-31_*`，每个目录的 README 有说明。
`_superseded/`、`_test_v1_2/` 是被取代的或测试用的结果，不要使用。

## 5. mm10 的特殊之处与使用注意

- **范围**：只做了 3.1–3.3（核心 BED、light BED、轨道）。聚类、热点、motif 富集都没有做。
- **分类需要复核**：TF/CAP 类别是 GO 规则草稿，`assignment_basis` 列取值为 `go_rule` 或 `no_go_rule_match`。
  因此 tf/cap 轨道和 `protein_by_class/` 应描述为“GO 规则分类”。
- **只用标准染色体**：mm10 黑名单不覆盖 chrUn 和 random contig，去黑名单后的 protein 轨道最大值仍在 `chrUn_GL456392`（25,663 个实验）。
  标准染色体上的最大值在 chr5:147,611,490（14,577 个实验），很可能是黑名单没有收录的伪影。
- **组蛋白标签缺口**：约 55 个组蛋白实验的标签现有规则还不认识，被归为 `pan_or_ambiguous`，因此没有计入组蛋白实验数轨道和修饰种类数轨道。
  这些标签包括 pr、bhb、me2s/me2a，以及 H3mm\*、TH2A/B 等小鼠变体。后续需要扩展 `08_histone_labels.py`。
- **`code_commit` 为空**：MANIFEST 里的 `code_commit` 是空的，因为代码是用 `git archive` 部署到 Argos 的。实际使用的提交是 `eb182f4`。
  Argos 上的代码在 `/home/zz950/PMA_fetch/claude_mm10_eb182f4/`，作业和日志在 `/home/zz950/PMA_fetch/claude_sge_mm10_20261030/`。
- **QC**：13 个 QC JSON 全部 PASS。

## 6. 已知的记录问题

- **脚本编号冲突**：`29_go_class_annotation.py`（mm10 分支）与 main checkout 中未提交的 `29_hotspot_protein_support.py` 编号相同；
  `ContextQuery` 用的 45–52（分支 `task_20261030_context_atlas_sox9baf`）也和 HG2/HG3/PM/POM 的 45–53 编号重叠。
  引用脚本时要带上分支或文件全名。
- **代码分散在多个未合并的分支**：
  - `step4a-chipatlas-occupancy`：v1；
  - `task_20261020_chipatlas_light_bed`：light 和轨道；
  - `task_20261030_chipatlas_mm10`：mm10；
  - `task_20261030_paper_ideas_v2`：Gate 和 N 系列。

  HG1–HG3、PM、POM 的脚本（43–53）目前还没有提交。
- **大文件只在 Argos**：以下文件只有 Argos 上有，Mac 上找不到属于正常情况：
  - `bin_model.tsv.gz`；
  - Context Query 的 `counts/`、`pma/parts/`；
  - signed modules 的 `parts/`、`logs/`。
