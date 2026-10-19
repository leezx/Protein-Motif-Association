# Step 4b footprint：十轮内形成可行工具选择

更新时间：2026-10-19 15:51 EDT（UTC 19:51）
范围：仅 footprint→de novo motif；ChIP BED6 / PR #7 由 Claude 负责，本交接不涉及。  
PR #8：`task_20261019_hint_overlay_smoke`，OPEN、未合并。固定 PMA 对话对完整 HEAD `0829b0886777637a88fb3925ce9d1f511b1a00dd` 给出 `APPROVE`，仅限文档/方法与仓库只读审计；不批准任何 Argos 或数据操作。固定 handoff 不自引用更新自身 commit SHA，后续复审前从 GitHub 读取实时完整 tip。
审核边界：此前 `fd0b041` 的 APPROVE 仅覆盖方法文档；`525f0d4` 收到的时间、状态来源、折外边界和事件级备选 findings 已在同 PR 修复，并获当前 `0829b08` 方案级批准。15:41 EDT Argos 队列读取来自当时用户明确要求的 15 分钟监控 heartbeat；只读取调度与已有状态文件，没有读取实验数据，也没有核查 detached processes。该监控授权不扩大为 caller 执行授权。

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

## 对 `525f0d4` 审核反馈的修正（已推送并获方案审核）

固定 PMA 项目对话对 `525f0d4` 返回 `REQUEST_CHANGES`。同 PR 修订及 handoff-sync 已推送：不再把空 `qstat` 解释为无后台任务；把 15:41 队列读取归因于用户的 15 分钟监控指示，并与实验数据访问分开；将 GNU `time` 子进程 28:18.88 与 job 时间戳 28:24 标明为不同口径；允许 held-out 输入用于冻结 caller 的预测，同时禁止用 held-out 标签/分数分布进行拟合、适配或选择；补充连续分数不可用时的事件级备选，并允许第十轮以不可排名结束。HCT116 HINT→STREME 输出改列为探索性 motif 结果，不作为 B4 验证。复审前从 GitHub 确认完整 live branch tip，并在固定 PMA 对话审核该 SHA。

固定 PMA 对话对精确 HEAD `0829b08` 审核为 `APPROVE`。审核确认：空 qstat 仅表示无队列作业；状态查询授权与实验数据访问已分开；时间/HEAD/计时口径已说明；允许冻结 caller 预测时使用 held-out 输入，禁止利用 held-out 标签/分数拟合或选择；事件级替代与“不能排名”停止条件已写明；HINT-STREME 仅属探索。仍未建立真值、共同连续分数或折外 score。此 APPROVE 只放行基于仓库现有材料整理准入/adapter/fold-exclusion 清单和同 PR 审计记录，不放行 Argos、实验数据、分析、环境改动或 caller 运行。

## 仓库证据资格清单（只读审计，2026-10-19）

下表只根据 PR 分支源码、设计文档及既有 handoff 记录判断；本轮没有重新访问 Argos/实验数据。`eligible` 表示可以进入相应准确度比较的前置资格，不表示结果已生成。

| 项目 | 仓库证据 | 当前判定 | 解除条件 / 允许的结论 |
|---|---|---|---|
| 独立 occupancy/扰动标签 | 设计 §4 要求同一 HCT116 CTCF 体系的匹配 ChIP、输入、独立生物学重复和可解释校准。CODEX_HANDOFF 既有记录称候选 ChIP 文件/manifest 尚未在此前搜索的 PMA raw/processed 路径验证，已有的是 ATAC BAM 与校验清单。 | BLOCKED；不得把 ATAC 校验或 HINT footprint 当 ChIP 真值。 | 先有可追溯、独立重复、匹配对照和 QC 的标签资产；否则第 3 轮记录无合格标签并停止准确度排名，或另选经阶段审核的标签体系。 |
| PRINT score | `scripts/04b_footprint/run_print.R` 写 `.r<radius>.track.tsv.gz`，列 `score = aggregateScores`，并另写原生事件；设计固定 r10 作为候选连续轨。 | CANDIDATE；当前速度尝试 EXIT=1，不能作为成绩。资源哈希、正式输出完整性和折外计算均未通过。 | 先完成有效运行、固定代码/参数/资源摘要与完整 callable coverage，再判断能否提供严格 OOF continuous score。 |
| TOBIAS score | `scripts/04b_footprint/run_tobias.sh` 输出 `footprints.bw` 连续 track，再调用 `events_from_track.py` 生成 BED。 | CANDIDATE；工程速度 EXIT=0，但既有 handoff 报告与其他工具的过滤数不一致且 K562 有 NFR 警告；无准确度资格。 | 对齐片段谓词/分母和 BW mask；确认分数方向、完整性、参数/资源哈希及 fold-excluded 生成。 |
| HINT output | `scripts/04b_footprint/run_hint.sh` 只运行 RGT caller 并汇总 `events.bed`。 | 当前仅阈值化事件；不进入 AP。已知 K562 全窗口任务有 3,125 个跨边界事件，32 路聚合 RSS 未测。 | 如需连续 AP，须添加和冻结文档化 threshold-free adapter；否则仅按第 6 轮事件级方案比较，先修事件边界/聚合内存审计。 |
| TraceBIND output/mode | `scripts/04b_footprint/run_tracebind.R` 对每区段跑 NB footprinting 后以 `p_threshold` 输出事件 BED；注释明确本 wrapper 是 PRINT-bias mode，无 mtDNA fine-tuning、无 mito FDR。 | 当前 threshold-truncated，输出不能当连续轨；full TraceBIND 不等同本 wrapper。 | AP 前须提供阈值前全分数且冻结 full/reduced mode；若仅有事件，走合法事件级比较；完整模式须记录 mtDNA 校准资格。 |
| 缺失值/公共 score 集 | 设计 §4.3 指明 absent event 不是 0；`events_from_track.py` 的事件输出不适合作 AP adapter。 | BLOCKED；PRINT/TOBIAS 是候选连续轨，HINT/TraceBIND 目前没有共同连续输出。 | 每工具显式区分 finite score、missing/unscorable、run failure；锁定共同 candidate mask 和共同可评分集合。四方 AP 仅在共同完整覆盖成立时可报。 |
| 折外隔离 | 当前 caller wrappers 接受整份 BAM/regions 或全量 fragments；本审计在 `scripts/04b_footprint/` 未发现已实现的 1-Mb folds、embargo、OOF score manifest 或适配训练折隔离。 | BLOCKED；当前没有验证过的 fold-excluded scores。 | 先落地并经静态/小型合成核对的 fold manifest、context-radius 说明、训练/测试读段隔离与 embargo 审计。不能证明则不报严格 held-out AP。 |
| B1 负控与事件比较 | `scripts/04b_footprint/eval_round1.py` 只按 native thresholds 统计相同窗口的 event rows / callable Mb；脚本声明不做准确度排名。 | 仅描述性；不同阈值未匹配灵敏度。 | 在合格训练标签上冻结目标召回与参数，测试报告 recall、naked-DNA false-event density；一对一匹配、共同定位窗口及固定事件/bp预算按第 6 轮执行。 |
| 癌症全局 caller 与 de novo motif | 当前 HCT116 HINT-STREME 是已记录的探索结果，不等于独立 B4；Cancer ATAC 全区域结果尚未在本 PR 证据中形成经 QC 的统一产物。 | 暂缓选择/生产发布。 | 只对符合准确度/特异性门槛或明确标注工程基线的最多两个候选启动后续阶段；第 10 轮允许不可排名，不用 motif 数反推准确度。 |

**本轮可测进展：**把“缺什么才可能排准确度”从概念写成逐工具准入表。当前可行结论仍是：尚不能可信地宣布四工具中谁最准；现有证据支持 HINT 是已测工程基线、TOBIAS 有一次有效速度记录、PRINT 有一次失败记录、TraceBIND wrapper 是 reduced mode。要在十轮内给出答案，必须在第 3–6 轮拿到合格标签/可用事件终点；若未拿到，第 10 轮明确报告“当前数据不能排名”，不追加无期限工具工程。

## 本轮 Review (Quick)

固定 PMA 项目对话已对 PR #8 exact HEAD `0829b0886777637a88fb3925ce9d1f511b1a00dd` 给出文档/方法 `APPROVE`，且批准范围明确不含执行。L1：PASS（GitHub PR 与三份文件核对）；L2：BLOCKED（无合格共同真值、连续分数和验证的折外结果）；独立性 LIMITED。方向 ON TRACK：十轮内先判断能否可信排名。进展 PARTIAL：首次把现有脚本状态变成逐工具资格表，仍没有准确度结果。可信性 usable with limits。观察到：TOBIAS 有一次可用工程速度，PRINT 失败，HINT 有事件边界/内存缺项，TraceBIND wrapper 是 reduced mode。支持：现有证据不能定准确度赢家。未确立：四工具 AP、可靠排名或泛癌赢家。GPT 只批准了基于仓库材料的准入/adapter/fold-exclusion 清单；人类阶段接受及任何计算授权仍未获得。**HUMAN DECISION: PENDING**。

## 下一项唯一高价值动作

准入/adapter/fold-exclusion 清单已按批准范围写入本交接。下一步仅将本次三份文件的审计记录提交到 PR #8，并在固定 PMA 对话审核完整新 HEAD。此审核只放行文档/只读审计，不自动许可任何 Argos 计算。执行阶段需另有明确范围和人类接受。
