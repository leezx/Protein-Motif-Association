# PRINT V3 八峰 smoke 结果与资源交接

时间：2026-10-20 11:10 EDT

项目：PMA Step 4b footprint；仅 PR #8。Claude 负责 ChIP BED6/PR #7，不在本次范围。

## 运行边界

固定 PMA 项目对话已对 PR #8 exact HEAD `7cadfcc276c08e324ef086b75bdc92a1ce0a1cd4` 明确批准一次 V3 smoke。仅在 Argos `rcGPUs` 执行；8 个冻结 K562 peak，2 workers，radii 10/20，CPU-only；总时限 30 分钟。每个进程 44-GiB `RLIMIT_AS`，另有 40-GiB 采样 process-group RSS 软停止线（不是 aggregate hard cap）。预检通过后 gate 只启动一次，无重试。

## 结果

- Gate ID：`BG_K562_PRINT_INTEGRATION_SMOKE_20261020_V3`
- Gate 状态：`EXIT=0`，11:01:31 至 11:08:36 EDT。
- 端到端 wall：424.117 秒（7:04.1），包含 selection、预检和 setup。
- GNU time 的 PRINT caller wall：5:37.52；user CPU 166.10 s，system CPU 21.84 s，CPU 55%；最大 RSS 17,920,756 KiB（约 17.09 GiB）。
- watchdog 采样 170 次，process-group 观测峰值 17.091 GiB；40-GiB软停止未触发。不要把单进程 `RLIMIT_AS` 解释为总任务硬内存上限。
- Inputs/regions：selector 扫描 159,628 个 eligible rows 后选出 8 个，位于 chr9/chr22，group sizes `[3,2,2,1]`，宽度 1042、1234、1777、1977 bp。冻结 peak BED SHA-256：`c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945`。K562 fragment SHA-256：`238367780a1b7a2a24595a4259bdbe91cb8be439c2e5fda210831ad60d77544f`。
- PRINT output：r10/r20 各 12,795 track rows；16 条直接比较全部 `bias_exact_match=TRUE`；native events 分别 14 和 17，共 31。Timing TSV：count construction 202.696 s；footprint group work 114.317 s，其中 r10 53.975 s、r20 59.972 s；直接比较 4.261 s；track write 0.676/0.634 s。

## 审计注意事项

1. Gate `.meta` 显示默认 `GROUP=ctrl TOOL=hint`，因为本次 gate 命令只提供 run ID 和 worker 路径。实际 argv 明确执行 PRINT 的 `run_print.R`，输出 prefix、GNU-time 命令和 `print.*` 产物都确认是 PRINT。下次如需运行，review 后应显式传 `ctrl print` 以免元数据混淆。
2. GNU-time stderr 有 `There were 14 warnings (use warnings() to see them)`，但具体 warning 列表未写入日志。本次没有证据表明 warning 导致输出失败，但不能宣称已逐条审查或无 warning；需在固定 PMA 审核中决定对输出解释是否有影响。
3. 此 8-peak smoke 证明固定管线产生输出并给出低规模时间/资源观测；不可据此线性外推 159,628 peaks 的总时间，不代表 genome-wide 全碱基扫描，也不提供准确度或工具排名。

## 外部证据（均不入仓库）

Run root：`/home/zz950/PMA_fetch/pma_print_integration_smoke_rcapps3_20261020_v3/`

Scientific output：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_integration_smoke_rcapps3_20261020_v3/`

| Artifact | SHA-256 |
|---|---|
| `smoke_completion.json` | `b78d652484b6dbf88bb351d318bb90b20ea3706338c9a63eadb29af434d7b158` |
| `selection_summary.json` | `ca2dc5f440fd5277b7935d1eb37ad408cf0fa6de1da358a00ef72cad9521fbc2` |
| `watchdog.jsonl` | `1182307a2fd0426578ebfa641a150fc7ead6448572e221722e0ada64bae9f903` |
| GNU-time stderr | `21a82bcea8e04ba63aca9164b5d04584b2996eb91291bfeeadfe35205338891d` |
| `print.timing.tsv` | `b5d75bb05d5cde9208420faca102335d03bcc5692c659b13e8f2ebf40a8a12fd` |
| `print.direct-comparison.tsv` | `9ea154be823bc29a28a75b4c66ca5fc930184406d80d8dce2d4d6044976b5399` |
| `print.r10.track.tsv.gz` | `135b6a053013c19701d67daef37c0a8425dea1c30f2faecf9039fc453b025576` |
| `print.r20.track.tsv.gz` | `c67429ee81867f70c9410af744087806ed3bdcd9de8bfe69f61331e479857825` |
| `print.r10.native_events.bed` | `30aedcd7843e947164290335cdfaff61b33338f7b44e7c6ebb887394d4fa66c8` |
| `print.r20.native_events.bed` | `b18d8916b5df3ade276e1f6f50628a9b82bf34b6b4741acb6ae552dbf4b8ad72` |

## 阶段审核与下一步

初步 Quick 复核：L1 对 gate/产物完成状态为 PASS，但 14 条 R warning 的具体内容和 gate 默认 TOOL 标签尚待复核；若 reviewer 认为 warning 可能改变输出，应把 L1 保持 BLOCKED。L2 为 BLOCKED / UNVERIFIED-critical：没有独立 ChIP/CUT&RUN 标签、matched-sensitivity、扰动/正交证据，不能排名准确度。方向 ON TRACK，实质进展是第一次成功得到 PRINT 双半径 track、直接比较结果和实际 wall/RSS。请固定 PMA 项目对话审阅这一里程碑并确认适合的下一项速度实验设计。V3 one-shot 已消耗；在新的 exact-head 审核和明确新放行前，不启动更大规模或全 peak 任务，不改环境、不合并 PR。

HUMAN DECISION: PENDING
