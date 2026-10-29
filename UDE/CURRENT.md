# PMA 当前状态索引

本页是 [`CURRENT.yaml`](CURRENT.yaml) 的 **2026-10-26 16:33 EDT 快照**的人工摘要；机器可读状态只在 YAML 中维护。后续任务必须先核对 Git、PR、数据和审核记录，不得把本页当作实时监控。

**总体：AMBER。** 项目身份与冻结范围可追溯；理解层只有报告级证据；设计层有一个未解决的合同冲突和一批未批准的外部提案；执行层分散在已集成基线、开放 PR 与其他分支。U/D/X 版本均为 `unknown`，没有推定的统一批准版本。

| 层 | 当前可依赖的来源 | 边界 |
|---|---|---|
| [Understanding](understanding/CURRENT.md) | 章程、冻结 v0.2 的项目问题；Step 1–4a 的报告值 | H-01–H-06 全部未验证；Q-01–Q-08 未决 |
| [Design](design/CURRENT.md) | D-01–D-04 的现有合同；D-05/D-06 为未合并变更 | 9 项外部提案（P-01–P-09）均未批准，其中 4 项为 L3 |
| [Execution](execution/CURRENT.md) | `origin/step4b-atac-footprinting@6c2e323`；PR #9 为本索引 | PR #5–#8 未合并；原 checkout 脏；记录数字不一致 |

## 六门核对

| 门 | 结果 | 依据 |
|---|---|---|
| ① 项目身份 | **PASS** | 章程 Part 1 与 [PROJECT.md](PROJECT.md) 一致；100% 定义与 non-goals 明确。 |
| ② 理解完整性 | PARTIAL | 定义清楚，但证据是报告值、假说未验证、无 U 版本。 |
| ③ 理解 → 设计 | PARTIAL | 冻结 v0.2 可追到创始问题；D-05/D-06 与 P-* 未用 U ID 做变更影响分析。 |
| ④ 设计 → 执行 | PARTIAL | D-03 与 D-05 冲突；D-04 未产生 benchmark；执行未绑定设计版本。 |
| ⑤ 版本与审批完整性 | PARTIAL | U/D/X 均 `unknown`；GPT 审核 ≠ UDE 人类接受；Worklog/handoff 数字滞后。 |
| ⑥ 朝交付物收敛 | PARTIAL | 关键路径应为 Step 4a closure → Step 4b → 统计框架；KB 的 pan-cancer/BAF/DBD/DL 属 L3 漂移风险。 |

## 关键问题（按分级）

- **L3（须用户决定并重新批准设计）**：P-01 region-centric 数据模型；P-04 hotspot/Tn5/normal–cancer 扩展；P-06 DBD–motif 新轨道；P-08 Genome Biology pan-cancer + BAF + Fig. 1–5。它们与章程 non-goals 或 v0.2 两张主图的冻结范围冲突。
- **L2（设计影响评审）**：P-02 饱和分析；P-03 bias-aware post-hoc footprint validation（与 D-04 语义冲突）；P-05 bigWig 定义与 normalized occupancy；P-09 representative vs full-raw 归因 benchmark。
- **L1（信息更新）**：P-07 不新建通用 de novo motif reference；KB 中的 29,778 motif 计数为历史值，不写入设计。
- **已存在的合同冲突**：D-03 逐实验峰 vs D-05 坐标唯一 BED6。在接受、替换或并存决定前，不能把两种产物叫成同一基线。

## 待决事项

| ID | 决策 | 所有者 |
|---|---|---|
| HD-01 | D-03 与 D-05 的产物关系 | 用户 |
| HD-02 | KB 的 L3 提案是否进入 PMA（或拆为独立项目） | 用户 |
| HD-03 | Step 4b 是否采用 P-03 的多模型 bias annotation | 用户 + GPT 设计审核 |
| HD-04 | 进度口径：20% / 33% / 重新核算 | 用户 |

## 下一步（已授权范围）

只做本索引的审核与修订：核对 YAML、链接和 Git 差异，等待 PMA 固定审核会话结论。**不**运行外部分析、**不**改变设计基线、**不**合并任何现有 PR。合并 PR #9 或任何其他 PR 都需要用户单独确认。
