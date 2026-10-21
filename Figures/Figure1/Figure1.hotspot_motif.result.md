# Figure 1 result：热点区域的 motif 富集

> **文档性质：** 内部分析结果稿，非投稿版本。
> **当前版本：** v0.1，2026-10-21
> **代码：** 分支 `task_20261020_chipatlas_light_bed`，脚本 `scripts/04a_chipatlas/26_motif_enrichment_prep.py`、`27_motif_enrichment_task.sh`、`28_motif_enrichment_collect.py`（结果来自提交 5a9c29c 的 run 2，汇总脚本为 b7685fa）。设计见 §18.3。
> **上游：** 热点区域定义见 [Figure1.hotspot_regions.result.md](Figure1.hotspot_regions.result.md)（hotspot_regions_v2，分 top20、top10、top5、top1 四层）。
> **结果目录：** `DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/`

## Methods

**目标序列**
- 每个热点区域只取 1 条 500 bp 序列，即区域内的峰值区间：
  - 蛋白热点取蛋白数最高的区间；
  - 开放热点取 ATAC 与 DNase 平均排名最高的区间。
- 这样一个长区域不会被重复计数。
- 每个集合随机抽取 10,000 条（seed 1），top1 开放热点总数不足时全部使用。

**对照序列**

用 HOMER 5.1 `homer2 bg` 生成。它在 10 个 GC/CpG 分层内挑选与目标序列 GC 和 k-mer 组成匹配的基因组序列，数量为目标的 2 倍。所有对照的 GC/k-mer 频率与目标相差都在 0.0018–0.0067 之间。

| 代号 | 对照来源 | 回答的问题 |
|---|---|---|
| **G**（基因组匹配） | 同一类别、同一层级热点以外的、不在黑名单内的区间：全部启动子区间加 50 万个随机远端区间 | 热点区域和组成相近的普通基因组序列相比，多了哪些 motif |
| **A**（再加开放程度匹配，仅蛋白热点） | 蛋白数低于同一层级，但开放程度（ATAC/DNase 排名）与目标分 20 层匹配的区间，每个目标配 20 个候选 | 在同样开放的区域里，蛋白热点还多了哪些 motif |
| **S**（启动子 / 远端分层） | top5 热点按 TSS ±1 kb 分成启动子和远端两部分，对照只从同一层内抽取 | 结果是否只由启动子驱动 |

**motif 库**

| 库 | motif 数 |
|---|---|
| JASPAR 2026 CORE vertebrates non-redundant（PMA v0.3 原始层） | 1,019 |
| PMA Step 3B 共识代表 motif，HIGH 层 | 2,059 |
| PMA Step 3B 共识代表 motif，MEDIUM 层 | 995 |
| PMA Step 3B 共识代表 motif，LOW 层 | 542 |

HIGH、MEDIUM、LOW 是三种聚类分辨率，不代表质量高低。

**检验**
- 用 MEME 5.5.9 SEA，并以 HOMER 生成的序列作对照（`--n`）。
- 为了加速，每个 motif 库拆成 8 份并行运行。每个 motif 的 p 值独立计算，所以拆分不影响结果。
- E 值和 BH q 值在合并后按整个库重新计算。
- 判为显著的条件：q < 0.05 且富集比（ENR）> 1。
- 排序先看 q 值，同时列出 ENR、TP%（目标序列中含该 motif 的比例）和 FP%（对照序列中的比例）。

**修正记录**

第一轮的结果在读取任何结果之前就被作废，原因有两个：
- G 对照排除了全部 top20 区间，而几乎所有 CpG 岛都在热点内。HOMER 在每个 GC/CpG 层中要求对照与目标数量对等，最高 CpG 那一层找不到足够的匹配序列，于是整体对照被压缩。例如 protein top1 只剩 40 条对照序列，protein top5 只剩 920 条。
- 每个集合用 50,000 条序列，计算量过大。

改进后的设计记录在 §18.3。

## Results

### 1. 对照质量

- **G 和 S 对照：** 全部达到预定规模（2 倍目标数）。
- **A 对照：** 在 CpG 含量很高、又需要开放程度匹配的那一层，能找到的匹配序列有限，所以规模偏小：

| 对照 | 序列数 | 状态 |
|---|---|---|
| A_protein_top20 | 9,390 | 正常 |
| A_protein_top1 | 6,730 | 正常 |
| A_protein_top10 | 4,392 | 标记为 SMALL_CONTROL |
| A_protein_top5 | 2,280 | 标记为 SMALL_CONTROL |

- **对照规模的含义：** A 对照本身就说明，"高开放、高 CpG、但蛋白数不高"的区间在基因组里很少。
- **证据：** [`summary/runs_summary.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/runs_summary.tsv)

### 2. 热点区域富集的 motif（按显著性排序，JASPAR 库）

![Motif heatmap JASPAR](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/Motif_A_JASPAR2026_CORE_vert_nr.png)

热图说明：
- 颜色为 log2 富集比；
- 灰点表示该比较中不显著；
- 行是各比较中排名前 8 的 motif 的并集。

各比较排名靠前的 motif（ENR 为富集比，q 为 BH 校正后的值）：

| 比较 | 排名靠前的 motif |
|---|---|
| G_protein_top5 | FOS::JUNB 2.97×（q = 1e-253）、FOS::JUND、FOSL1::JUN、FOSL2::JUN、BACH1、FOS::JUN、FOSL1、**CTCF 5.52×**（q = 1e-234）、BATF/BATF3、JUN |
| G_protein_top1 | **CTCF 5.58×**（q = 1e-282），其后依次为 ETV4、FEV、ELK4、ETS1、FLI1、ELK3、ELK1（ETS 家族，1.5–1.7×）、JUN::JUNB、ZNF131、ZBTB11 |
| G_open_top5 | **CTCF 7.29×**（q = 1e-470）、FOS::JUNB 3.50×、FOSL1 3.93×、FOSL2::JUND、BACH1、JUNB、JUND |
| G_open_top1 | CTCF 7.08×、KLF8 2.97×、ZNF131、ETV4、ETV5、ELK3、FEV、ELK1 |
| S_protein_top5_distal | 几乎全是 AP-1（FOS/JUN/FOSL/BACH1，3.1–3.5×）。按富集比排序时 CTCF 最高，为 7.03× |
| S_protein_top5_promoter | ETS 家族（ETV4、FEV、ELK3、ETV5、ELK1、FLI1、ELF2，1.4–1.6×）、TFDP1、ZNF131、CTCF 4.86×、CGGBP1 |
| S_open_top5_distal | AP-1 3.6–3.9×，**CTCF 26.8×**（TP 14.7%，FP 0.54%） |
| A_protein_top5（对照偏小） | CTCF 2.62×（q = 1e-15）、FOX 家族（FOXS1、FOXD1、FOXA2/3、FOXP1/4、FOXM1，1.7–2.1×） |
| A_protein_top1 | ETS 家族（ELK3 3.42×、ETV4、ETV5、FEV、ELK1、ETS2、FLI1）、ZBTB11、NRF1 |
| A_protein_top20 / top10 | ZNF131、Zfp961、E2F1/E2F8、ZBED4、CGGBP1、ZNF142、CTCF |

- **显著 motif 的数量很多：** G 对照下，JASPAR 中有 637–754 个 motif 显著，占 1,019 个的 63–74%。这些区域是转录因子结合的密集区，所以单看显著性会饱和，解读时要同时看富集比。
- **证据文件：**
  - 每个比较和每个库的完整排序：[`summary/ranked/`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/ranked/)
  - 各比较前 20 名：[`top_motifs.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/top_motifs.tsv)
  - 全部结果：[`all_results.tsv.gz`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/all_results.tsv.gz)
  - 各比较的显著 motif 数：[`significant_counts.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/significant_counts.tsv)

### 3. PMA 共识 motif 库的结果

[HIGH](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/Motif_A_PMA_HIGH.png) / [MEDIUM](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/Motif_A_PMA_MEDIUM.png) / [LOW](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/hotspot_motif_v1/summary/Motif_A_PMA_LOW.png)

- **与 JASPAR 一致：**
  - G_protein_top5 中排名靠前的是 C2H2 ZF（PATZ1/MAZ，8.3×）、CTCF 类（7.2–7.6×）和 bZIP（JUN/JDP2/BACH2/NFE2，2.3–3.6×）；
  - A_protein_top1 中排名靠前的是 ETS（ELF1/ELF2、ELK4/ETV6、GABPA）。
- **共识库自身的问题：** 即使在最粗的 LOW 层（542 类），CTCF 仍分散在约 10 个类中（例如 PMC_M00015、M00112、M00139、M00249、M00255、M00283）。这些类在热点中同时富集。这说明 Step 3 的 motif 参考在 CTCF 上仍有冗余，应当回到 Step 3 处理。

## 结论

1. **三类 motif 构成了热点区域的序列特征：**
   - **AP-1（bZIP）** 主导远端热点：在蛋白热点和开放热点中，富集比都在 3–4 倍，约 20–35% 的序列含有 AP-1 motif。
   - **CTCF** 在所有集合中富集比最高（5–7 倍，远端开放热点达 27 倍），但只出现在 10–20% 的序列中。
   - **ETS/NRF1/ZBTB/ZNF131 一类** 集中在启动子和 top1 极端热点：富集比只有 1.4–1.7 倍，但覆盖约一半的序列，对应 CpG 岛启动子的序列特征。
2. **层级越高，启动子特征越强：** top20 到 top5 以 AP-1 为主；到 top1（启动子占约 52–70%），ETS 和 CTCF 排到最前。
3. **控制开放程度之后：**
   - AP-1 的富集大幅减弱，但没有消失：35 个 AP-1 类 motif 中仍有 23–33 个显著，但富集比的中位数从 G 对照下的 2.5 倍降到 1.2–1.6 倍，最高排名从第 1 位降到第 16–61 位。这说明 AP-1 的富集大部分伴随开放程度本身。
   - 仍然保留的是：top5 的 CTCF 和 FOX，以及 top1 的 ETS。这些 motif 区分的是"蛋白数多"和"仅仅开放"的区域。
   - A_protein_top5 和 top10 的对照偏小，这部分结论需要谨慎看待。
4. 这些结果都是序列层面的 motif 富集，**不说明是哪个蛋白结合在这里**。另外，motif 富集和 ChIP 热点之间存在循环性：热点由 ChIP 定义，而 CTCF 和 AP-1 本身就是 ChIP-Atlas 中实验最多的靶标之一。

## 局限与下一步

- **研究覆盖偏差：** 被测得多的蛋白（如 CTCF、AP-1 家族）可能抬高其 motif 在热点中的比例。下一步可以按蛋白去掉 CTCF、AP-1 的 ChIP 实验后重新定义热点，看这两个 motif 是否仍然富集。
- **共识库的 CTCF 冗余：** 需要回到 Step 3 处理。
- **A 对照的规模：** 可以把候选池扩大到相邻层级，或改用连续的开放程度权重。

## 版本记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-10-21 | 16 个比较（G、A、S 三类对照）× 4 个 motif 库（JASPAR 和 PMA HIGH/MEDIUM/LOW），对照由 HOMER 匹配，检验用 SEA |
