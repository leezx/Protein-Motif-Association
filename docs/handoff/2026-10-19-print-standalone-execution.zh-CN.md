# Step 4b PRINT 全峰集执行交接

## 目标与边界

本轮只在同一样本 K562 `ENCSR868FGK` 的完整原始 ENCODE ATAC IDR peak 区间上运行 PRINT，使用固定的两个尺度 `10,20`、16 个 CPU worker，输出原生逐位点 track 和事件 BED，并记录时间、CPU、内存、退出码、行数和哈希。本轮只评估计算时间/资源和输出规模，不排名准确度，不发现 motif，不运行其他 caller，不优化/C++ 移植，不触碰 Claude 负责的 ChIP BED6/PR #7，不合并 PR #8。

固定输入仍为 `ENCFF993BAP.bed.gz`：159,628 个区间、3,651,342 压缩字节、SHA256 `c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945`；区间长度和 150,359,120 bp，合并重叠后的唯一覆盖 55,114,693 bp。对应 BAM `ENCFF534DCE.bam`。不得用旧的 77,668 个 1-kb 窗口替代。

## 节点发现与现状

依用户要求查阅 `/Volumes/Stelligen_SSD/Stelligen/computingResource.md`。文档记录可直登 standalone 节点：`rcapps3`（72 核、1 TB、x86_64、K80）和 `rcapps8`（128 核、1 TB、T4）。PRINT 是 CPU 运算，本任务不使用 GPU。

- `rcapps8` 于 2026-10-19 22:59 EDT 有 453 GiB 可用、负载 0.15，但架构为 aarch64。共享 R4.3.2 `Rscript` 二进制为 x86-64，不能执行；系统 R 4.1.2 缺 `cladoRcpp`、`rhdf5`。本轮不在该机安装或修改环境。
- `rcapps3` 于 23:02 EDT 有 917 GiB 可用、72 核、负载 51.1；R 4.2.2 与 `cladoRcpp`、`GenomicRanges`、`data.table`、`rhdf5` 通过只读 namespace 检查，固定输出目录未存在。正式启动前刷新资源；若不足则暂停。
- 已检查 `rcapps3` 与 `rcapps8` 的登录和系统资源。未提交 QSUB。

## 执行前门禁与拟定命令

之前 PR #8 HEAD `1664b565c7e52928b2d05f789e2887bcca05a3a7` 的 GPT 批准仅覆盖任务定义/文档，明确不授权计算。随后用户明确授权在 QSUB 不可用时直登 standalone 节点；因此已在同一 PR 更新为 rcapps3 方案。当前 launcher、路径、模型和输入 hash 的完整 execution scope 须先获固定 PMA 对话 `PMA｜固定阶段审核` exact-head APPROVE；只有当前完整 HEAD 获 APPROVE 后才能运行 caller。

在 `rcapps3` 运行前：

1. 确认 live PR HEAD 与本次审批一致；确认输入 BED/BAM、fragment 文件、runner 和 `print_shared` 模型/偏好文件存在且哈希符合已审数据清单。
2. 确认 x86_64 R 环境和依赖可用，特别是 worker 进程的 `R_LIBS` 包含 `/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib`，并用只读 R preflight 验证 `cladoRcpp`、`GenomicRanges`、`data.table`、`rhdf5`。
3. 将 PR 审核过的 `run_print.R` 与监督 launcher 同步到仓库外的固定执行目录 `/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1/`，核验 SHA256；不得运行未固定的 `/home/zz950/softwares/src/PRINT` checkout。PRINT 源仓库干净 commit 为 `8dad7317c3a640454a191dba2acd138e6edc54ac`，四个 sourced R module SHA256：`utils.R` `8c20776317dd5a9207aeebb9dd084f9e4f0d5d80c1056f599c411fe696ecc8b7`；`getCounts.R` `2f54f1c2c6a8cd410ed102cc934679f14c977ef002b8c1abf50c12018212d495`；`getBias.R` `455b6ac5a33807d558399679d9947d29561d00fc7a7a7ffa2b8cc948e8f04615`；`getFootprints.R` `7944dfa194cdf1eeda3cdfa821dab7df45cf59d7aa36d74ae206f77fb7e0babd`。Frozen fragment SHA256 `238367780a1b7a2a24595a4259bdbe91cb8be439c2e5fda210831ad60d77544f`; bias HDF5 SHA256 `574140487a0a829c7a59735e0e7a64a3f3a227a7e5ceb8ea5f355f7cc3289402`; dispersion model SHA256 r10 `c0cd01806684784abc0cb6894e6cfcd0234704f88baf3045121a2b6e07737414`, r20 `1413478ee5dfef1655a419adf67ef18b503d7bcd4c82273c4c5c0f485cf2d0b3`。监督 launcher SHA256 `8a48cbdbf31d8f1ab7cd36ec2d8969728a36e5fc4aad164e60e66563b69cf657`；`run_print.R` SHA256 `3b658a2021d13278f9b5e46e7aba2426613a1a53d71d52bd7fd6ee617489a966`。runner 在没有 native event 时写零字节 BED 文件（合法）；无 score 数据行会导致输出验收失败。
4. 选取 16 个当前允许的 CPU 核。保留原 `/home/zz950/PMA_fetch/pma_bg_gate_v2.sh` 的每进程 44-GiB `RLIMIT_AS` 与 CPU-only 环境，但该限制不是进程树总内存限制。
5. **当前 launcher 需要新 HEAD 审核。** Fresh preflight 于 2026-10-19 23:25 EDT 确认实际 `rcapps3` 主机没有 `/proc/self/smaps_rollup`，因此已批准 launcher 在启动前 fail closed；只读检查确认 `/proc/self/smaps` 可读且有 `Pss:` 字段。固定 PMA 对话的技术建议是逐 PID 完整读取 `/proc/<pid>/smaps` 至 EOF，求和所有合法非负 `Pss: <n> kB` 行。这保留 PSS 字段口径，但逐映射取整和快照非原子性意味着不宣称严格数值/时序等价。采样在独立可终止 helper 中运行，1.5 秒截止时间、2 秒固定单调时钟节拍、无重叠；超时、截断、缺失/格式错误 PSS、存活成员不可读或错过节拍均记失败，旧值或部分值不重置连续失败计数；连续 3 次失败 fail closed。helper 必须被 KILL、wait/reap 后才可进入下一次采样。固定 PMA 对话复审该实现后又指出：helper 的 KILL 后 `communicate()` 无回收时限，且成功但迟到的样本仍可能有效。最新修复在 `finally` 中将 KILL/reap 限为 0.5 秒；若仍未回收，立即终止 PRINT 进程组、再次尝试有界回收、记日志，并禁止后续采样。耗时超过 1.5 秒或错过 2 秒节拍的值作废、不更新峰值；内核不可中断状态下的 helper 退出无法由用户态保证，因此需要关闭 caller。当前 launcher SHA256 为 `8a48cbdbf31d8f1ab7cd36ec2d8969728a36e5fc4aad164e60e66563b69cf657`，新 HEAD 仍待 exact-head review。
6. 通过当前 HEAD exact-head approval 后，才进行新鲜资源和输入哈希预检、复制审核过的 runner/launcher 并核验哈希；未通过任一项即停止。其余过程保持：独立 session/process group；达到 100 GiB、24 h、TERM/INT、监督器异常或 caller 退出后发现残留组成员时，对受监控组发 TERM，等待 60 秒再 KILL，并 wait/reap 主 caller。监控仅覆盖仍留在该进程组的成员。100 GiB 是采样终止阈值，不是硬限制，采样间隔和 TERM 宽限内可能越过；外层 gate 的 44-GiB `RLIMIT_AS` 是每进程限制。

固定外部路径：

- launcher、监控日志、GNU time：`/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1/`
- 结果：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_fullpeak_rcapps3_20261020_v1/print{.r10.track.tsv.gz,.r10.native_events.bed,.r20.track.tsv.gz,.r20.native_events.bed,.timing.tsv}`
- gate 状态：`/home/zz950/PMA_fetch/pma_bg_pr8_20261019/BG_K562_PRINT_FULLPEAK_20261020_V1.{meta,status,stdout,stderr}`

固定调用（当前 launcher 在远端拷贝后核验 SHA；QSUB 不用；仅新 HEAD 获批且 fresh preflight 全通过后执行）：

```text
nohup /home/zz950/PMA_fetch/pma_bg_gate_v2.sh BG_K562_PRINT_FULLPEAK_20261020_V1 /home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1/run_print_fullpeak_supervised.py print print </dev/null >/dev/null 2>&1 &
```

launcher 固定使用 16 个当前允许 CPU、`nCores=16`、radii `10,20`，并把所有结果/日志写到上述唯一仓库外目录。预检记录 BED/fragment/runner/PRINT module/bias/model hashes；GNU-time 与 watchdog PSS 分别保存；结束后逐文件统计输出字节、SHA256 和行数。要求两个 score track 均有至少一条数据行、timing TSV 包含 bias/counts/footprint_r10/footprint_r20，且原生事件文件存在（允许合法空文件）；验证的是必需文件有效、score 数据行和四个 finite/nonnegative timing stages，不证明完整峰区间覆盖；非空 event BED 逐行验证4列及坐标/score有效，空文件合法。全过程不输出峰坐标到对话或仓库。失败保留所有日志，不自动重跑。

## 审核后状态

GPT 对上一 tip 的 exact-head 审核指出监督器异常/信号清理、进程枚举失败处理和 track/timing 输出判据三项问题；这些已在同一 PR 修复。对 live HEAD 6f76e0a 的复审发现一项尾部异常路径：若 watchdog 日志写入失败，terminate_group 可能跳过信号。现已改为日志 best-effort，组成员轮询异常也不能跳过最终 KILL；新 launcher SHA256 为 ecd83823dfde5d306f5f32ece3c3d9379d7c63789fe734c9d0eb8f122a2e43fb。PR body/handoff/worklog 已同步，等待新 tip 在固定 PMA 对话 exact-head re-review。此前不复制 launcher 到 Argos、不启动 PRINT。没有 PRINT 全峰集 caller 已启动。
