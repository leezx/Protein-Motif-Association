# ChIP-Atlas 坐标唯一 BED6 范围交接

更新时间：2026-10-18 17:22 EDT
工作分支：`task_20261018_chipatlas_unique_bed6_design`  
基线：`origin/step4b-atac-footprinting`  
PR：[#6](https://github.com/leezx/Protein-Motif-Association/pull/6)，OPEN；设计-only，当前完整 HEAD 审核待请求。初始提交 `49621ade482fb8fa1b73de8392dd8d65da4c782d`，随后会推送审计同步提交并以新 SHA 送审。

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

下一步：推送本轮 PR/handoff/worklog 审计同步，复核 GitHub 当前完整 HEAD 和 diff，随后请求 GPT 对该 exact HEAD 明确 APPROVE/REQUEST_CHANGES。只有该 HEAD 获批后，才继续按批准范围执行；数据级 Argos 构建需要单独明确授权。两项目标当前完成度仍不可报为完成；本轮可测进展是目标 1 获得一份可审核的修订契约，目标 2 无进展。`HUMAN DECISION: PENDING`。
