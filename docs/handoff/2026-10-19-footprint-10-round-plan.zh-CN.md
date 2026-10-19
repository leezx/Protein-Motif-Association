# Step 4b footprint：十轮内形成可行工具选择

更新时间：2026-10-19 15:46 EDT（UTC 19:46）
范围：仅 footprint→de novo motif；ChIP BED6 / PR #7 由 Claude 负责，本交接不涉及。  
PR #8：`task_20261019_hint_overlay_smoke`，OPEN、未合并；当前修改基于已推送 HEAD `525f0d4f8e617349836c9ea94870c92cc08fb5ae`，固定 PMA 对话对该 HEAD 返回 `REQUEST_CHANGES`。本次文件仍在本地修改，尚未提交；后续 exact-head 审核必须针对推送后的完整 PR tip。
审核边界：固定 PMA 项目对话 `PMA｜固定阶段审核` 对 `fd0b041` 的 APPROVE 仅覆盖文档/方法设计，不批准计算。随后针对 `525f0d4` 的反馈要求修正时间、状态来源表述、折外预测/适配边界和事件级备用终点。Argos 队列状态检查属于用户明确要求的 15 分钟监控 heartbeat；该次检查只读取调度队列，不读取实验数据，也不检查 detached processes。该监控授权不扩大为 caller 执行授权。

## 现在能确定什么

2026-10-19 15:41 EDT Argos 只读核查：按当时用户的 15 分钟监控指示运行 `qstat -u zz950`，未列出该账户的调度作业。没有检查 detached/background processes，因此不能据此声称 Argos 上“没有任务”。只读取已有任务状态文件，未读取实验数据。状态文件在 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`。

- HCT116 unfiltered BAM verify V3：EXIT=0；四个 ENCODE BAM 的字节数、MD5、SHA-256、`samtools quickcheck` 和 chrM header 均通过。这只证明输入完整，不产生 ChIP 真值标签。
- K562 TOBIAS 速度任务：EXIT=0；固定 77,668 个 1-kb 窗口，3,319,912 个事件，墙钟 1:02:16，最大 RSS 1,267,312 KB。该 K562 输入有 NFR QC 警告，当前只作工程速度观测。
- K562 PRINT 速度任务：EXIT=1；39/39 chunk 后 R worker 缺少 `cladoRcpp`，墙钟 36:19.75、最大 RSS 34,130,552 KB。失败运行不构成有效速度或准确度结果。
- K562 fragment prep：EXIT=0，110,891,807 fragments。GNU `time -v` 子进程 elapsed 为 28:18.88；job start/end 时间戳相减为 28:24，两值来自不同计时口径，首选进程 elapsed。独立 K562 过滤基准为 110,891,952 proper pairs，存在 145 条差异，分母口径需先对齐；预处理时间计入 PRINT/TraceBIND end-to-end 时间。
- HCT116 HINT→STREME 探索：ctrl 90,387 对、aux 88,444 对，分别 10 个 motif，任务 EXIT=0。背景为同窗口 GC 匹配、`selected_only` 排除。仅是探索性 motif 输出；不能算 B4 的重复性/家族恢复证据，也不是准确度标签、独立真值或已验证 motif 库。
- HINT 全窗口 caller 任务此前报告 77,668 K562 窗口上 16:53.47、781,863 events；边界 QC 有 3,125 个跨窗口事件，聚合进程峰值内存未直接测得。运行通过不等于边界发布 QC 通过。
- 原始 smoke 为四工具各在 control、aux、naked gDNA 的相同 2,000 区域调用/描述统计；这些结果不能按事件数或 caller 原生阈值排准确度。

## 十轮封顶计划

每轮只交付该轮表格所列的一项验收物。不得因为某项失败静默更换终点、标签、搜索空间或工具模式。缺数据/实现时记录阻塞及最小解除条件；最多一次针对性工程修复，之后将该工具标为不合格/不可评分。所有重计算只在 Argos，CPU-only、每作业 44 GiB `RLIMIT_AS`、无 GPU；数据和结果留在仓库外。

| 轮 | 交付物 | 冻结验收 / 停止条件 |
|---|---|---|
| 1（本轮，已核对） | 四工具运行状态与可信性清单 | 仅 EXIT=0 且输出完整者算有效；PRINT 失败不算成绩，HCT116 BAM 校验不算标签，STREME motif 数不算准确度。输出已记录在本文。 |
| 2 | 目标与唯一主终点冻结 | 主终点优先为共同、独立标注位点上的 held-out AP；HCT116 CTCF degron只能支持局部“control-ChIP-bound 位点的保留/耗竭区分”，不得声称通用 footprint 真值或 pan-cancer 排名。缺合格标签则本轮结论为“不能作准确度排名”。 |
| 3 | 数据准入表 | 每个候选 ChIP/CUT&RUN/降解数据列出 accession、细胞、处理、replicate、生物重复、matched input、spike-in 时点/固定投入、基因组、开发集重用及 QC。达不到预设标签资格即 fail closed；无峰区域不能自动当真阴性。 |
| 4 | 每工具 adapter/模式资格表 | 冻结四工具版本、模式、资源哈希、连续分数字段、方向/单位、阈值前覆盖和 missingness。当前 PRINT/TOBIAS只是候选连续轨；HINT/TraceBIND当前 wrappers 为阈值事件，缺失事件不能填 0。无法阈值前打分的工具退出 AP 主比较，不能虚构四方 AP。TraceBIND 的 reduced PRINT-bias 与完整 mtDNA-calibrated 模式分开记账。把一次最相关作者基准的小规模模式核对/复现并入本轮；失败最多做一次针对性修复，然后如实标记不可复现。 |
| 5 | 公共输入和折外执行清单 | 同一 BAM/核内 fragment 过滤谓词、固定候选窗口/callable mask、hg38 资源哈希；按设计冻结 1-Mb block folds，并逐工具核实最大 score-context radius。允许 frozen caller 将 held-out reads/sequence 作为预测输入；禁止以 held-out 标签或其分数分布拟合、适配、选参、定阈值或选择工具。需要 sample-specific adaptation 的 caller 必须仅用训练折拟合，并隔离其所需上下文与 embargo；不能隔离则不参加严格 OOF AP。 |
| 6 | 主准确度结果或事件级备选／不可评分报告 | 若合格连续分数和标签存在，报共同位点 pooled OOF AP、覆盖、有效 n、paired block bootstrap 和六对校正。若任何工具无连续分数，则不造 AP；若所有比较者都能生成合法调用，使用预先冻结的事件级备选：一对一事件匹配、共同匹配窗口及定位误差；阈值只在训练折校准到预设标签召回，测试折报告实际召回和 naked-DNA false-event density，并补固定 event/bp budget 下召回。单阈值工具不能达到共同召回时只报原生工作点和 Pareto 关系，不声称匹配灵敏度。缺标签/共同终点/合法调用时，交付“不可排名”与具体缺项，不补造数据。 |
| 7 | B1–B2 方向/特异性报告 | B1 用训练折阈值在 naked DNA 报 false-event density，不称传统 FPR；B2 使用冻结 paired control→aux 标签。固定同一 callable 分母、事件 NMS、深度匹配、missingness；这两项不能单独判定主 AP 赢家。 |
| 8 | B3/B4 独立性报告 | B3 必须用工具开发集之外的正交 occupancy 真值；B4 报重复性和 motif-family recovery。作者自有数据或 motif 富集只能标为支持性/重分析，不能冒充独立准确度。若没有独立数据，明确“泛化未验证”。 |
| 9 | 公平速度/端到端癌症试用，若有合格候选 | 统一线程、资源、输入和过滤；包含 fragment prep 的端到端 wall、core-hours、峰值聚合 RSS、输出完整性。只对最多两个有资格的候选做冻结癌症 ATAC 全可及区域 footprint→STREME/TOMTOM 试用；motif 数不回流作准确度。若没有合格候选，不启动新试用，改交不可排名/证据缺口。若精度赢家慢，先 profiler 定位热点，后续另立 C/C++ 优化；本十轮不重写。 |
| 10 | 最终工具决策备忘录；若适用则交付 de novo motif | 若同一场景有可靠领先证据且 B1–B3 不冲突，选择该场景工具；准确度不可区分时可按可用性/端到端速度选部署工具，但必须写“准确度未证优”；若准确度/特异性/速度冲突，保留最多两个 Pareto 候选；资格不满足则以“当前数据不能排名”封板，写清缺少什么以及工程基线的局限，不强求新 footprint/motif 结果。只有此前资格和人类阶段门禁均通过，才交付工具的 footprint、背景匹配、de novo motif 与稳定性/QC。第十轮后不再扩展 benchmark。 |

## 对 `525f0d4` 审核反馈的修正（本地待提交）

固定 PMA 项目对话对 `525f0d4` 返回 `REQUEST_CHANGES`。本次同 PR 修正四点：不再把空 `qstat` 解释为无后台任务；把 15:41 队列读取归因于用户的 15 分钟监控指示，并与实验数据访问分开；将 GNU `time` 子进程 28:18.88 与 job 时间戳 28:24 标明为不同口径；允许 held-out 输入用于冻结 caller 的预测，同时禁止用 held-out 标签/分数分布进行拟合、适配或选择；补充连续分数不可用时的事件级备选，并允许第十轮以不可排名结束。HCT116 HINT→STREME 输出改列为探索性 motif 结果，不作为 B4 验证。

本次审核不放行 Argos、数据、环境变更或分析。它只要求修正文档；完整新 PR tip 推送后，仍需在同一固定 PMA 对话做 exact-head 复审。即使文档获批，运行依赖任务仍须满足相应人类阶段接受。

## 本轮 Review (Quick)

**L1：PASS（文档状态与范围核对）**；**L2：BLOCKED（无合格共同真值/共同分数）**；独立性 LIMITED。方向 ON TRACK：用有限轮次回答是否可排名，而不是用运行数代替进展。进展 PARTIAL：有真实运行失败与工程时长，但没有准确度比较。可信性 usable with limits。观察到：TOBIAS 固定窗口速度有效；PRINT 速度运行失败；HINT motif 探索已结束。支持：这些记录不能选准确度赢家。未确立：四工具共同 AP、可靠工具排名、泛癌赢家。建议 REVISE：修正文档后对新完整 PR tip 复审；本轮不启动 Argos。**HUMAN DECISION: PENDING**。

## 下一项唯一高价值动作

按 GPT 本次批准的窄范围，在 PR #8 同一分支补齐并审计这份准入/adapter/fold-exclusion 清单，逐项引用仓库现有脚本/文档证据；随后在固定 PMA 对话审查新 HEAD。该审核只放行文档/只读审计，不自动许可任何 Argos 计算。执行阶段需另申请明确范围与人类接受。
