# Gate A result — Context-aware co-occupancy improves recovery of curated co-complex partners in a matched subset of TFs, concentrated in bZIP（CONDITIONAL，已关闭）

> **文档性质：** 内部分析结果稿，非投稿版本。
> **版本：** v0.2，2026-10-30。v0.2 加入 GPT 终审（`UDE/design/paper_ideas_v2_gateA_y3_review1.md`）：裁定 CONDITIONAL，Gate A 关闭归档，不再追加计算。
> **设计：** `UDE/design/paper_ideas_v2_plan_v0.2.md` + `_impl.md` + `paper_ideas_v2_preflight_fix.md`（预检 review2 PASS）。BioPlex 因无法核实 bait/prey 检测资格只作富集支持，GO 判据 3 预先记为 NOT EVALUABLE，所以本轮判定上限为 CONDITIONAL。
> **代码：** 分支 `task_20261030_paper_ideas_v2`，`scripts/06_gates/60, 61, 67, 69`；正式运行用的 `61_gateA_benchmark.R` md5 `1641c1aa…`。
> **结果目录：** `DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateA_cooccupancy_benchmark_v1/`。
> **结果边界：** 标签是 Complex Portal 同复合物关系；共占据是跨实验汇总的 peak 关联，不是同一细胞内的共同结合，也不是物理复合物。未标注的蛋白对不是确认的阴性。

![Gate A](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateA_cooccupancy_benchmark_v1/figures/GateA_cooccupancy_benchmark.png)

图文件：[PNG](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateA_cooccupancy_benchmark_v1/figures/GateA_cooccupancy_benchmark.png) / [PDF](../../../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/gateA_cooccupancy_benchmark_v1/figures/GateA_cooccupancy_benchmark.pdf)

## Result overview

**正式判定：CONDITIONAL（GPT 裁定，按预注册文字）。** 冻结代码输出为 INCONCLUSIVE（把"少于 10"用在了 8 个匹配主评价 anchor 上，这不是预注册规则）；两者同时归档于 `model/decision.json`（代码）与 `model/adjudication.json`（裁定）。c1、c2、c4、c5 满足；c3（BioPlex）NOT EVALUABLE。**Gate A 关闭，不继续优化。**

1. **匹配主评价（8 个 anchor，71 个正例）：** 在覆盖度/基因组协变量和全背景 Jaccard（M1）之上，加入 K-562 / Hep G2 / MCF-7 内的分层 MH 共占据关联（M2），AP 从 0.259 升到 0.369，**ΔAP = +0.109（anchor bootstrap 95% CI +0.062 到 +0.176），相对提升 42%**。MH 块在伙伴广度十分位内置换 200 次，第 95 百分位 0.0003，p = 0.005。8 个 anchor 中 7 个提升；逐一剔除 anchor 后 ΔAP 在 +0.088 到 +0.123 之间。
2. **完整候选空间（23 个 anchor，150 个正例，18,561 对）：** ΔAP +0.034（CI −0.009 到 +0.087），方向为正但 CI 含 0；18/23 个 anchor 提升；没有变差（不触发降级规则）。
3. **增益集中在 bZIP：** 匹配集中 bZIP anchor 平均 +0.163（5/5 提升），非 bZIP +0.045（2/3）。去掉 bZIP 后：匹配集 +0.044（3 个 anchor，CI −0.004 到 +0.119），完整空间 +0.012（18 个 anchor，CI −0.030 到 +0.075）。SMAD3、SMAD4、STAT2、YY1 在完整空间中变差。
4. **BioPlex（只作支持）：** 293T 中 M2 − M1 = +0.062（CI −0.035 到 +0.140）；HCT116 −0.008。
5. **DepMap 共依赖（探索）：** 残差相关 |r| ≥ 0.3 且 FDR < 0.05 的非 CP 对只有 2 个，无法评价。

**结论（GPT 审定措辞）：** Context-aware protein co-occupancy associations improved the recovery of curated co-complex partners beyond conventional genomic overlap in a matched subset of transcription factors. However, the improvement was concentrated in bZIP-family factors and did not generalize robustly across the full candidate space or the non-bZIP subset. These results support a limited capacity to recover family-associated occupancy relationships, but do not establish generalizable protein assembly inference.

| 项 | 归档状态 |
|---|---|
| Gate A | CONDITIONAL — restricted family-level evidence |
| General protein assembly inference | NOT ESTABLISHED |
| Independent physical assembly validation | NOT EVALUABLE |
| 下一步 | CLOSE，不追加计算 |

Gate A 的 CONDITIONAL 不影响 Gate B 的 GO：Gate B 直接检验扰动响应预测，有独立的预注册比较和阴性对照。

## 1. 判定的一个实现差异（需审核裁定）

- v0.2 A2 写的是"若**可评价** anchor 少于 10 个，报告为 insufficient coverage"。可评价 anchor 有 23 个。
- 冻结代码把"少于 10"用在了**通过匹配平衡的主评价 anchor** 上（v0.2 A4 要求不平衡的 anchor 不进入匹配主评价）。23 个中只有 8 个通过（任一协变量 \|SMD\| ≤ 0.5）；15 个退出：ATF1、ATF3、BATF、CEBPA、CEBPB、FOSL1、FOSL2、JUNB、JUND、RARA、SMAD3、SMAD4、STAT1、STAT2、YY1。
- 按冻结代码：INCONCLUSIVE。若按 v0.2 文字（23 ≥ 10），c1/c2/c4/c5 满足、c3 NOT EVALUABLE → CONDITIONAL（预先接受的上限）。
- 两种读法都不是 GO。没有在看到结果后修改代码。**GPT 裁定：以预注册文字为准 → CONDITIONAL**；匹配后只剩 8 个 anchor 记为严重的证据覆盖限制。

## 2. 设计（简述）

- **蛋白 universe：** Figure 1E 的 808 个蛋白，326,028 对，Complex Portal 同复合物 565 对。
- **Anchor：** 序列特异 TF、≥ 20 实验、≥ 3 细胞类型 → 147 个；≥ 3 个 CP 伙伴 → 23 个可评价（150 个正例）。
- **模型（ridge logistic，留一 anchor）：** M0 覆盖/基因组协变量（两蛋白的实验数、广度、promoter/HOT/ATAC/cCRE 占比、GC、细胞类型与研究数的 min/max，共享细胞类型与研究、三背景可测标志）；M1 = M0 + log Jaccard；M2 = M1 + 三背景 MH log2 OR。
- **匹配：** 每个正例配 5 个同 anchor 的未标注伙伴（Mahalanobis）。匹配后合并 SMD 全部 < 0.2（匹配前 0.3–0.9）。

## 3. 结果表

| 评价集 | anchor | n（正例） | AP M0 | AP M1 | AP M2 | ΔAP M2−M1（95% CI） | AUROC M1 → M2 |
|---|---|---|---|---|---|---|---|
| 匹配主评价 | 8 | 426（71） | 0.224 | 0.259 | 0.369 | +0.109（+0.062 到 +0.176） | 0.595 → 0.668 |
| 完整候选空间 | 23 | 18,561（150） | 0.052 | 0.077 | 0.112 | +0.034（−0.009 到 +0.087） | 0.822 → 0.838 |
| 匹配，去 bZIP | 3 | 144（24） | 0.195 | 0.194 | 0.237 | +0.044（−0.004 到 +0.119） | 0.508 → 0.580 |
| 完整，去 bZIP | 18 | 14,526（103） | 0.052 | 0.079 | 0.092 | +0.012（−0.030 到 +0.075） | 0.807 → 0.819 |

- **M1 − M0（Jaccard 的贡献）：** 完整空间 +0.026（CI +0.007 到 +0.046）。
- **完整空间 top-k lift：** top-10 M1 49× vs M2 12×；top-50 17× vs 42×；top-100 16× vs 32×。M2 在前 50–100 名更好，但最前 10 名不如 M1。
- **逐 anchor（完整空间）：** 提升最大 ATF3（0.23 → 0.56）、DDIT3（0.24 → 0.48）、JUN、CEBPB；变差 SMAD3（0.44 → 0.12）、STAT2（0.67 → 0.39）、SMAD4、YY1。

## 4. BioPlex 与 DepMap（不参与判定）

| 网络 | anchor | 对数（正例） | AP/prevalence M1 → M2 | ΔAP M2−M1（CI） |
|---|---|---|---|---|
| 293T | 22 | 14,357（53） | 47 → 64 | +0.062（−0.035 到 +0.140） |
| HCT116 | 14 | 6,312（28） | 39 → 37 | −0.008（−0.098 到 +0.089） |

BioPlex 中未出现的边是未标注，不是阴性。DepMap：残差化后只有 2 个高共依赖对，探索性分析无信号。

## 5. 局限

1. 可评价 anchor 偏向 bZIP，Complex Portal 收录的 TF 伙伴本身就以二聚化伙伴为主。
2. 匹配平衡规则让 15/23 个 anchor 退出主评价，主评价只代表 8 个 anchor。
3. MH 关联只来自三个背景（K-562、Hep G2、MCF-7），其他背景未覆盖。
4. 23 个可评价 anchor 依赖 Complex Portal 伙伴数，不独立于标签选择（选择不依赖模型性能）。
