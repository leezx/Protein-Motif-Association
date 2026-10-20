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
3. 将 PR 审核过的 `run_print.R` 与监督 launcher 同步到仓库外的固定执行目录 `/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1/`，核验 SHA256；不得运行未固定的 `/home/zz950/softwares/src/PRINT` checkout。PRINT 源仓库干净 commit 为 `8dad7317c3a640454a191dba2acd138e6edc54ac`，四个 sourced R module SHA256：`utils.R` `8c20776317dd5a9207aeebb9dd084f9e4f0d5d80c1056f599c411fe696ecc8b7`；`getCounts.R` `2f54f1c2c6a8cd410ed102cc934679f14c977ef002b8c1abf50c12018212d495`；`getBias.R` `455b6ac5a33807d558399679d9947d29561d00fc7a7a7ffa2b8cc948e8f04615`；`getFootprints.R` `7944dfa194cdf1eeda3cdfa821dab7df45cf59d7aa36d74ae206f77fb7e0babd`。Frozen fragment SHA256 `238367780a1b7a2a24595a4259bdbe91cb8be439c2e5fda210831ad60d77544f`; bias HDF5 SHA256 `574140487a0a829c7a59735e0e7a64a3f3a227a7e5ceb8ea5f355f7cc3289402`; dispersion model SHA256 r10 `c0cd01806684784abc0cb6894e6cfcd0234704f88baf3045121a2b6e07737414`, r20 `1413478ee5dfef1655a419adf67ef18b503d7bcd4c82273c4c5c0f485cf2d0b3`。监督 launcher SHA256（当前版本）`e32eba2a39914c790e407f84c0fd70a56713ffa3a4f8c21242ece6c9d747ba03`；`run_print.R` SHA256 `cae788b22dfb8ffc6006bae168b356909b3082036faa4a73e853c496ce717abf`。
4. 选取 16 个当前允许的 CPU 核。保留原 `/home/zz950/PMA_fetch/pma_bg_gate_v2.sh` 的每进程 44-GiB `RLIMIT_AS` 与 CPU-only 环境，但该限制不是进程树总内存限制。
5. 执行仓库内 `scripts/04b_footprint/run_print_fullpeak_supervised.py`。它创建独立 session/process group，每 2 秒枚举该组 `/proc/<pid>/stat` 并汇总所有非 zombie 进程的 `smaps_rollup` PSS；达到 100 GiB 或采样失败连续 3 次，对整个 process group 发 TERM，等待 60 秒再 KILL。主进程退出后仍检查组内残留子进程并清理。100 GiB 是采样终止阈值而非硬限制，采样间隔及 TERM 宽限内可能越过阈值。总墙钟上限 24 h。若节点内核不提供 `smaps_rollup` 或 process group 范围不能核验，fail closed、不运行。

固定外部路径：

- launcher、监控日志、GNU time：`/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1/`
- 结果：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_fullpeak_rcapps3_20261020_v1/print{.r10.track.tsv.gz,.r10.native_events.bed,.r20.track.tsv.gz,.r20.native_events.bed,.timing.tsv}`
- gate 状态：`/home/zz950/PMA_fetch/pma_bg_pr8_20261019/BG_K562_PRINT_FULLPEAK_20261020_V1.{meta,status,stdout,stderr}`

固定调用（当前 launcher 在远端拷贝后核验 SHA；QSUB 不用）：

```text
nohup /home/zz950/PMA_fetch/pma_bg_gate_v2.sh BG_K562_PRINT_FULLPEAK_20261020_V1 /home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1/run_print_fullpeak_supervised.py print print </dev/null >/dev/null 2>&1 &
```

launcher 固定使用 16 个当前允许 CPU、`nCores=16`、radii `10,20`，并把所有结果/日志写到上述唯一仓库外目录。预检记录 BED/fragment/runner/PRINT module/bias/model hashes；GNU-time 与 watchdog PSS 分别保存；结束后逐文件统计输出字节、SHA256 和行数。全过程不输出峰坐标到对话或仓库。任务退出后核对两个尺度输出；失败保留所有日志，不自动重跑。

## 审核后状态

截至本交接写入时，PR #8 当前 HEAD 包含 watchdog 的实际实现，exact-head GPT 审核尚待完成；没有 PRINT 全峰集 caller 已启动。下一动作是推送当前完整文件和同步修正的 PR body，在固定 PMA 审核对话提交 exact-head review，然后按审核决定执行。
