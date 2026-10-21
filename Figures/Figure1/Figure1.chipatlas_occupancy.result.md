# Figure 1 result — ChIP-Atlas 人类蛋白占据参考：统一 BED、轻量 BED 与占据证据轨道

> **文档性质：** 内部分析结果稿，非投稿版本。
>
> **当前版本：** v0.1，2026-10-21。
>
> **对应图位：** Figure 1D「Occupancy dataset coverage」，见 `design/PMA_pseudo_figures_v0.2.md`。
>
> **覆盖范围：**
> - Step 4a 实验级占据 BED（v1）；
> - 坐标去重 BED6；
> - 每个蛋白的轻量 BED；
> - 蛋白、组蛋白、RNA 聚合酶、开放染色质的占据证据轨道；
> - 实验过滤和 ENCODE 黑名单拆分。
>
> **代码：** 分支 `task_20261020_chipatlas_light_bed`，脚本在 `scripts/04a_chipatlas/`，设计见 `docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md` §1–§12。
>
> **结果边界：** 所有轨道的数值都是跨实验汇总的 peak 证据计数，不是 reads 覆盖度，不是结合强度，也不代表同一细胞内的共同结合。

## Result overview

PMA 的 association 统计需要一个统一的 occupancy 输入。它要回答三件事：每个 peak 来自哪个实验，结合的是哪个蛋白，在什么细胞背景中、用什么抗体测得。为此，我们把 ChIP-Atlas 人类 hg38 中 MACS2 q < 1e-5 的全部 peak 整理成一套可追溯的参考，包括：

| 层级 | 内容 | 规模 |
|---|---|---|
| 实验级 BED6+18 | 转录因子和其他蛋白，加 RNA 聚合酶 | 4.43 亿行，38,795 个实验 |
| 实验级 BED6+18 | 组蛋白 | 6.28 亿行，37,481 个实验 |
| 坐标去重 BED6 | 蛋白和组蛋白合并 | 10.24 亿个区间 |
| 轻量 BED（同一蛋白跨实验合并） | 蛋白 / 组蛋白 | 7,088 万 / 1,599 万个区间 |
| 全基因组占据证据轨道 | 蛋白、组蛋白、RNA 聚合酶、ATAC-seq、DNase-seq | 每套都有 ENCODE 黑名单内外两个拆分版本 |

主要发现：

- **完全按坐标去重几乎压缩不了数据**，只去掉约 4% 的行。只有在同一蛋白内部合并重叠 peak，才能得到能在浏览器里查看的体量：蛋白缩小 6.25 倍，组蛋白缩小 39 倍。
- **最高的占据信号大多是伪信号。** 实验支持数 ≥ 10,000 的碱基中，57% 落在 ENCODE 黑名单里。
- **开放染色质数据中混有大量不合格实验。** ATAC 实验里有 30,125 个（62%）是单细胞实验，或 peak 数不到 1 万，或者不是开放染色质测序。

## 1. 实验级占据 BED：每个 peak 都能追溯到蛋白、背景和抗体

### 为什么做

ChIP-Atlas 按实验分发 peak，元数据在另一张表里，而且同一个实验 ID 可能同时有 hg19 和 hg38 两条记录。后续的 protein–motif association 需要先把 peak、蛋白身份、细胞背景和抗体信息连接起来，并且要能逐条追溯回原始实验。

### 做了什么

- 从 `allPeaks_light.hg38.05.bed.gz`（22.9 亿行）和 `experimentList.tab` 出发，为每个实验选出唯一的 hg38 元数据行。
- 把抗原名映射到 HGNC，整理细胞类型、组织和抗体字段。
- 输出 BED6+18，每行是一个 peak。“TFs and others”和“RNA polymerase”两类放在主文件；组蛋白用同一套规则单独输出。
- 坐标去重 BED6 只合并坐标完全相同的区间。它由独立脚本逐个实验对账：38,795 个 TF/Pol 实验与 v1 完全一致。

### 得到什么结果

| 文件 | 实验数 | 行数 | 核验 |
|---|---|---|---|
| 蛋白（TF 和其他 + Pol） | 38,795 | 443,029,514 | 2026-10-17 验证通过 |
| 组蛋白 | 37,481 | 627,664,680 | 构建通过 |
| 坐标去重 BED6（三类合并） | — | 1,024,044,914 | 构建器自检和独立核验都 PASS |

- 早期的一个候选构建错误地把“同一实验同时有 hg19 和 hg38 两条记录”当成元数据歧义，丢掉了 98.6% 的行。修复后的版本和 v1 逐个实验完全一致。
- 完全按坐标去重只去掉约 4% 的行：不同实验的 peak 边界几乎从不完全相同。

### 结论

实验级 BED 是 PMA 中 occupancy 证据的唯一源头，其他产物都由它派生。“完全相同坐标”不是有意义的去冗余单位；要压缩数据，必须在同一蛋白内部合并重叠区间。

对应证据：
- 设计 §1–§9：[`docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md`](../../docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md)
- 数据集说明：[`DATA/.../occupancy_chipatlas/link.md`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/link.md)（v1 BED 和坐标去重 BED6 只存放在 Argos）

## 2. 每个蛋白的轻量 BED：能直接放进 IGV 查看

### 为什么做

16.5 GB、4.43 亿行的实验级 BED 无法在基因组浏览器中直接查看。用户的需求是：每个区间只标出蛋白名，详细的实验和背景信息另存一张可按坐标查询的附表。

### 做了什么

- 在每个蛋白（靶标）内部，把重叠或首尾相接的 peak 跨实验串联合并，得到 BED6，name 列为蛋白名。
- 生成 bigBed，另附 tabix 索引的 detail 表（每个区间由哪些实验支持）、实验背景表和 QC。
- 组蛋白单独成一个文件，name 用 ChIP-Atlas 的修饰名。
- 蛋白 BED 按用户提供的类别注释拆成 8 个文件。

### 得到什么结果

| | 输入 peak | 合并后区间 | 靶标 | 压缩倍数 | QC |
|---|---|---|---|---|---|
| 蛋白 | 443,029,514 | 70,878,901 | 1,865 | 6.25 | peak 守恒，同一靶标内无重叠：PASS |
| 组蛋白 | 627,664,680 | 15,994,563 | 144 | 39.2 | PASS |

示例区间 chr4:15,966,228–16,085,729（PROM1 附近）：
- 1 kb 窗口 chr4:16,001,000–16,002,000 有 3,336 个实验、248 个蛋白；
- 前 5 个蛋白（CTCF 1,815 个实验，加上黏连蛋白各亚基）占全部实验的 73.5%。

### 结论

轻量 BED 加附表的设计既能直接可视化，又保留了完整的追溯链。同一位置“蛋白很多”往往是少数蛋白被大量重复测定的结果，所以可视化时需要同时看实验数和不同蛋白数。

对应证据：
- 示例 BED 与 detail 表：[`processed/light_v1/examples/`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/examples/)
- QC：[蛋白](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/protein/PMA_chipatlas_hg38_protein_nr.qc.json)、[组蛋白](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/histone/)
- 区间查询脚本：`scripts/04a_chipatlas/07_region_query.py`

## 3. 占据证据轨道：由 peak 推导，按蛋白类别和修饰拆分

### 为什么做

在全基因组尺度上看“哪里有多少证据”，需要连续的信号轨道。ChIP-Atlas 的 peak 来自不同实验，不能当作 reads 覆盖度相加。因此我们定义了基于 peak 的计数轨道，并为每种轨道写出数学定义和恒等式 QC。

### 做了什么

对每条染色体做流式扫描，维护 peak 终点的堆，逐碱基统计以下计数（定义见设计 §11–§12）。

**蛋白轨道**
- E：实验数；
- P：不同蛋白数；
- TF：序列特异 TF 数；
- CAP（Chromatin-Associated Protein）：组蛋白 writer/eraser、reader、重塑因子、结构蛋白/黏连蛋白的数目，CTCF 计入 CAP。

**组蛋白轨道**
- H：实验数；
- M：不同修饰数；
- 6 个核心修饰各一条：H3K27ac、H3K4me3、H3K4me1、H3K27me3、H3K9me3、H3K36me3。它们分属 4 个功能组，不相加。

**RNA 聚合酶轨道**
- Pol II 实验数；
- Pol III 实验数。

**开放染色质轨道**
- ATAC-seq：实验数、细胞类型数；
- DNase-seq：实验数、细胞类型数。

**QC**
- 在每个断点检查恒等式，例如 P = Σ 各类别的蛋白数、TF ≤ P、P ≤ E；
- 另用 tabix 独立复算 300 个随机位点。

### 得到什么结果

| 轨道集 | 覆盖碱基 | 最大值 | QC |
|---|---|---|---|
| 蛋白 | 20.1 亿 bp | E 38,092；P 1,861；TF 1,006；CAP 208 | 恒等式 0 违例；300 个位点 0 不一致 |
| 组蛋白（已过滤） | 22.4 亿 bp | H 34,006；M 88；H3K27ac 11,390 | PASS |
| RNA 聚合酶 | 4.7 亿 bp | Pol II 4,214；Pol III 96 | PASS |
| ATAC-seq（已过滤） | 11.5 亿 bp | 18,578 个实验；977 种细胞类型 | PASS |
| DNase-seq（已过滤） | 6.8 亿 bp | 2,082 个实验；315 种细胞类型 | PASS |

### 结论

这套轨道可以在全基因组尺度上展示“证据有多少、来自多少个不同蛋白”。但数值主要反映测定次数，热点处往往由少数被大量测定的蛋白主导。v1 有意不做按蛋白归一化的支持度，也不做按细胞背景分层的轨道，这两项留到后续版本。

对应证据：
- 各轨道 QC：[`processed/light_v1/tracks*/qc.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/)
- IGV session（原始、noBlacklist、blacklistOnly 三套）：[`processed/light_v1/*.igv_session.xml`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/)

## 4. 实验过滤：开放染色质数据中约六成实验不合格

### 为什么做

ATAC-seq 和 DNase-seq 中混有单细胞实验。单细胞 peak 不可靠，会污染汇总结果。还有一部分实验 peak 数过少，或者根本不是开放染色质测序（例如 KAS-seq、NOMe-seq，以及只测 RNA 的多组学样本）。

### 做了什么

逐个实验判断并给出原因，输出过滤表 `PMA_chipatlas_hg38_experiment_filter.tsv`。规则如下：

| 原因 | 判定 |
|---|---|
| `single_cell` | 标题中含单细胞相关关键词，例如 10x、scATAC、single nuclei、iCELL8 |
| `non_accessibility` | 标题核心部分表明不是开放染色质测序 |
| `low_peaks` | peak 数 < 10,000 |

关键词都按词边界匹配，避免“placenta”被识别为 PLAC、“genome”被识别为 NOMe 之类的误判。组蛋白只排除单细胞实验。蛋白 ChIP 不过滤。

### 得到什么结果

| 类别 | 保留 | 排除 | 主要原因 |
|---|---|---|---|
| ATAC-seq | 18,651 | 30,125 | peak < 1 万：29,892；单细胞：4,440；非开放染色质：67（一个实验可有多个原因） |
| DNase-seq | 2,086 | 2,518 | peak < 1 万：2,517 |
| 组蛋白 | 37,762 | 2,682 | 全部是 iCELL8 单细胞 |

ATAC 排除了 62% 的实验，但保留实验的 peak 占全部 ATAC peak 的 92.1%。DNase 的这一比例为 99.1%。被排除的实验大多 peak 很少，对汇总信号的贡献本来就小。

### 结论

开放染色质轨道必须先按实验过滤；否则实验数这一指标会被大量低质量实验抬高。过滤只影响 ATAC、DNase 和组蛋白；蛋白 ChIP 的实验数和 peak 都没有改动。

对应证据：
- 过滤表：[`processed/light_v1/PMA_chipatlas_hg38_experiment_filter.tsv`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/PMA_chipatlas_hg38_experiment_filter.tsv)
- 规则：`scripts/04a_chipatlas/11_experiment_filter.py`

## 5. ENCODE 黑名单：最高的占据信号大多是伪信号

### 为什么做

在蛋白轨道中，实验支持数最高的区域集中在已知的高信号伪区。最大值位于 chr1:125.17 Mb 的 High Signal Region。如果不处理，这些区域会主导所有“热点”的解读。

### 做了什么

每套轨道都在 ENCODE hg38 v2 黑名单的边界上按碱基切开，得到两个版本：
- noBlacklist：黑名单外的部分；
- blacklistOnly：黑名单内的部分，单独发布，供核查。

QC 检查两部分的信号相加等于原始信号，并且两部分互不越界。

### 得到什么结果

- 蛋白轨道中，实验支持数 E ≥ 10,000 的碱基有 57% 在黑名单内。
- 黑名单只占基因组的极小一部分，但各轨道有不少信号落在其中：

| 轨道 | 黑名单内信号占比 |
|---|---|
| 蛋白 E / P / TF / CAP | 5.2–5.5% |
| 组蛋白 H3K27ac / H3K4me1 / H3K4me3 | 2.3–2.7% |
| 组蛋白 H3K27me3 | 9.5% |
| 组蛋白 H3K36me3 | 11.6% |
| 组蛋白 H3K9me3 | 19.1% |
| Pol II | 4.2% |
| Pol III | 23.0% |
| ATAC / DNase | 2.4–2.5% |

- 所有拆分的守恒 QC 都是 PASS。

### 结论

做任何热点分析或跨蛋白比较时，都应默认使用 noBlacklist 版本。H3K9me3 和 Pol III 在黑名单内的信号比例很高，这和异染色质、tRNA 等重复区域的特性一致。这两者的黑名单内信号既可能是伪信号，也可能有真实成分，因此单独发布 blacklistOnly 版本供核查，不直接删除。

对应证据：
- 拆分 QC：[`processed/light_v1/tracks*_noBlacklist/mask_qc.json`](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/)
- 脚本：`scripts/04a_chipatlas/10_mask_blacklist.py`

## 讨论

1. **这部分是资源构建，不是生物学发现。** 它的价值在于统一和可追溯：任何一个位点的证据都能追溯到实验、蛋白、细胞和抗体。后续 Figure 2 的统计校准，以及 Figure 3 的共占据分析（`Figures/Figure3/Figure3.dbp_cooccupancy.result.md`），都以这里的实验级 BED 为输入。
2. **计数轨道反映测定次数。** CTCF 一个蛋白就有 2,000 多个实验，热点处的“证据多”常常只是某些蛋白被大量测定。按蛋白归一化的支持度 S(x) 是 v1 有意没做的部分，应作为下一版的优先项。
3. **研究来源是一个隐含的混杂。** Figure 3 的验证发现，单个研究就可能主导某个蛋白的占据集合（例如 SRP158854 对 ESR1 的影响），而目前的轨道和 BED 没有体现研究来源。下一版应考虑在附表中加入研究编号，并给出每个蛋白的研究影响度。
4. **尚待用户决定的问题：**
   - CENPB 和 HINFP 现在在组蛋白文件中，是否移到蛋白文件；
   - 9 个归为 TF、但不在 Lambert 2018 名单中的基因的复核；
   - P 轨道是否只统计 HGNC 基因，目前也计入了 Epitope_tags、GFP 等标签。
