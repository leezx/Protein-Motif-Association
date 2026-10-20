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

## Immutable gate source audit

The fixed `PMA｜固定阶段审核` conversation authorized a gate-file-only read: SHA-256 plus argv parser/exec lines. No gate execution, input/cache/output/process/environment/resource inspection, or staging was included. The exact remote file returned:

```text
SHA-256 3776778b950be90cad124c04937eee422c81466154eccdadfe9e57d58224253c
 3 ID=$1
 4 SCRIPT=$2
 5 GROUP=${3:-ctrl}
 6 TOOL=${4:-hint}
12 export JOB_ID="$ID" NSLOTS=1 GROUP TOOL
13 export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
18 status_code=0
19 "$SCRIPT" > "$D/$ID.stdout" 2> "$D/$ID.stderr" || status_code=$?
21 exit "${status_code:-99}"
```

The gate accepts exactly `ID SCRIPT [GROUP] [TOOL]` and invokes `SCRIPT` with no positional arguments. It does not forward arbitrary argv. The staged wrapper owns timeout and R arguments. It reads only its own `/proc/self/status` affinity line to select the first already-permitted CPU, then `exec`s `taskset -c CPU timeout ... Rscript`. This binds the diagnostic to one allowed CPU without changing host affinity or requesting more resources. Gate `NSLOTS=1` is metadata/scheduler context, not the CPU limit.

## Staging set and hashes

Only the diagnostic R file, its same-directory helper, and the fixed invocation wrapper are staged; no data are staged.

```text
diagnose_print_pnorm.R  3d883552675d765010fb08663d011ef0ee285c13c106fdc5ab4617488055aca0
print_variable_width.R  9dee1d7588e7a47a9449ae88a61710c4f16dd4b6f40cef93886b6421ef1f362b
run_print_pnorm_diagnostic_gate.sh  d07ebc0f711caf7af2a103a99233f4ef2e2629fb86ee962a2519de9c82642b8c
```

Expected local source files are under `/tmp/pma-hint-smoke/scripts/04b_footprint/`. Preflight must reject a pre-existing staging directory, output directory, gate status for the unique ID, active matching process, host/architecture mismatch, missing input, any mismatch among the six trusted V5 evidence/track/event SHA pins, PRINT commit/module mismatch, missing R package/runtime, wrong immutable gate SHA, or an inability to confirm 44-GiB per-process `RLIMIT_AS`, `taskset`, CPU affinity, and CPU-only/single-thread BLAS/OpenMP settings. Count/bias/model cache files have no historical pins; the diagnostic hashes them before reading and verifies those hashes again on normal/catchable error exits, describing them only as frozen at diagnostic start.

## Proposed one-time invocation

After fixed-PMA approval and successful fresh preflight, stage the three hash-pinned scripts to the unique code directory and call the immutable gate exactly once. The gate only accepts a script path, so the wrapper executes `/usr/bin/taskset -c <first-allowed-cpu> /usr/bin/timeout --signal=TERM --kill-after=60s 1800s Rscript ...`. It sets known BLAS/OpenMP thread variables to one and clears CUDA. The gate supplies 44-GiB soft/hard per-process `RLIMIT_AS`; this is not an aggregate process-tree memory cap. This remains a proposal pending exact-head review and a separate explicit one-time release.

```sh
ssh zz950@rcapps3.dfci.harvard.edu 'mkdir -m 700 /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1'
scp /tmp/pma-hint-smoke/scripts/04b_footprint/diagnose_print_pnorm.R /tmp/pma-hint-smoke/scripts/04b_footprint/print_variable_width.R /tmp/pma-hint-smoke/scripts/04b_footprint/run_print_pnorm_diagnostic_gate.sh zz950@rcapps3.dfci.harvard.edu:/home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/
ssh zz950@rcapps3.dfci.harvard.edu 'sha256sum /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/diagnose_print_pnorm.R /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/print_variable_width.R /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/run_print_pnorm_diagnostic_gate.sh'
ssh zz950@rcapps3.dfci.harvard.edu 'bash /home/zz950/PMA_fetch/pma_bg_gate_v2.sh BG_K562_PRINT_PNORM_DIAG_20261020_V1 /home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/run_print_pnorm_diagnostic_gate.sh ctrl print'
```

These commands remain proposals, not executed commands. `bash -n` passed locally for the wrapper. It selects the first CPU from its inherited allowed CPU list; fresh preflight must confirm `taskset`, `timeout`, Rscript, runtime/packages, paths, and hashes. No gate trial is allowed.

## Fresh preflight and stop rules

Following exact-command review and explicit one-time release, run a read-only preflight first: host and architecture, current time/available memory/CPU affinity, no competing diagnostic process, unique paths/status absent, gate SHA, staged-file hashes/modes, pinned PRINT commit/modules, R 4.2.2/runtime and package availability, all required input paths, all six trusted artifact hashes, and the 44-GiB gate configuration. Any failure means stop before the gate call. Gate invocation consumes the single attempt, even if it fails. A timeout, R error, warning blocker, hash failure, changed original artifact, incomplete output or mismatch is retained as-is; no automatic retry or larger peak set.

## Result acceptance

L1 requires gate exit code, completion/diagnostic manifest, input and original-output hashes unchanged, 16 V5 comparisons and 14/17 event counts retained, all warnings attributed by replay context, and every anomalous coordinate linked to a known native mask. L2 remains blocked if a replay warning cannot be explained or any anomalous value is outside native exclusion. An all-masked result classifies only the current cache replay; it does not prove the historical V5 28 warnings are explained, establish accuracy/full-peak feasibility, or select a caller. The fixed PMA conversation must review the result package before any downstream stage.

## Fixed-PMA review result — REQUEST_CHANGES

The fixed PMA conversation reviewed exact PR #8 HEAD `ff7703e3e29d5acf5ce62c4974f91e15d0e945c7`, verified the eight-argument path contract and both staged-file hashes, but did not authorize any remote preflight, staging, read or run. It found four minimum repairs: (1) include the actual immutable gate argv parser/exec excerpt and SHA from an already authorized read-only inspection; the packet cannot infer arbitrary-argv support from the gate hash or historical `script ctrl print` calls; (2) bind the diagnostic to one CPU with `taskset` and verify single-thread BLAS/OpenMP settings, because `NSLOTS=1` is not a CPU cap; (3) state that an all-masked replay only classifies that replay and does not resolve the historical V5 warning set; and (4) synchronize the operative summary, which still had stale script/test hashes and warning-gate wording.

This audit revision applies items 3–4. Items 1–2 remain unresolved. The reviewer response says this review did not authorize remote access; ask the fixed PMA reviewer how to obtain the already-authorized read-only gate excerpt without violating the current no-remote-access condition. Do not execute, stage, inspect Argos inputs or contact the host in the meantime.

## Follow-up audit — 2026-10-20

The operative handoff now has the exact current diagnostic/helper/regression hashes. The replacement command requirements are explicit: verify and quote the immutable gate's argv parser/exec source, use `taskset` to bind the child to one verified online CPU, and retain single-thread BLAS/OpenMP variables. The prior command is superseded. Since the last reviewer response denied all remote read/preflight, request a narrowly scoped exception in the same fixed PMA project conversation for a read-only inspection of the gate file itself (SHA plus parser/exec excerpt only); no input, cache, process or environment inspection, staging, gate trial, or analysis is included. Await that decision before contacting Argos.
