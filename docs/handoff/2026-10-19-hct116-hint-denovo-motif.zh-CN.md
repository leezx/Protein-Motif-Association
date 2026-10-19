# HCT116 HINT motif 与 K562 TOBIAS 里程碑

时间：2026-10-19 14:20 EDT
工作区：`/tmp/pma-hint-smoke`
PR：#8，更新前 HEAD `361e6589ce4cab9e88b381758836ea4c2bf08532`（OPEN）

## 结果

### K562 TOBIAS 速度任务

Argos 任务 `BG_K562_TOBIAS_SPEED_V1` 于 14:05:48 EDT 退出 0。固定输入为 ENCODE `ENCSR868FGK` BAM 和 77,668 个固定 1-kb 窗口。任务记录的片段数为 110,891,807；独立 read count 是 110,891,952，计数条件略有不同，最终速度归一化前需统一过滤谓词。

| 阶段 | 时间 |
|---|---:|
| ATACorrect | 2,827 秒 |
| FootprintScores | 834 秒 |
| 事件轨道转换 | 75 秒 |
| 全任务 | 1:02:16 wall |

GNU time 最大 RSS 为 1,267,312 KB。输出 3,319,912 个事件，events BED SHA-256：`de8267471ad662be0122662d903e5b3cfb01e578690536eec1c7ad358c67e178`；footprints bigWig SHA-256：`970835ad182d020f1e5485288236c851a3096b5d2e07c47bf15dd7440787326b`。K562 的 ENCODE 记录有 NFR QC 警告，所以这个样本只作时间测量，不作准确度真值。HINT 使用 32 分块、TOBIAS 使用 16 cores，原始 wall 不能直接选速度赢家。

### HCT116 HINT→STREME

ctrl 和 aux 任务分别于 14:08:43、14:07:44 EDT 退出 0。每组从最高分 HINT footprint/窗口提取 50-bp 序列，并与同一窗口、GC 差不超过 0.1 的背景配对；背景排除模式为 `selected_only`。配对数 ctrl/aux 为 90,387 / 88,444。两组 STREME 都报告 10 个 motif 且各 E<0.05。

- ctrl 输入 HINT events SHA-256：`ea2b730c79e82637a63bf18f0493b689d3ad40f8f6c81b011ebeaee8660225d`
- aux 输入 HINT events SHA-256：`eb08834325ee1119b832f2f0bc132bfa26a9b726511fc77149812500127eb517`
- ctrl STREME 文本 SHA-256：`7d1085d2fd3ace2a61bef448606d2fbc5d60ff2959f0d12911e9d523a6a32804`
- aux STREME 文本 SHA-256：`9085a2c4a06f135ad774dd04be5441dd99ca50d2e92d0d93eb22f9c09e089180`

这只是探索性 HINT motif 结果。`selected_only` 背景可能包含其他 HINT 事件，因此富集会受影响；E-value 不证明准确度、TF 身份、独立复现或 CTCF 降解响应。不得据此发布 motif reference 或认定 HINT 为赢家。

## 阶段判断与后续

- L1：任务退出码、输入/输出和哈希可核验；通过。
- L2：准确度排名与公平速度比较仍阻塞。尚无留出 ChIP AUPRC、匹配灵敏度 B1、扰动 B2 或正交 B3。
- 方向：结果对旧的 footprint→motif 路线有帮助，但 HINT motif 探索先于工具赢家选择，偏离用户当前的 accuracy-first 优先顺序。
- 真实进展：HINT 在两种 HCT116 条件下产生可复现保存的候选 motif 输出；没有工具赢家或广泛癌种结论。
- 持久 GPT 对话目前仍显示旧 PR #6 请求及 `systemError`；PR #8 当前 exact-head review 和人工阶段接受均未获得。

在 PR #8 当前 HEAD 获得审查、且人类接受阶段结论前，不启动依赖性准确度评分、全 TraceBIND 校准、PRINT 重跑或癌症 ATAC 全局新运行。放行后优先验证独立 HCT116 CTCF ChIP 标签，并按冻结共同位点集执行分块留出 AUPRC、B1–B3。所有分析产物均留在 Argos 外部目录；仓库仅记录摘要、参数与校验哈希。
