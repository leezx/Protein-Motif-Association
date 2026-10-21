# Worklog — Protein-Motif-Association

Chronological log, newest entry at the bottom. Entry shape and rules:
see `PR/_TEMPLATE/WORKLOG_TEMPLATE.md`.

## Progress tracker

| Step | Status | PR | Notes |
|---|---|---|---|
| 0. Scope freeze (v0.2) + repo init | closed | — | design/PMA_pseudo_figures_v0.2.md |
| 1. Motif reference pilot (Codebook vs JASPAR) | merged | #1 | docs/STEP1_MOTIF_PILOT_RESULTS.md |
| 2. Multi-source motif import + QC + calibration benchmark | merged (0318026, 2026-10-16) | #2 (draft) | docs/STEP2_MOTIF_IMPORT_RESULTS.md; §8 fallback (no curator), v0.1 stays operational |
| 2b. Raw layer v0.2.1 (+840 HOCOMOCO INVITRO/INVIVO) | merged (a19666f, 2026-10-16) | #3 | docs/STEP2_MOTIF_IMPORT_RESULTS.md §3; design §12 |
| 3. Motif clustering + CORE/EXTENDED | not started | — | |
| 4. Motif reference QC + freeze v0.1 (gates G1–G4) | not started | — | |
| 5. Statistical Framework v0.1 design | not started | — | core association risk |

Weights against the 100 % definition in the charter: motif reference
(steps 1–4) 25 %; occupancy reference 20 %; association statistics
25 %; evidence grading + replication 15 %; Fig. 1/2 + release 15 %.

Overall: `19% → 20% (+1%)`: completeness check closed the HOCOMOCO
sub-collection gap; raw layer v0.2.1 (30,781 records, 1,771 TFs).
Engineering and calibration progress only; no association result exists
yet. Blocker for Step 3: compute location for the all-vs-all
(~30k × 30k) TOMTOM. Curator labels remain optional (v0.2 rule not
issued).

---

## 2026-10-14 — Step 0: scope freeze + repo init

**What**: Initialized the git repo and public GitHub repo. Instantiated
the charter, README, Worklog and .gitignore from `PR/_TEMPLATE`.

**Why**: v0.2 design froze PMA as a protein–motif association reference
(not a recruitment-mechanism project), with two core figures.

**Next**: PMA Statistical Framework v0.1 design.

## 2026-10-14 — Step 1: motif reference pilot (branch step1-motif-pilot, PR pending)

**What**: Imported Codebook 2026 (1,685 representative PWMs, 1,421 TFs) and
JASPAR 2026 CORE vertebrates non-redundant (1,019 motifs) into
`DATA/2.PROJECTS/PMA/motif_reference/`. Ran TOMTOM (MEME 5.5.9) to answer
the Codebook-first pilot questions from `design/motif_resources.md`.

**Why**: the plan says to check how much Codebook already covers before
integrating all five sources.

**How**: per-query BH q < 0.01 on TOMTOM p-values, with overlap ≥ 60 %
of the shorter motif. Mid-step amendment, made before any result was
read: TOMTOM's own q-values shift with query order because of its
randomised π₀ estimate.

**Real findings**:
- TF coverage is near-complete: 759 of 762 JASPAR human TFs are in Codebook.
- Motif coverage is partial: 66 % of JASPAR human motifs match a same-TF
  Codebook PWM under the primary criterion. 105 have no match even at
  q < 0.05: 69 are ≤ 10 bp (power-limited), 18 are composites and 18 are
  longer single-protein motifs.
- The fixed q-threshold is length-biased: 27 % of ≤ 8 bp motifs are
  missed versus 12 % of > 15 bp.
- Codebook Table-10 clusters have a coarse tail (one cluster of 225
  PWMs), and 13 % of TOMTOM similarity edges cross clusters. PMA will
  build its own clusters and use Codebook as a benchmark.
- 4 Codebook PWMs contain all-zero spacer rows, set to uniform.

**Review**: ChatGPT (RA-Xiaolu / PMA项目), round 1: REQUEST CHANGES, 4
merge conditions, all verified as valid:
- objective labels instead of paralog/unrelated;
- cutoff-dependent wording instead of "absent";
- universe assertions and BH tests;
- Q3 framed as an agreement check between similarity definitions.

All were fixed. The 105 split, prompted by the review, overturned my
earlier characterisation: most of the 105 are short motifs.

## 2026-10-15 — Step 2: multi-source import, QC, calibration benchmark (PR #2)

**What**: Built raw layer v0.2 (`processed/v0.2_raw_layer/`): Codebook,
JASPAR CORE + UNVALIDATED, HOCOMOCO v14, CisBP 3.10, Factorbook ChIP-seq
and Factorbook HT-SELEX (downloaded manually; TF/ligand/batch from ENA
run reports). 29,941 records, 28,938 matrices, 1,771 HGNC TFs. Ran the
§8.1 benchmark: 1,740 queries × 28,938 targets.

**Why**: Step 3 clustering needs every source in one provenance-aware
layer, and a description of how the v0.1 match rule behaves.

**Real findings**:
- v0.1 links 71 % of P-provisional (same TF, independent sources) and
  4.8 % of N-challenge pairs. Both weaknesses sit in ≤ 8 bp motifs
  (56 % and 15 %); from 9 bp up, N-challenge ≤ 6 %.
- 21 of the 24 N-challenge links are plausible shared specificities
  (E-boxes, TALE/MyoD sites, MGA T-box, SKOR–TAATTA). The N-challenge
  rate is therefore not an FPR.
- The SELEX key makes 416 HOCOMOCO–Factorbook SELEX pairs one
  experiment. CisBP/Codebook copies of Yin 2017 cannot be linked.
- No curator: §8 fallback, `statistical_match_v0.2` not issued.

**Repro**: rerun of `run_import.sh` after TOMTOM gave identical md5s;
9 tests pass. Bug fixed in `05_benchmark_analysis.py` before any output
was written (source-pair labels were built from the full table).

**Review**: ChatGPT results review round 1 (14c5215): REQUEST CHANGES, 3
merge conditions, each verified in the code and fixed in b091c88:
- F1 (P1): P-provisional excluded only *known* shared experiments.
  Per-pair `independence_status` gives 36/500 confirmed distinct (all
  Factorbook SELEX vs HOCOMOCO, 0.83); 464 unresolved. Unresolved
  same-publication pairs link more than different-publication pairs
  (0.76 vs 0.60).
- F2/F3: N-challenge and CI wording narrowed to the sampled benchmark.
- F4: query-set and row-count assertions.

Round 2 (b091c88): APPROVE. Non-blocking: F8 CIs stay descriptive; F9
Step 3 must not treat v0.1 as a calibrated equivalence classifier (check
short motifs, composites, large clusters and threshold sensitivity).

**Next**: PR #2 merged 2026-10-16 (0318026) on user confirmation;
Step 3 compute location. Unresolved pairs must not count as independent
replication in later evidence grading.

## 2026-10-16 — Step 2b: completeness check + raw layer v0.2.1 (branch step2b-hocomoco-subcollections)

**What**: Checked v0.2 against design §2. Only gap: HOCOMOCO H14INVITRO/
H14INVIVO were never imported. Added the 840 matrices not identical to an
H14CORE matrix as `processed/v0.2.1_raw_layer/` (design §12). HOCOMOCO v13
(user download) assessed and archived only: refits of v14, no new TFs.
TF coverage vs Lambert 2018: 1,536/1,639 with a motif; the 103 without are
98 Lambert "No motif" + 5 renamed genes that are covered.

**Checks**: v0.2 rebuild reproduces checksums; v0.2.1 rerun identical;
no existing record changed except duplicate flags.

**Review** (ChatGPT PMA conversation): round 1 REQUEST CHANGES. F10:
merge on identical matrix alone could merge across TFs/experiments
(verified: 0 such of 2,334; rule now also requires same TF, origin,
assay). F11: merged entries lost provenance (fix: per-entry
`PMA_hocomoco_collection_memberships.tsv`, 4,769 rows; 817 keep their own
collection quality). F12–F15 docs/tests. Round 2 (07de20e): APPROVE.
For Step 3: F16 read collection-specific quality from the membership
table; F17 experiment count is not cluster size.

**Next**: PR #3 merged 2026-10-16 (a19666f) on user confirmation; Step 3 design on v0.2.1.


## 2026-10-21 EDT — 热点区域、热点 motif 富集、公共 footprint 数据库轨道（会话总结）

**做了什么**

1. **热点分布与阈值**
   - 分支 `task_20261020_chipatlas_light_bed`，脚本 `23`–`25`。
   - 全基因组切成 6,176,550 个 500 bp 区间，每个区间统计非组蛋白蛋白数、ATAC 实验数、DNase 实验数，并画出分布图。
   - 按分位数分 4 层，层层嵌套：top20、top10、top5、top1（阈值是事先定好的分位数，不是显著性）。
2. **热点 BED（v2）**
   - 两类热点：蛋白结合热点，以及开放染色质热点（ATAC 层与 DNase 层取交集）。
   - 4 层 × 2 类，共 8 个 BED，放在 `occupancy_chipatlas/result/hotspot_regions_v2/`。
   - 已复制到 `Figures/Tables/`。
   - 结果文档：`Figures/Figure1/Figure1.hotspot_regions.result.md` v0.2。
3. **热点 motif 富集**
   - 脚本 `26`–`28`，结果在 `result/hotspot_motif_v1/`。
   - 对照序列：HOMER 5.1 `homer2 bg` 生成 GC/k-mer 匹配的对照，分三种：G（全基因组）、A（再匹配开放程度）、S（按启动子和远端分层）。
   - 富集：SEA 分别跑 4 个 motif 库：JASPAR 2026，以及 PMA 的 HIGH、MEDIUM、LOW 三层。
   - 主要发现：
     - 远端区域以 AP-1 为主；
     - CTCF 的富集倍数最高；
     - 启动子区域和 top1 以 ETS/NRF1/ZBTB 为主。
   - 显著性普遍饱和，所以按富集倍数和排名解读。
   - 结果文档：`Figure1.hotspot_motif.result.md` v0.1。
4. **公共 footprint 数据库**
   - 分支 `task_20261021_footprint_db_tracks`，head bbc3b8a，脚本 `scripts/04c_footprint_db/`。
   - 调研了 8 个来源，其中 Vierstra 2020、Funk 2020、Neph 2012（hg19→hg38）、Boyle 2011（hg18→hg38）有逐样本数据。
   - 生成 8 条样本数 bigWig，全部通过 QC；整合文件单独存放；PRINT 只保存原始文件（hg38）。
   - liftover 产物都带 `liftedFrom<Build>` 和 `LIFTOVER_NOTICE.txt`。
   - bigWig 已拷回 Mac，MD5 一致。
   - 结果文档：`Figures/Footprint_atlas/Footprint_public_db_tracks.result.md` v0.1。
5. **登记**
   - 5 个 footprint 数据集各写了 `link.md`。
   - 更新了 `DATA/dataset.index.md`、`DATA/2.PROJECTS/PMA/README.md`、工作区 `HANDOFF.md`、`SOFTWARES/TOOL_INDEX.md`（Argos liftOver v369）。

**遇到的问题**
- `homer2 bg -bgr` 对全基因组运行时内存爆掉，改为先抽样候选区间。
- HOMER 会把每个 GC 区间都裁到最小区间的数量，导致对照序列太少。改为只排除同一层的区间，并对对照偏少的比较标记 SMALL_CONTROL。
- SEA 太慢：把目标序列上限设为 1 万条，motif 库拆成 8 份并行，q 值在整个库上重新计算。
- Argos 环境：glibc 太旧，改用 liftOver v369；计算节点访问 UCSC 的 curl TLS 失败、conda 源连不上；scp 失败，改用 `tar | ssh`。

**进度**
- 项目整体估算：`20% → 36%（+16%，相对 2026-10-16 Step 2b 的记录）`。按章程权重估算：

  | 部分 | 权重 | 估算完成度 | 说明 |
  |---|---|---|---|
  | motif reference | 25% | 约 18% | Step 1–3b 已完成，尚未冻结 |
  | occupancy / footprint reference | 20% | 约 14% | ChIP-Atlas v1、light BED、轨道、热点、公共 footprint 轨道已完成；自建 ATAC footprint atlas 仍在试运行 |
  | 关联统计 | 25% | 约 2% | 热点 motif 富集属于探索性分析，统计框架还没开始 |
  | 证据分级 | 15% | 0 | 未开始 |
  | 图与发布 | 15% | 约 2% | 结果文档已起草 |

- 这些数字说明工程和数据资产在推进，不代表蛋白–motif 关联结论已经成立。

**卡点**
- 各 PMA 分支都没有合并，每个 PR 需要用户分别确认：
  - `task_20261020_chipatlas_light_bed`
  - `task_20261019_bed6_independent_verify`
  - `task_20261021_repo_data_links`
  - `task_20261021_footprint_db_tracks`
- GPT 审阅尚未发送（需要用户批准）。

**下一步**
1. 用户决定是否合并各分支，以及是否送 GPT 审阅。
2. 在 `task_20261021_repo_data_links` 分支的仓库 `LINKS.md` 里补上 footprint 条目。
3. 处理 Step 3 的 CTCF consensus 冗余（CTCF 被拆成约 10 个 LOW 层级的 cluster）。
4. 自建 ATAC footprint atlas 跑完后，与公共 footprint 轨道做一致性比较，然后做 footprint × motif。
