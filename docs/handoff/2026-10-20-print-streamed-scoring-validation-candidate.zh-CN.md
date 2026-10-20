# PRINT 持久评分调度与 8-peak 验收结果

## 2026-10-20 14:16 EDT — pnorm warning 定位候选（仅本地实现）

用户授权修改本地 PRINT 工作流源码。固定 `PMA｜固定阶段审核` 对 PR #8 HEAD
`2026c22658d13e3698e71af4ba6cd8051fa5170b` 的决定仅批准诊断方案，不批准 Argos 执行。V5
单次运行授权已消耗。

新候选 `scripts/04b_footprint/diagnose_print_pnorm.R` 只读取现有 V5 8 峰 count chunk、bias
group RDS、10/20-bp dispersion models、validated score tracks/event BED、V5 summary/completion
和固定 PRINT 源模块。它在隔离环境中包裹原生 `pnorm`，记录 q、预测均值/SD、p 值、警告、peak
行/坐标、半径、flank、PRINT 内部 pseudobulk/cell-type 两条路径，以及异常位置是否被原生
`(leftTotal < 1) | (rightTotal < 1)` mask 排除。计数、bias、模型不重建；不写回任何缓存、轨道或
事件文件；不钳制 SD、不屏蔽警告。输入、PRINT 源、summary/completion 和原结果均要求运行前后
SHA 不变，且轨道与事件哈希必须等于 V5 的固定值。所有 16 个既有 peak-radius 对照及 14/17
事件数均需保持；若警告数与 V5 记录的 28 不同，或任何异常不被 mask 排除，报告仍为
BLOCKED，不能扩大到全峰或作准确度结论。

本地 regression 使用合成 pnorm 向量，覆盖正 SD、负 SD 和 NaN 输入；验证原生 pnorm 返回值
逐元素一致、警告仍出现、两条内部评分路径均被捕获，并将一个异常映射到未排除位置、另一个映射
到零覆盖 mask。命令 `Rscript tests/test_print_pnorm_diagnostic.R` 通过；R 解析和
`git diff --check` 通过。候选 SHA-256：脚本
`c5f7f6964de840408a1bcdb2e6ca1435c463411fb6287e7b28c59b46b72a5c2c`；回归
`755a18f1d7427708cc821c5ab07b88c26ffdee9179de1861acabc72629c2ff5f`。没有本地 V5 生物数据缓存，
因此尚未对真实 V5 输入运行诊断。

下一步仅在 PR #8 同一分支发布该实现和审计，并在固定 PMA 对话请求 exact-head 实现审核。即使
实现审核通过，仍需单独审核精确命令/资源并取得一次性运行放行，随后重新预检；此记录不授权
Argos 读取/暂存/执行、全峰扩展、环境修改、准确度排名或 PR 合并。

## 2026-10-20 14:20 EDT — PR #8 candidate published

上述诊断代码、合成回归和 audit 更新已作为 commit
`358328587c159f197d28022fb0ae681ef449a4d7` 推送到既有 PR #8 分支。fetch 后的 origin ref、GitHub
branch API 和 PR API 一致指向该提交，PR OPEN、未合并。PR body 已同步并请求仅实现审核。此更新没有
连接/读取 Argos、暂存脚本或执行诊断；该操作仍需当前 exact-head 实现审查通过、对确切命令/资源的
后续审查及单独的一次性运行放行。

时间：2026-10-20 13:06 EDT

范围：PMA Step 4b footprint，仅 PR #8。ChIP BED6/PR #7 由 Claude 负责。

## V5 实际运行结果（2026-10-20 14:01 EDT）

固定 PMA 项目对话对 PR #8 exact HEAD `dce3d4e610644dce7545837d1af9add41cf39df2` 明确批准一次 V5 8-peak gate。远端只读预检、输入/模型/PRINT/gate 哈希、依赖、资源与唯一目录检查通过；五个 staged 文件的 SHA 与 Git mode 全部一致。V5 gate 于 `2026-10-20T14:01:53-04:00` EXIT=0。V5 单次授权已消耗，不能重跑。

结果：8个原始冻结 K562 peak（来自159,628行peak BED；2条染色体；宽度1,042–1,977 bp），16 workers，强制3/3/2 chunks，r10/r20。streamed结果与 legacy 路径16/16 peak-radius一致；direct comparison 16/16 bias exact-match。r10和r20各有12,795个通过验证的有限分数行；native event BED 分别14和17行。缺失输出、计时阶段和验证错误均为0。该结果证明8个peak上的代码/调用集成和与legacy评分对象等价；不测独立准确度，不证明全峰调用可完成，也不能据此选工具。

资源：gate至完成452.432秒（7分32秒），其中监督器预检66.596秒；PRINT caller wall 384.589秒（GNU time 6分24秒），172.04秒user CPU + 25.79秒system CPU。GNU time 的51% CPU表示平均约0.51个CPU核，即16核worker/affinity容量的约3.2%，不是8.2核。GNU time最大子进程RSS 17,921,552 KiB；采样进程组VmRSS峰值17,922,204 KiB（约17.09 GiB）。单进程 `RLIMIT_AS` 为44 GiB。40-GiB VmRSS采样软停止未触发；该采样不是硬聚合内存上限。总预算30分钟。

调用日志有28条 `pnorm(...): NaNs produced` 警告。监督器对轨道有限分数、tracks、event BED、16组比较、required timing stages和completion marker均验证通过，但警告来源/科学影响仍未查清。不得屏蔽警告，也不得据当前smoke作准确度结论。

外部证据仍保存在 Argos/DATA，不复制进仓库：证据目录 `/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/`；gate状态 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/BG_K562_PRINT_STREAM_VALIDATION_20261020_V5.status`；结果 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/`。`summary.json` SHA-256 `51e7d2292b4baa7d2e4851d14b7acddb3ab0974f73ca4e88d11e1d79c51d71b5`；`smoke_completion.json` `f6789a5d1f5ebc5c65467bf6d3287cbcac5172ce020eedfda2414d91035b7a0a`；watchdog `ea1caf0b3c297c2cbb5888e0965d2cbe534c3d299e09894e5af055202e6b95bc`；caller stdout `83866e658a02332e28049275bee38ca645c4e3e41aa904402165a90a266d3e8f`；GNU time `0379b81eea46f43b9fd94ebd058ff72c24c924860725595b897f3bc6985882dd`；gate status `2d5fef2cde71051b672a6804ba17e0698afca83beaad192ab5f90463e1bff856`。r10/r20 track SHA `4ee07f188d4c0b43ea813fa2930b3da9ea41e2e2b2f83cf0d1aa70ff2bfda72b` / `b54254670978d006781af4fb228ff744c9fbac2b09afb2fc07e915801778c447`；native events SHA `30aedcd7843e947164290335cdfaff61b33338f7b44e7c6ebb887394d4fa66c8` / `b18d8916b5df3ade276e1f6f50628a9b82bf34b6b4741acb6ae552dbf4b8ad72`。

Quick stage review: L1 PASS for this 8-row implementation-validation deliverable; L2 BLOCKED for biological accuracy/full-peak suitability; direction ON TRACK; real progress for live Argos PRINT integration and exact equivalence at this sample size; trust usable with limits. Fixed-PMA review returned REQUEST_CHANGES solely because the audit overstated CPU use; the 28 pnorm NaN warnings also require diagnosis before scaling or biological interpretation. Candidate next experiment: use the existing 8-peak count/bias/model cache to localize pnorm inputs by path, peak, radius, and flank, without rebuilding counts or expanding the peak set. This requires separate fixed-PMA review and explicit one-shot approval. V5 approval is consumed and does not authorize another run, a 64/full-peak run, accuracy testing, environment changes, or merge.

## V4 实际运行结果（2026-10-20 13:37 EDT）

固定 PMA 对话对 PR #8 exact HEAD `9b048058903c24dbd1c39783084718e5b134a36c` 明确批准一次 V4 8-peak gate。预检、宿主资源、依赖、输入/模型/PRINT/gate 哈希与唯一输出路径均通过；五个 staged 文件哈希及执行权限匹配。按批准的命令调用一次后，gate 于 `2026-10-20T13:35:25-04:00` 返回 `EXIT=1`，V4 额度已消耗，禁止重试。

8峰选择成功；4个 bias group 成功写出；disk-backed count tensor完成，counts stage约3.171123分钟。随后 legacy oracle 尚未进入评分即报错：

```text
Error in get("regionFootprintScoring", envir = envir, inherits = FALSE) :
  object 'regionFootprintScoring' not found
Calls: with_print_region_scorer -> get -> get
Execution halted
```

故障定位为本地补丁假定 `regionFootprintScoring` 绑定直接存在于 `environment(getFootprints)`；该环境没有该局部绑定。评分 dispatch 未发生。没有 r10/r20 track、native-event BED、timing TSV，也没有 footprint 或准确度结果。外部结果目录仅有选择记录、bias-group临时对象和count tensor。清理后无V4 gate/supervisor/PRINT进程残留。

资源/时间：caller wall 208.623秒；GNU time 3:26.32，用户CPU 155.24秒、系统CPU 19.74秒、84% CPU，最大子进程RSS 17,921,156 KiB。采样进程组VmRSS峰值17,921,796 KiB（约17.09 GiB），低于40-GiB采样软停止；该值不是硬聚合内存上限。结果不支持全峰耗时或准确度外推。

外部证据目录：`/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v4/`；gate记录：`/home/zz950/PMA_fetch/pma_bg_pr8_20261019/BG_K562_PRINT_STREAM_VALIDATION_20261020_V4.status`；外部输出：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v4/`。摘要SHA-256：summary `467105ee87da5c03ee397071f8292be8600d87bedf00c1b4203c2177b6d57bdf`，watchdog `2d4a3e31f9eeedf39283789ad1b0050bfeea67292e13195408293907f6781e3e`，caller log `a696d30f0eea9e0e9e39de11b119524f494c4c604311c3848278bc5c5d5df12a`，GNU-time log `c6dca09a159cedf9aed274b0fce9a647141d6ac918cfa4cd1291d3dba8f2900d`，selection `4cb65107b73d8ac17a372bfb0425fe98ba3a080aa812f344971a2d0b62c4a017`，gate status `7aa62cebf20a541e5c933251dd8ac0fd0bc99b6f2629e2d5329e282e653975a1`。外部数据和结果未复制入仓库。

阶段结论：L1 footprint交付FAIL（预检和清理PASS）；L2评分语义等价BLOCKED/UNVERIFIED-critical；无准确度结论；L3 ON TRACK/PARTIAL。固定PMA对话正在进行故障诊断。V4不得重跑。未来任何本地修复需在同一PR审核新的exact HEAD，并取得新的明确one-shot Argos授权。

## 2026-10-20 13:42 EDT — GPT diagnosis and local V5 repair candidate

固定 PMA 对话诊断：错误来自把 S4 generic 的环境误当作 `regionFootprintScoring` 的词法绑定环境；这不代表 PRINT 原生 scorer 缺失。按建议仅在同一 PR 修改本地源码：通过 `methods::selectMethod()` 选出具体 `getFootprints` 方法，从方法词法链找到 `get_footprints`，再从 helper 词法链找到实际 scorer 绑定所有者。替换前要求该绑定正是预期 bulk-safe 包装器，且环境/绑定未锁定、不是 active binding；只临时替换实际所有者中的绑定，并由 `on.exit` 在成功或错误时恢复。缺失、错误、锁定、active binding 均 fail closed，不解锁 namespace、不用 `assignInNamespace`。

回归测试使用 generic、method、helper、scorer 分属不同环境的 S4 fixture；验证解析到正确 owner、无 shadow binding、原生 scorer 调用后恢复 wrapper、异常后恢复 wrapper，且锁定/active/missing/wrong binding 均拒绝。完整本地套件现通过：R 单测及解析、三个 Python wrapper 编译、PRINT speed supervisor、8-peak selector、smoke deadline/path/hash、runner contract fixtures、`git diff --check`。哈希：`run_print.R` `f2059c1677d9efda31d175b7f326a1bdae18a01fb4f4224ed3eab86cde985042`；`print_variable_width.R` `9dee1d7588e7a47a9449ae88a61710c4f16dd4b6f40cef93886b6421ef1f362b`；outer wrapper `8ed17c3ad8e01be0c08b59c3f1749a5e756b4832e95bbdb46c992bd835a1763c`；base supervisor `af29005f2ec0101100303be50227fe0f94a13d9cb25cb5a07a8a6159efaa44c0`；selector `7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856`。

V4 的单次授权已消耗且禁止重试。现有一次性包装器已改为独立 V5 ID 与全新 code/root/output 路径，属于待审代码候选，不等于运行授权。当前未远程 staging、未读取 Argos 输入、未调用 gate。下一步在固定 PMA 对话审核提交后的 exact PR head，并单独明确是否放行一次新的 V5 8-peak 验收。

V5 review packet：run `BG_K562_PRINT_STREAM_VALIDATION_20261020_V5`；code stage `/home/zz950/PMA_fetch/pma_print_stream_validation_code_20261020_v5`；evidence root `/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5`；DATA output `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5`。五个执行文件 SHA-256：selector `7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856`；runner `f2059c1677d9efda31d175b7f326a1bdae18a01fb4f4224ed3eab86cde985042`；helper `9dee1d7588e7a47a9449ae88a61710c4f16dd4b6f40cef93886b6421ef1f362b`；base supervisor `af29005f2ec0101100303be50227fe0f94a13d9cb25cb5a07a8a6159efaa44c0`；outer V5 wrapper `8ed17c3ad8e01be0c08b59c3f1749a5e756b4832e95bbdb46c992bd835a1763c`。唯一候选命令：

```sh
PRINT_SMOKE_EXPECTED_SHA256=8ed17c3ad8e01be0c08b59c3f1749a5e756b4832e95bbdb46c992bd835a1763c bash /home/zz950/PMA_fetch/pma_bg_gate_v2.sh BG_K562_PRINT_STREAM_VALIDATION_20261020_V5 /home/zz950/PMA_fetch/pma_print_stream_validation_code_20261020_v5/run_print_integration_smoke_supervised.py ctrl print
```

该提议只针对8个原始peak、16 workers、3/3/2、r10/r20、CPU-only、30分钟总预算、44-GiB每进程RLIMIT_AS及40-GiB采样RSS软停止，复用已核验fragments。必须另由固定PMA对话针对最终 exact HEAD 明确批准此 V5 命令一次；当前没有远程执行授权。

固定 PMA 对 PR #8 HEAD `52d9c325ba648ed7d36afffeb70c6bfadaa4282f` 的第一次 V5 复审返回 `REQUEST_CHANGES`：仅发现文档/命令中 outer wrapper SHA 与真实文件不符，运行会被自身 SHA 检查拒绝。reviewer 确认词法 owner 修复无新增代码 blocker、其他四个执行文件哈希相符。已按本地文件与 GitHub blob 字节核对更正为上述 SHA，并重跑 smoke deadline/hash、PRINT R 回归/解析、Python 编译、speed supervisor、selector、runner contract、`git diff --check`，全部通过。更正需推送后在固定 PMA 对话复审新 exact HEAD；V5 尚未 staging/运行。

## 当前状态

用户授权修改本地 PRINT 源码。固定 `PMA｜固定阶段审核` 对话建议：保留 PRINT 原生计数/评分语义，实现持久评分 worker 调度后，先用 8 个原始 peak 做一次实现验收。该答复是技术建议，不是当前代码 exact-head 审核或 Argos 运行许可。

此前 64-peak、2-worker 的 PRINT V2 一次运行在 30 分钟预算时退出 124，caller 已运行 1,710.18 秒；采样进程组 RSS 峰值约 17.09 GiB；105 次评分调用完成、106 次开始。没有完整 track、event BED 或 timing TSV。该运行不支持准确度或全峰时间推断。V1/V2 均已消耗，不得重试。

## 本次本地候选改动

- `run_print.R` 保留原生 `getCountTensor()`，生产路径使用其 `returnCombined=FALSE` 磁盘分块 count tensor，不重新扫描/转换 fragments 文件。
- 评分按原始 BED 顺序分块：最多 500 个峰或累计 1,000,000 bp，先到者切分；单个超长峰完整处理。
- 父进程逐批读取 native count chunk 和 HDF5 bias slice；不向 workers 广播整个 count tensor、bias HDF5 handle 或全染色体 bias。
- 建立一个 16-worker PSOCK 评分池并跨块复用；每个 worker 任务处理一个原始 peak 的 r10/r20 两尺度。
- 使用 pinned `regionFootprintScoring()` 的原公式，显式 `scoreType="pval"`、`flankRadius=radius`、原始区间、count、bias、cell/group label 和返回设置。
- 单 bulk 组时 PRINT 原 scorer 内部 `sapply()` 会丢掉 singleton 维度。兼容包装只在 `sapply()` 恰有一项且结果为向量时补回一列矩阵，并给字符组标签列名；多组行为保持不变。函数公式不改。
- 逐峰检查位置×1组矩阵形状、完整原始宽度和轨道坐标；每个完整 chunk 的 track/event part 原子写出，并逐 chunk 保存 row/interval/hash manifest。最终两尺度先分别通过行数、part SHA 与 gzip 完整性验证，再发布最终文件；最后生成 `.complete.tsv`。
- V4 实现验收固定原有 8 个 peak，16 workers、r10/r20、强制 3/3/2 chunk，和旧分组 `getFootprints()` caller 路径逐峰比较 16 个 peak-radius 结果；最终 gzip track 和 event BED 重读后再次核对坐标及数值。V4 不代表全峰结果或准确度排名。

## 验证证据

本地通过：

- R parser：`print_variable_width.R` 与 `run_print.R`。
- `Rscript tests/test_print_variable_width.R`：原始顺序、3/3/2 分块、500 峰/1 Mb 双上限、超长单峰、singleton bulk matrix、多组路径不变、duplicate rows、空 event BED、part hashes/行数及 completion marker。
- `python3 -m py_compile`：PRINT wrappers 与监督测试。
- `python3 tests/test_print_speed64_supervisor.py`。
- `python3 tests/test_select_print_integration_smoke.py`。
- `python3 tests/test_print_smoke_deadline.py`。
- `bash tests/test_step4b_runner_contract.sh`。
- `git diff --check`。

contract test 中的 `BAM_CONVERSION_FAIL` / `BAM_PREP_FAIL` 是预期失败分支，最终 fixture 显示 PASS。Mac 本地 R 缺少 `hdf5r`、`survcomp`；未在 Mac 处理 ATAC 数据，也未运行 PRINT S4/PSOCK caller。故真实 HDF5、远程依赖与 scorer 等价性仍未验证。

候选源码 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `scripts/04b_footprint/run_print.R` | `f388b705d021862ff99e45cda576c43194b3234fc457b2afc79308f49f135c31` |
| `scripts/04b_footprint/print_variable_width.R` | `6657838e9e1d95ff08124b95fc78da9aae266ddce5b83e255c59d4d5ad8069b0` |
| `scripts/04b_footprint/run_print_fullpeak_supervised.py` | `af29005f2ec0101100303be50227fe0f94a13d9cb25cb5a07a8a6159efaa44c0` |
| `scripts/04b_footprint/run_print_integration_smoke_supervised.py` | `34f3d550da0ca74e2f1d4f5c0b03d81dcd3a2000e0ce904b54caeb9e3d5a0ea5` |
| `scripts/04b_footprint/select_print_integration_smoke.py` | `7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856` |

## 唯一下一步与边界

代码提交 `d60ca250d53318c2b2232ddeb01b330687d6499d` 与后续审计提交已推送到同一分支；PR #8 OPEN、未合并。V4 候选经过后续 review repair，具体情况见下方。

V4 固定：16 workers；r10/r20；30 分钟端到端执行预算；每进程 44 GiB `RLIMIT_AS`；采样进程组 40 GiB RSS soft-stop（不是硬 aggregate cap）；CPU-only；复用既有 fragment file。运行只提供实现/计时/资源证据，不测准确度，不授权全峰、不改环境、不合并。

### Review-task 状态

- L1：本地静态/合同验证 PASS；真实 Argos caller 集成未验证。
- L2：bulk singleton 维度修复和 native scorer 语义需 8-peak 实测，当前 UNVERIFIED-critical；准确度不在此步骤测。
- L3：用户方向仍是从 bulk ATAC peak 内调用 motif-free PRINT footprint；当前没有新 footprint 输出，进展是候选实现准备完毕。
- Trust：本地验证高；真实运行正确性和全峰资源推断目前低/未建立。

## 2026-10-20 13:19 EDT — 修复固定 PMA 对 V4 候选的两项 review finding

固定 `PMA｜固定阶段审核` 对 exact HEAD `8b60f31c480736046ec62c9cc85de81a819d9d63` 给出
`REQUEST_CHANGES`。第一项指出原 `footprint_r10/r20` 实际计的是 scorer 已完成后的轨道/事件整理与分块写出；第二项指出旧分组
`getFootprints()` oracle 在执行前已被全局替换为 bulk-safe scorer，因而不独立。

同 PR 最小修订：

- 在 `parLapplyLB()` 周围单独累计联合 `r10+r20` 评分派发墙钟，字段为
  `score_dispatch_r10_r20`；各尺度分块表构造、part 写出/哈希字段改为
  `output_materialization_r10/r20`。`pipeline_wall_through_validation_including_legacy_oracle`
  明确包含旧路径对照成本；外层 watchdog 的 caller wall 是独立总运行时间。
- 保存源自 pinned PRINT 的未包装 scorer。旧 `getFootprints()` 路径临时在其词法环境绑定原 scorer，
  并通过 `on.exit` 在成功和异常时恢复 bulk-safe worker scorer。新 worker 继续使用包装版。
- 回归 fixture 断言 oracle 使用 native scorer，并在正常及错误返回后恢复包装器。监督器计时门槛改成
  要求新的联合评分派发与输出物化/发布字段。

本地重新运行：R 测试/解析、两个监督器 Python 编译、PRINT speed supervisor 测试、8-peak selector
测试、deadline 测试、runner contract fixtures 与 `git diff --check` 均通过。contract fixture 输出的
`BAM_CONVERSION_FAIL` / `BAM_PREP_FAIL` 是其预期负向分支，最终 PASS。真实 HDF5/S4/PSOCK 路径仍未验证。
未访问 Argos、未 staging、未调用 gate。本修订后仍需推送，并在同一固定 PMA 对话复审新 exact HEAD；
旧的 V4 单次提议不视作批准，需新的明确放行才可运行。

计时监督器现在接受两种明确的 runner pipeline wall 字段（常规路径和包含 oracle 的验证路径），并强制
检查联合评分派发字段及两个尺度的输出物化/发布字段；对应单元测试验证两种合法形式和缺失评分字段。

2026-10-20 13:23 EDT：同 PR 代码修复提交 `ae0445632b253b33fd2339dfe2ba8abc8fb5a1c8` 已推送；`git ls-remote` 与 GitHub API 均确认它是 PR #8 当时 live head，PR OPEN、未合并。旧 V4 审核请求对应父提交 `8b60f31c...`，收到 REQUEST_CHANGES 后已失效。下一步同步最终 Worklog/handoff/PR body 后，必须在固定 PMA 对话请求新 exact-head 审查。无 Argos staging、访问或运行。

## 2026-10-20 14:25 EDT — 固定 PMA 对诊断实现的 REQUEST_CHANGES 与同 PR 修订

固定 `PMA｜固定阶段审核` 对 PR #8 exact HEAD `a6803335ca297cfc499bc168938a40d901395477` 做代码/测试审核，结论 `REQUEST_CHANGES`，L1 有三项：

1. 无法定位的 warning 会形成 NA 占位，而旧汇总只数 mask 为 FALSE 的记录，可能把未知位置误报为全部已 mask。现改为未知 mask、无元素定位的 warning、未知 warning 类别均保持 blocked；只有当前回放每条异常均能定位且明确落在 native zero-coverage mask 时，当前回放异常门才可通过。
2. 两轮串行 native replay 的总数不能证明与 V5 中 legacy/direct/streamed 多上下文执行产生的历史 28 条 warning 一一对应。现按 pass、path、peak、radius、flank逐行报告；历史 28 仅作为参考值，不作相等通过条件。即使当前回放异常全被 mask，scale-up gate 仍为 `BLOCKED_HISTORICAL_CONTEXT_NOT_REPRODUCED`。
3. 旧版在读完部分缓存后才计算基线，且异常退出不做后置校验。现将 count/bias/model/evidence/output、辅助文件和 pinned PRINT source 的哈希基线前移到 `source/readRDS/fread` 之前。summary/completion、track、event 保留已有可信历史 SHA；未有历史 pin 的 count/bias/model 缓存仅记录为“诊断开始时冻结”，不宣称是原 V5 字节。外层 guard 在成功或错误退出后都复核哈希；若主任务和完整性核验同时失败，错误消息保留两者。

新增回归覆盖 unknown/false mask、unlocated/unclassified warning、历史 28 总数不能解锁 gate、已有输出目录拒绝、主错误及输入变化同时发生时保留双错误。`Rscript tests/test_print_pnorm_diagnostic.R` 通过；测试中四条 `NaNs produced` warning 照原样显示。R parse 和 `git diff --check` 通过。候选哈希：诊断脚本 `3d883552675d765010fb08663d011ef0ee285c13c106fdc5ab4617488055aca0`；回归 `98c3139f3ec6c24d70987a25788383d66cd220c9f1eb023b95cc266e537814b6`。

本机没有 V5 的 Argos cache，因此未做真实数据诊断。此修订尚待提交并在同一 PR 发布后，于固定 PMA 对话做新 exact-head 实现审核。此前批准只针对诊断提案，不是执行许可；仍需另行审核精确命令/资源并另获一次性运行授权。当前没有 Argos 访问、staging、读取、运行、扩峰、准确度结论、环境更改或合并。
