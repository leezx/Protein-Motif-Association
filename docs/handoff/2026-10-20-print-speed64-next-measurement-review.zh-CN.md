# PRINT 64-peak V2 超时后的下一步评估方案

时间：2026-10-20 12:23 EDT  
范围：仅 PMA Step 4b footprint；PR #8。ChIP BED6/PR #7 不在本次范围。

## 审核对象与结论

固定 PMA 项目对话 `PMA｜固定阶段审核` 对 PR #8 live HEAD
`1503811a09308f7a699774ca75137bbdaea84bda` 完成 Quick L1/L2/L3 阶段复核。

- **L1：**完整 64-peak 产物交付 FAIL；超时监督和清理 PASS。
- **L2：**准确度及全峰性能仍 BLOCKED/UNVERIFIED-critical。
- **L3：**ON TRACK，实际进展 PARTIAL。超时和采样 RSS 是真实观测；分组开销解释为中等可信；完成时间和全峰投影可信度低。
- **准确度：**没有独立占据标签评估，本轮不产生工具准确度排名。

## 唯一建议

若后续继续取得一个可完成、可报告的 PRINT runtime measurement，建议维持同一份冻结的 64 个 peak、2 workers、radii 10/20 和现有实现，只把新的一次任务总执行预算改为 60 分钟。用新 run ID、唯一 evidence/output 路径；保留当前内存限制和 process-group sampled VmRSS 软停止。此预算可能让任务完成，但审核明确表示不保证完成。

在提交新的 exact-head review 前，先从已有 64 行映射表汇总：

1. 实际 chromosome × exact-width 分组数及每组行数/宽度；
2. 每组、每个 radius 的开始/结束记录及总调用数；
3. 将 105 个已完成评分调用与已记录的组/radius 逐项对齐。

原因：当前实现按 chromosome × exact-width 分组，并对每个 radius 独立调用。64 个峰最多形成 64 组、最多 128 个 group-radius 调用，但上限不是实测组数。105 次完成代表调用数，不是峰数或完成百分比，不能直接换算剩余时间。分组计时会判断瓶颈来自很多小组的启动/并行开销，还是少数大组的计算时间。

## 可作出的结论与边界

- 可确认：V2 的 64-peak PRINT 执行超过 30 分钟预算；caller 运行 1,710.18 秒后被 TERM，采样 process-group VmRSS 最高约 17.09 GiB；没有最终 track、event BED 或 timing TSV。
- 不能确认：完整 64 峰运行时间、真实内存峰值、CPU 总量、准确度，或 159,628 峰全量时间/内存。
- 8-peak V3 的 424.117 秒只能描述该 8 峰样本，不能按峰数线性外推。

## 授权状态

固定 PMA 审核只给方案，没有批准远程读取、代码暂存或 Argos gate。V2 one-shot 已消耗，禁止重试。下一次运行必须先提交方案与映射组统计到同一 PR，取得新 exact-head 审核和明确的单次运行批准。PR #8 不得合并，除非用户另行授权。

