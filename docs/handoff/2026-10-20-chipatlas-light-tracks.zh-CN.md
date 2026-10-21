# ChIP-Atlas 统一 BED、轻量 BED 与占据证据轨道：交接

更新时间：2026-10-21 03:30 EDT（Claude）
代码分支：`task_20261020_chipatlas_light_bed`（基于 `step4a-chipatlas-occupancy`，已推送，**未合并**）
设计文档：`docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md` §10（轻量 BED）、§11（证据轨道）、§12（Pol、开放染色质、实验过滤）、§13–§15（三层聚类）、§16（v1.1 验证门）

## 1. 目标（PI 方向）

把 ChIP-Atlas 人类 hg38 的 ChIP-seq 整理成一套统一、可追溯的参考：
1. 实验级 BED，记录每个 peak 的蛋白、组织、细胞和抗体；
2. 能直接在 IGV 里看的轻量 BED；
3. 由 peak 推导出的全基因组占据证据轨道（bigWig）。

蛋白和组蛋白分开。轨道统一称为 “ChIP-Atlas Protein Occupancy Evidence Tracks”：数值是跨实验的 peak 证据计数，不是 reads 覆盖度，不是结合强度，也不表示在同一个细胞里共同结合。

## 2. 已完成的数据产物

所有数据在 Argos 的 `/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/` 下。`processed/light_v1/` 的大部分已拷到本地 `$BIO_DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/`，并核对过 sha256。

| 产物 | 位置（`processed/` 下） | 规模 | 状态 |
|---|---|---|---|
| 实验级 BED6+18：蛋白（TF 和 Pol） | `v1/` | 4.43 亿行，38,795 个实验 | 2026-10-17 已验证 |
| 实验级 BED6+18：组蛋白（同一套 Step 4a 规则，`PMA_OCC_CLASSES=Histone`） | `histone_v1/` | 6.28 亿行，37,481 个实验 | 完成（只在 Argos） |
| 坐标去重 BED6（蛋白和组蛋白，Codex PR #7 的构建器，由 Claude 接手） | `unique_bed6_v1_d84d98b/` | 10.24 亿个区域 | 构建器自检和独立核验都 **PASS** |
| 轻量蛋白 BED（同一蛋白的重叠 peak 跨实验合并） | `light_v1/protein/` | 7,088 万个区域，1,865 个靶标，`.bb` 780 MB | PASS，已拷回本地 |
| 轻量组蛋白 BED（name 用 ChIP-Atlas 修饰名） | `light_v1/histone/` | 1,599 万个区域，144 个标签，`.bb` 161 MB | PASS，已拷回本地 |
| 蛋白 BED 按类别拆分（8 类） | `light_v1/protein_by_class/` | 合计 7,088 万行 | PASS，已拷回本地 |
| 蛋白证据轨道：experiments / proteins / tf / cap | `light_v1/tracks/` | 覆盖 20.1 亿 bp | 恒等式 QC 和 300 个位点复算都 PASS，已拷回本地 |
| 组蛋白证据轨道：experiments / modifications / 6 个核心修饰（已按实验过滤表排除单细胞实验） | `light_v1/tracks_histone/` | 37,762 个实验 | PASS，已拷回本地 |
| RNA 聚合酶轨道：rnapol2 / rnapol3 | `light_v1/tracks_rnapol/` | — | PASS，已拷回本地 |
| 开放染色质轨道：ATAC、DNase 的 experiments / celltypes（已过滤） | `light_v1/tracks_atac/`、`tracks_dnase/` | ATAC 18,651 个实验，DNase 2,086 个 | PASS，已拷回本地 |
| 实验过滤表（单细胞、非开放染色质测序、peak 数 < 1 万） | `light_v1/PMA_chipatlas_hg38_experiment_filter.tsv` | ATAC、DNase、组蛋白 | 已拷回本地 |
| 黑名单拆分版：上述所有轨道的 `*_noBlacklist`、`*_blacklistOnly` | `light_v1/tracks*_{noBlacklist,blacklistOnly}/` | — | 全部 PASS，已拷回本地（每个目录有 `SHA256SUMS`） |
| 过滤前的旧版 DNase / 组蛋白轨道 | 本地 `light_v1/preFilter/`，Argos `light_v1/preFilter/` | — | 保留备查，不再使用 |
| 示例区间 chr4:15,966,228–16,085,729 | 本地 `light_v1/examples/` | BED 文本和轨道 | 完成 |
| IGV session（原始 / noBlacklist / blacklistOnly 三套） | 本地 `light_v1/*.igv_session.xml` | 相对路径 | 等数据拷全后才能打开 |

注释与清单（本地 `light_v1/`，Argos 上也有一份）：

| 文件 | 内容 |
|---|---|
| `PMA_chipatlas_hg38_protein_class_annotation.csv` | 用户提供的 1,819 个基因分类，**不改** |
| `..._protein_class_annotation.v1_1.csv` | 修订版，轨道和拆分都用这一版：168 个 `conservative_unresolved` 的 Lambert 2018 TF 改为 Sequence-specific TF；新增 `original_class` 和 `functional_tags` 两列；9 个归为 TF、但不在 Lambert 名单里的基因标记为待人工复核 |
| `..._protein_class_qc.tsv` | 用户分类与 Lambert 名单不一致的基因（分类修订前生成） |
| `..._histone_label_annotation.tsv` | 144 个标签分 4 类（规则在 `08_histone_labels.py`）：修饰 89、变体/本体 31、泛修饰/含义不明 22、非组蛋白 2 |
| `..._protein_genes.txt`、`..._protein_targets.tsv`、`..._histone_marks.tsv` | 蛋白基因清单、靶标表、组蛋白标签清单 |

## 3. 怎么做的（代码在 `scripts/04a_chipatlas/`）

| 脚本 | 作用 |
|---|---|
| `01_experiments.py`（加了 `PMA_OCC_CLASSES`）+ `02_peaks.py` | 实验级 BED6+18；组蛋白用 `PMA_OCC_CLASSES=Histone` |
| `04_light_bed.py` + `run_light.sh protein\|histone` | 每个靶标内部把重叠或首尾相接的 peak 串联合并，产出 BED6、bigBed、detail 附表、实验附表、QC 和 MANIFEST；组蛋白加 `PMA_LIGHT_TARGET=antigen` |
| `05_occupancy_tracks.py` + `run_tracks.sh [N] protein\|histone` | 流式扫描（每条染色体维护一个 peak 终点堆），逐碱基统计不同实验数或不同标签数；每个断点都做恒等式 QC，另外用 tabix 独立复算 300 个位点 |
| `06_split_by_class.py` | 轻量蛋白 BED 按类别拆分 |
| `07_region_query.py chr:s-e [prefix]` | 输入区间，输出 蛋白 → 实验 → 细胞类型，并给出前 5 个蛋白的实验占比 |
| `08_histone_labels.py` | 组蛋白标签分类（规则固定、可复现） |
| `09_igv_session.py out.xml [locus] [variant]` | IGV session：每条轨道独立 y 轴，配色固定 |
| `10_mask_blacklist.py` + `run_tracks.sh 2 mask_protein\|mask_histone` | 在 ENCODE v2 黑名单边界上按碱基切开，分成 noBlacklist 和 blacklistOnly 两份；守恒 QC |
| `05_occupancy_tracks.py` 的 `pol`、`access` 模式 + `run_tracks.sh [N] pol\|atac\|dnase\|filter\|mask_<kind>` | RNA 聚合酶轨道和 ATAC/DNase 开放染色质轨道；`PMA_EXCLUDE_TSV` 按过滤表跳过实验 |
| `11_experiment_filter.py` | 生成实验过滤表：单细胞、非开放染色质测序（按标题判断）、peak 数 < 1 万 |
| `12`–`14`、`16`–`18` | 三层聚类、v1.1 验证、单对留一诊断（见 §4） |
| `verify_unique_bed6.py`（分支 `task_20261019_bed6_independent_verify`） | 坐标去重 BED6 的独立核验：结构检查，并与 v1 逐个实验对账 |

轨道的数学定义、QC 恒等式和组蛋白统计口径都写在设计文档 §11。要点：
- **蛋白：** E 为实验数，P 为不同蛋白标签数，TF 为 Sequence-specific TF 数，CAP（Chromatin-Associated Protein）为 writer/eraser、reader、remodeler、architectural 四类的数目。CTCF 计入 CAP。
- **组蛋白：** 只统计已确认的修饰。H 为实验数，M 为不同修饰数，H_m 为单个修饰的实验数。6 个核心修饰分 4 个功能组，不相加。

Argos 运行方式：
- **不要在登录节点（argos-qsub1）运行任何任务。** 2026-10-20 用户明确要求，此前用 nohup 在登录节点跑的做法作废。
- Argos 用 SGE：先执行 `set +u; source /opt/sge/default/common/settings.sh`，再用 `qsub -q all.q -pe smp 8 -l h_vmem=48G` 提交。Argos 的 h_vmem 实际按整个作业的总 vmem 执行，不是每核；用户要求按上限申请（48G，低于 50G 的上限）。有依赖的步骤用 `-hold_jid`。作业里要设 `OPENBLAS_NUM_THREADS=$NSLOTS`（OMP、MKL 同样设置）。
- 2026-10-20 晚起的作业脚本和日志都在 `/home/zz950/PMA_fetch/claude_sge_20261020/`，查状态用 `qstat -u zz950` 和 `*.status`。
- 代码先 clone 固定的 commit 到 `/home/zz950/PMA_fetch/claude_tracks_<commit>/` 再运行。
- 日志和状态文件放在 `/home/zz950/PMA_fetch/claude_light_logs/`。

## 4. 三层聚类与 v1.1 验证门（2026-10-20 晚 – 10-21）

| 内容 | 位置（Argos 和本地 `result/` 下） | 状态 |
|---|---|---|
| 三层聚类 v1（蛋白共占据、实验、区域 20 类） | `cooccupancy_v1/{all,K_562,Hep_G2}`、`experiment_clustering_v1`、`region_classes_v1` | 完成；GPT 审阅为 REVISE |
| v1 报告 | `docs/reports/STEP4A_CHIPATLAS_CLUSTERING_REPORT_2026-10-20.zh-CN.md` | 已送 GPT |
| v1.1 验证门（研究来源、广度匹配 + FDR、同蛋白集合比较、留一研究、实验混杂敏感性） | `validation_v1_1/` | 完成，本地 sha256 已核对 |
| v1.1 审计报告 | `docs/reports/STEP4A_CHIPATLAS_CLUSTERING_V1_1_AUDIT_2026-10-21.zh-CN.md` | 待用户决定是否送 GPT |

脚本：`12_cooccupancy.py`、`13_experiment_clustering.py`、`14_region_classes.py`、`16_cooccupancy_validation.py`、`17_experiment_sensitivity.py`、`18_pair_loso_diagnostic.py`。作业脚本和日志在 Argos 的 `/home/zz950/PMA_fetch/claude_sge_20261020/`。

**接着做：**
1. 用户决定是否把 v1.1 审计报告送到 PMA 项目的 GPT 对话“聚类分析意义”。
2. 不经用户批准不开始：L2（bin/阈值敏感性、区域类稳定性、Complex Portal 审核）、新模块提名、SRP158854 的处理、分支合并。

## 5. 关键发现

- **v1.1 审计（详见报告 §0）：** 复合物找回保留（AUROC 0.81，CI 0.77–0.85；FDR ≤ 0.05 有 170/373）。Hep G2 内部按蛋白的结构和 CTCF 跨细胞类型的差异，在控制同研究和同深度后消失（推翻）。未收录候选对只有 63/300 通过跨研究加留一检验。
- **SRP158854：** 这一个研究的 58 个 ESR1 实验贡献了 ESR1 一半的占据区间，造成 CTCF–ESR1 的假共占据。

- **定义问题：** 坐标完全相同才去重，只去掉了约 4% 的行。所以浏览用的是“同一蛋白重叠 peak 合并”的轻量版：蛋白缩小约 6.25 倍，组蛋白缩小约 39 倍。
- **旧候选为什么错：** Codex 的旧候选 a3c0c68 把同时有 hg19 和 hg38 记录的实验 ID 当成“元数据歧义”，丢掉了 98.6% 的行。修复后的 d84d98b 和 v1 逐个实验完全一致。
- **CTCF 热点：** chr4:16,001,000–16,002,000（PROM1 附近）有 3,336 个实验、248 个蛋白，但前 5 个蛋白（CTCF 1,815 个实验，加上黏连蛋白）占了 73.5%。
- **伪信号：** 实验支持数 E ≥ 10,000 的碱基中，57% 在 ENCODE 黑名单里。最大值在 chr1:125.17 Mb 的 High Signal Region。这是拆出 noBlacklist 和 blacklistOnly 两套的原因。

## 6. 待决定与 v1 不做的事

**需要用户决定：**
- CENPB、HINFP 要不要放进蛋白文件。它们现在在组蛋白轻量 BED 里，但组蛋白轨道已经把它们排除了。
- 9 个待复核的 TF：ZFP36、NR0B2、BCL3、SMAD2 等。
- `proteins` 轨道目前把 `Epitope_tags`、`GFP` 这类非基因标签也计入；是否改成只算 HGNC 基因。
- 两个分支是否合并（每个 PR 都要用户单独确认）。

**v1 不做（GPT 审查建议冻结范围）：**
- 按蛋白归一化的支持度 S(x)，以及组蛋白的 R_m；
- 按细胞背景分层的轨道；
- 热点聚类；
- 更多组蛋白修饰轨道；
- 与 ChIP-Atlas / ReMap 的功能对照。这一项是 P1，属于文献和资源调研，尚未开始。
