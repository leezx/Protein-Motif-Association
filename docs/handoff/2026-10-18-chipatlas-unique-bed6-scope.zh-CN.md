# ChIP-Atlas 坐标唯一 BED6 范围交接

更新时间：2026-10-18 19:16 EDT
工作分支：`task_20261018_chipatlas_unique_bed6_design`
基线：`origin/step4b-atac-footprinting`
PR：[#6](https://github.com/leezx/Protein-Motif-Association/pull/6)，OPEN、未合并；分支当前 HEAD `3e15ab23c42a44d8139f3b4fb04038428fa3bc3c`，base `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`。GPT 对该精确完整 HEAD 给出 `APPROVE — Design-only gate`，零 blocker。批准范围只覆盖设计，不包括实现、Argos 读取、数据处理、资源预检、运行或合并。

## PI 目标

复用 Argos 已有 ChIP-Atlas human hg38 `allPeaks_light.hg38.05.bed.gz` 与 metadata，产出坐标唯一的 BED6；同一 region 可以链接多个 ChIP-seq experiments，且每个输入 peak 行都可追溯。原始与结果数据放仓库外。

## 已知状态与判断

- 原始 hg38 peaks archive 和旧 Step 4a 处理结果已在 Argos；本轮没有访问 Argos。
- 旧结果是 443,029,514 行 BED6+18，按 experiment 保留 peak，纳入 TFs and others + RNA polymerase 子集，不是最终目标。
- GPT 技术意见建议把 Histone 加入目标；排除 Input control、ATAC-Seq、DNase-seq、Bisulfite-Seq、非实验 annotation/aggregate 和未知 class。旧 reconciliation 的 `out_of_scope_class` 行数不等于 Histone 行数。
- ChIP-Atlas 将 hg38/hg19 作为不同 assembly；此契约限定为 hg38，不能宣称覆盖 hg19 或 liftover 记录。

## 提议的可审查契约

设计见 [`docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md`](../STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md) 顶部 revision section：

- 纳入 `genome=hg38` 且 antigen class 精确为 `TFs and others`、`RNA polymerase`、`Histone` 的 experiments。
- source q<1e-5 peaks 不新增过滤；只按完全相同的 `(chrom,start,end)` 去重，不合并相交区间。
- BED6 name 为 assembly/坐标规范化后的稳定 SHA-256 `region_id`；score 为支持该 region 的 distinct experiment 数、按 BED 范围封顶 1000；strand 为 `.`。
- 外部 sidecar 保存 region→experiment、多对多 linkage、逐 source peak 行 provenance、region summary、experiment metadata 和互斥 reconciliation 状态。
- 验收包括全源行 accounting、纳入 class/genome 精确 join、坐标/ID 唯一、linkage 与 source rows 无孤儿/丢失、确定排序及 bgzip/tabix 随机查询、输入/输出 hashes 与重复构建一致性。

## 本轮范围与后续门禁

这轮只写了设计提案和审计文件，没有 Argos 查询/命令、数据处理、测试、环境变更或 footprint 分析。Step 4b 的 HINT builder G2 上次在 Conda repodata 下载处 OS network timeout，尚未获准重试；没有 benchmark 结果。PR #5 仍 OPEN/unmerged，审核只覆盖 audit-only 文档更新。

### GPT 审核与实现建议（2026-10-18）

GPT 核验了 PR #6 完整 diff、PR body 和精确 SHA，结论为 `APPROVE — Design-only gate`。其非阻塞实现建议：

1. 冻结互斥 `primary_status` 优先级，并用附加 QC flags 保留并存异常。
2. 报告 global unique-region 数、三个互相重叠的 class-specific 数和七种非空 class-membership mask；七种互斥 mask 的计数之和必须等于 global 数。
3. 历史 Step 4a v1 仍是旧类别子集，不能沿用其计数作为新目标结果。
4. 采用两次 GNU external sort、三次流式扫描：坐标/experiment/source-row 排序后流式聚合；映射按 source-row 排序；重读输入并按源行次序生成完整 provenance。此方案避免全量 SQLite/内存索引，但未在 Argos 验证资源需求。

建议的 status 优先级：`MALFORMED_SOURCE_ROW`、`INVALID_COORDINATE`、`UNSUPPORTED_CHROM`、`EXPERIMENT_METADATA_MISSING_OR_AMBIGUOUS`、`OUT_OF_SCOPE_GENOME`、`OUT_OF_SCOPE_CLASS`、`INCLUDED_PAIR_FIRST`、`INCLUDED_PAIR_ADDITIONAL`。`INCLUDED_PAIR_ADDITIONAL` 仍是纳入 provenance 的行，不是排除项。实现前需把 status 和 provenance 能否随机回查的合同写清楚。这里的 8–12 GiB sort buffer / 2–4 workers 仅为初始规划建议，不是实测。

### 最新 Argos / benchmark 状态

2026-10-18 19:15 EDT 的只读检查没有发现可识别的 PMA 计算进程；最近一小时没有 PMA 日志更新。发现一个旧 `singularity help build` 命令仍存活，未对其采取操作。PR #5 仍 OPEN、未合并，HEAD `c1f9329cd395eff82d2374184c3e1f7cc674922c`；先前 G2 在 Conda repodata 网络超时，没有重试授权。四工具 benchmark 尚未产生结果。

下一验收：把 status/provenance 与 class-mask 规则并入契约，明确全源行 traceability 是逻辑回查还是随机回查；实现外排 builder 并在审查通过后做合同验证。任何 Argos 元数据读取、磁盘预检或数据处理之前，须确认当时完整 PR HEAD 的 GPT `APPROVE` 明确覆盖具体步骤。两个最终产出仍未完成；目标 1 已从未复核提案推进到设计 gate 通过、实现方案成形，但没有输出行或资源实测；目标 2 无结果。`HUMAN DECISION: PENDING`。
