# PRINT pnorm 诊断：Argos 单次运行审核包

## 当前状态

- 范围仅限 PRINT Step 4b；Claude 负责 ChIP BED6/PR #7。
- 固定 PMA 项目对话已对 PR #8 HEAD `6cf2b6b9a55555c1be13a927978066bbddfca23c` 的诊断实现给出 `APPROVE`，只批准代码审查，没有授权 Argos 访问、暂存、缓存读取或运行。
- 当前 PR #8 OPEN、未合并。用户允许修改本地 PRINT 源码；该许可不替代 Argos 单次执行门禁。
- 本包请求固定 PMA 对话审核精确路径、单次 gate 命令、资源/超时与失败清理边界，并明确批准一次诊断尝试。获得批准前不得执行下面的远端命令。

## 唯一诊断范围

只重放已完成 V5 的 8 个 K562 peak；读取现有 count chunk、bias group、10/20-bp dispersion model、已验证的 V5 score tracks/native-event BED、selection BED/map、V5 evidence 和 pinned PRINT 源模块。只在新目录写 pnorm 诊断表和 manifest。不重算 BAM/fragments/counts，不改动原 cache、track、event 或源代码，不扩峰、不做准确度排名。

预期输出仅为 `pnorm_calls.tsv`、`pnorm_positions.tsv`、`manifest.json`，位置：
`/home/zz950/PMA_fetch/pma_print_pnorm_diagnostic_rcapps3_20261020_v1/`。
gate 状态及 stdout/stderr 由不可变 gate 写入其既有 status/log 目录。输入损坏、哈希改变、评分/事件不等价、未定位或未分类 warning、未知/未屏蔽异常均保留证据并 fail closed；不重试、不扩大样本。

## 固定输入路径

```text
PRINT source: /home/zz950/softwares/src/PRINT
V5 main/cache: /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/print_main_print
selected BED: /home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/eight_frozen_peaks.bed
selection map: /home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/eight_frozen_peaks.map.tsv
V5 output prefix: /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/print
shared models: /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/print_shared
V5 evidence: /home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5
new diagnostic output: /home/zz950/PMA_fetch/pma_print_pnorm_diagnostic_rcapps3_20261020_v1
unique gate ID: BG_K562_PRINT_PNORM_DIAG_20261020_V1
unique staged code directory: /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1
```

The V5 `run_print.R` constructs `print_main_print` beside the output prefix. The V5 supervisor constructs the selection BED and map under its evidence root. These relationships are documented locally; they must be verified read-only during fresh preflight before staging.

## Staging set and hashes

Only the diagnostic R file and its same-directory helper are staged; no data are staged.

```text
diagnose_print_pnorm.R  3d883552675d765010fb08663d011ef0ee285c13c106fdc5ab4617488055aca0
print_variable_width.R  9dee1d7588e7a47a9449ae88a61710c4f16dd4b6f40cef93886b6421ef1f362b
```

Expected local source files are under `/tmp/pma-hint-smoke/scripts/04b_footprint/`. Preflight must reject a pre-existing staging directory, output directory, gate status for the unique ID, active matching process, host/architecture mismatch, missing input, any mismatch among the six trusted V5 evidence/track/event SHA pins, PRINT commit/module mismatch, missing R package/runtime, wrong immutable gate SHA, or an inability to confirm 44-GiB per-process `RLIMIT_AS` and CPU-only single-slot settings. Count/bias/model cache files have no historical pins; the diagnostic hashes them before reading and verifies those hashes again on normal/catchable error exits, describing them only as frozen at diagnostic start.

## Proposed one-time invocation

After fixed-PMA approval and successful fresh preflight, stage the two hash-pinned scripts to the unique code directory and call the immutable gate exactly once. `timeout` imposes a 30-minute wall limit with TERM followed by KILL after 60 seconds. The gate supplies the established 44-GiB per-process address-space cap, one-slot CPU-only environment, and unique status/log records.

```sh
ssh zz950@rcapps3.dfci.harvard.edu 'mkdir -m 700 /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1'
scp /tmp/pma-hint-smoke/scripts/04b_footprint/diagnose_print_pnorm.R /tmp/pma-hint-smoke/scripts/04b_footprint/print_variable_width.R zz950@rcapps3.dfci.harvard.edu:/home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/
ssh zz950@rcapps3.dfci.harvard.edu 'sha256sum /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/diagnose_print_pnorm.R /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/print_variable_width.R'
ssh zz950@rcapps3.dfci.harvard.edu 'R_LIBS=/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib:/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4 bash /home/zz950/PMA_fetch/pma_bg_gate_v2.sh BG_K562_PRINT_PNORM_DIAG_20261020_V1 /usr/bin/timeout --signal=TERM --kill-after=60s 1800s /home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/diagnose_print_pnorm.R /home/zz950/softwares/src/PRINT /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/print_main_print /home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/eight_frozen_peaks.bed /home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/eight_frozen_peaks.map.tsv /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/print /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/print_shared /home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5 /home/zz950/PMA_fetch/pma_print_pnorm_diagnostic_rcapps3_20261020_v1'
```

The review should confirm that the installed gate accepts `/usr/bin/timeout` as its command argument and propagates the timeout/return code as expected. If it does not, do not improvise a different remote command; repair this packet locally and obtain a new exact-head review. The three SSH/SCP commands above are proposals, not executed commands.

## Fresh preflight and stop rules

Following exact-command review and explicit one-time release, run a read-only preflight first: host and architecture, current time/available memory/CPU affinity, no competing diagnostic process, unique paths/status absent, gate SHA, staged-file hashes/modes, pinned PRINT commit/modules, R 4.2.2/runtime and package availability, all required input paths, all six trusted artifact hashes, and the 44-GiB gate configuration. Any failure means stop before the gate call. Gate invocation consumes the single attempt, even if it fails. A timeout, R error, warning blocker, hash failure, changed original artifact, incomplete output or mismatch is retained as-is; no automatic retry or larger peak set.

## Result acceptance

L1 requires gate exit code, completion/diagnostic manifest, input and original-output hashes unchanged, 16 V5 comparisons and 14/17 event counts retained, all warnings attributed by replay context, and every anomalous coordinate linked to a known native mask. L2 remains blocked if a warning cannot be explained or any anomalous value is outside native exclusion. Even an all-masked result only closes the diagnostic blocker; it does not establish accuracy, full-peak feasibility, or caller superiority. The fixed PMA conversation must review the result package before any downstream stage.
