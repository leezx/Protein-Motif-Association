# 公共 footprint 数据库：逐样本 footprint 计数轨道（hg38）

> **文档性质：** 内部分析结果稿（非投稿版本）
> **当前版本：** v0.1，2026-10-21
> **代码：** 分支 `task_20261021_footprint_db_tracks`，head bbc3b8a，未合并。脚本在 `scripts/04c_footprint_db/`：
> - `01_footprint_tracks.sh`：生成轨道；
> - `02_footprint_track_qc.py`：QC；
> - `03_lift_bed.sh`：liftover 并加标注。
>
> 设计文档：`docs/FOOTPRINT_DB_TRACKS_DESIGN.md`。
> **数据：**
> - 完整数据在 Argos 的 `DATA/2.PROJECTS/PMA/footprint_{vierstra2020,funk2020,neph2012,boyle2011,print2025}/`，每个目录都有 `link.md`。
> - Mac 上有 `processed/tracks_v1/` 下的全部 bigWig，MD5 已与 Argos 核对一致。
>
> **结果边界：** 这些都是已发表数据的重新整理，没有新的生物学结论。各来源的 caller 和阈值不同，所以不同来源的轨道之间只能比较分布模式，不能直接比较数值。

## 为什么做

PMA 的 footprint reference 计划“先有 footprint，再接 motif”。自建的 ATAC footprint atlas（`Footprint_atlas_pipeline.methods_result.md`）还在试运行阶段。这期间先把已发表的、带逐样本 footprint 的公共数据库整理成同一种格式，有两个用途：

- 作为外部参照和基准；
- 和 ChIP-Atlas 证据轨道并列，在 IGV 里一起看。

信号的定义与 ChIP-Atlas 轨道一致：**每个碱基上，有多少个样本在这里有 footprint。**

## Methods

**来源调研（2026-10-21）**

| 来源 | 有无逐样本 footprint | 基因组版本 | 是否使用 |
|---|---|---|---|
| Vierstra 2020 *Nature*（Altius，footprint-tools） | 有，243 个 DNase 样本，多个 FPR 阈值 | hg38 | 用 FPR 0.001（主轨道）和 0.01（宽松版） |
| Funk 2020 *Cell Rep*（ENCODE DNase/FAIRE，HINT 和 Wellington） | 有。原文的 NeMO 链接已失效，从 FILER2 镜像下载 | hg38 | 用。DNase 和 FAIRE 各做 HINT、Wellington 两套；只用比对 seed 20 那一份 |
| Neph 2012 *Nature*（UW ENCODE） | 有，41 个细胞类型，FDR 1% | hg19 | 用，liftover 到 hg38 |
| Boyle 2011 *Genome Res* | 有，7 个细胞系 | hg18 | 用，liftover 到 hg38 |
| PRINT/scPrinter 2025（Zenodo 15399859） | 没有 footprint BED，只有 6 个示例 TFBS 打分 bigWig | hg38（已核实） | 只保存原始文件 |
| footprintDB（2014 *Bioinformatics*） | 没有，它是 motif/TF 数据库 | — | 不用 |
| TOBIAS | 没有人类预计算图谱 | — | 不用 |
| GTRD | 当天网站无法访问 | — | 未核实 |

用户的取舍：
- Vierstra 只下载 footprint BED 和 consensus 文件。
- 没有逐样本数据的来源，就下载整合后的 footprint 文件，单独存放。
- 能用 hg38 就用 hg38，否则 liftover。
- liftover 过的数据必须明确标注。

**轨道构建（`01_footprint_tracks.sh`）**

1. 每个样本：取出不重复的 footprint 区间，截到染色体边界内，并在样本内部合并重叠区间。这样同一个样本在一个碱基上最多只算一次。
2. 用 `bedtools genomecov -bg` 统计每个碱基上的样本数，范围限定在 chr1–22、X、Y。
3. 输出：
   - bigWig；
   - bgzip 压缩的 bedGraph，带 tabix 索引；
   - 所有 footprint 的合并 BED（`<V>.footprints.bed.gz`）；
   - `samples.tsv`。
4. 按 ENCODE v2 黑名单切分，得到 `_noBlacklist` 和 `_blacklistOnly` 两个版本，脚本复用 `04a_chipatlas/10_mask_blacklist.py`。
5. Funk 的数据每一行是“footprint × motif 命中”，footprint 坐标取第 7–8 列。
6. Boyle 的 `Combined_GM` 是合并样本，不计入计数轨道。

**liftover（`03_lift_bed.sh`）**

- 工具：UCSC liftOver v369，默认 minMatch 0.95。Argos 的 glibc 是 2.23，新版 liftOver 跑不了，所以用这个旧版。
- chain 文件：`hg19ToHg38`、`hg18ToHg38`。
- 无法映射的 footprint 直接丢弃，另存一份备查。
- **标注规则：** liftover 产物的文件名和轨道名里都带 `liftedFrom<Build>`，旁边放一份 `LIFTOVER_NOTICE.txt`，写明源版本、chain 和映射数量。输出名里没有 `liftedFrom` 时，脚本直接拒绝运行。

**QC（`02_footprint_track_qc.py`）**

- 守恒：所有区间的“数值 × 长度”之和，等于全部 footprint 的总碱基数。
- 范围：所有数值都在 1 到样本数之间。
- bedGraph 已排序，区间互不重叠。
- 随机抽 300 个有信号的位置和 300 个零信号位置，用 tabix 重新计数，与轨道数值比对。
- 另外还做了一次内容检查：扫描完整的 bedGraph，确认值全为整数，并看值的分布；再用 pyBigWig 抽查局部最大值。

所有计算都在 Argos SGE 上完成。

## Results

**1. 8 条逐样本计数轨道全部通过 QC**

| 轨道 | 样本数 | footprints | 覆盖 | 单碱基最大值 | bw 大小 |
|---|---|---|---|---|---|
| `vierstra2020_fpr0.001`（主轨道） | 243 | 67,994,177 | 126.7 Mb | 243 | 250 MB |
| `vierstra2020_fpr0.01`（宽松版） | 243 | 159,657,310 | 295.1 Mb | 243 | 510 MB |
| `funk2020_dnase_hint` | 162 个文件（155 个实验） | 227,734,229 | 674.2 Mb | 159 | 815 MB |
| `funk2020_dnase_wellington` | 162 | 50,508,583 | 344.4 Mb | 162 | 330 MB |
| `funk2020_faire_hint` | 6 | 7,653,614 | 138.4 Mb | 6 | 59 MB |
| `funk2020_faire_wellington` | 6 | 1,548,930 | 33.0 Mb | 6 | 15 MB |
| `neph2012_fdr0.01_liftedFromHg19` | 41 | 45,085,507 | 156.6 Mb | 41 | 169 MB |
| `boyle2011_liftedFromHg18` | 7 | 1,352,143 | 21.4 Mb | 7 | 14 MB |

- 每条轨道的守恒、范围、排序检查都通过，600 个位置的 tabix 重算没有一个不一致。
- 内容检查：
  - 值全部是整数；
  - 大部分覆盖碱基只有 1–2 个样本（例如 Vierstra 0.001：值为 1 的占 51%，值 ≥10 的占 11%）；
  - 局部最大值符合样本数（例如 Vierstra 在 chr1:1.0–1.1 Mb 为 233/243）。
- 文件偏大的原因是区间太碎：几百个样本的 footprint 边界彼此错开，计数每过一个边界就会变，每段同值区间平均只有 3–7 bp。例如 Funk DNase HINT 有 1.74 亿个区间。文件大小反映的是变化次数，不是数据有误。

**2. liftover 损失很小**

| 输入 | 源 footprints | 无法映射 | 比例 |
|---|---|---|---|
| Neph 逐样本 | 45,096,726 | 4,000 | 0.009% |
| Boyle 逐样本 | 1,423,510 | 667 | 0.05% |
| Neph combined | 8,374,968 | 778 | 0.009% |
| Boyle Combined_GM | 225,799 | 112 | 0.05% |

**3. 整合 / consensus 文件单独存放，不并入计数轨道**

| 来源 | 位置 |
|---|---|
| Vierstra（原生 hg38） | `raw/2026-10-21/consensus.index/`：consensus footprints、motif 重叠、index 矩阵、motif 富集 |
| Neph | `footprint_neph2012/processed/consensus_hg38/neph2012_combined_fps.liftedFromHg19.hg38.bed.gz` |
| Boyle | `footprint_boyle2011/processed/consensus_hg38/boyle2011_Combined_GM.liftedFromHg18.hg38.bed.gz` |

**4. PRINT**
- 6 个 PBMC 示例 bigWig，MD5 与 Zenodo 一致。
- chr1 长度为 248,956,422，确认是 hg38。
- 这些是连续的 TFBS 打分，不是 footprint 调用结果，所以没有生成计数轨道。

**5. 下载**

| 来源 | 大小 | 失败数 |
|---|---|---|
| Vierstra | 7.1 GB | 0 |
| Funk | 55 GB | 0 |
| Neph | 420 MB | 0 |
| Boyle | 63 MB | 0 |

所有下载都有 MD5SUMS。

## 结论与讨论

- 现在有了 4 个来源、8 条 hg38 footprint 样本数轨道，格式与 ChIP-Atlas 证据轨道相同，可以直接放进 IGV 对照。另有 3 套整合 footprint 文件。
- 可比性有限：
  - Vierstra 用 FPR 阈值，Neph 用 FDR，Funk 用 HINT 和 Wellington 两种 caller；
  - Funk 的 HINT 覆盖约 674 Mb，是 Wellington 的 2 倍，说明 caller 本身就是很大的变量。

  因此它们适合作为“某个位点在多少独立数据里出现过 footprint”的参照，不能互相当作重复。
- Neph 和 Boyle 是 liftover 来的数据，所有文件名都带 `liftedFrom`，使用时请留意坐标转换带来的边界误差。
- 下一步：
  - 自建 ATAC footprint atlas 跑完以后，用这些轨道做外部一致性比较；
  - 再进入 footprint × motif 的关联。

## 版本记录

- v0.1（2026-10-21）：首版。包括来源调研、8 条轨道、liftover 与标注、consensus 文件、PRINT 版本核实、内容检查，以及拷贝到 Mac。
