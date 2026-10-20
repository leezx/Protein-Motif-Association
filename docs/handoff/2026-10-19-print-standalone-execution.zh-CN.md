# Step 4b PRINT 全峰集执行交接

## 目标与边界

本轮只在同一样本 K562 `ENCSR868FGK` 的完整原始 ENCODE ATAC IDR peak 区间上运行 PRINT，使用固定的两个尺度 `10,20`、16 个 CPU worker，输出原生逐位点 track 和事件 BED，并记录时间、CPU、内存、退出码、行数和哈希。本轮只评估计算时间/资源和输出规模，不排名准确度，不发现 motif，不运行其他 caller，不优化/C++ 移植，不触碰 Claude 负责的 ChIP BED6/PR #7，不合并 PR #8。

固定输入仍为 `ENCFF993BAP.bed.gz`：159,628 个区间、3,651,342 压缩字节、SHA256 `c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945`；区间长度和 150,359,120 bp，合并重叠后的唯一覆盖 55,114,693 bp。对应 BAM `ENCFF534DCE.bam`。不得用旧的 77,668 个 1-kb 窗口替代。

## 节点发现与现状

依用户要求查阅 `/Volumes/Stelligen_SSD/Stelligen/computingResource.md`。文档记录可直登 standalone 节点：`rcapps3`（72 核、1 TB、x86_64、K80）和 `rcapps8`（128 核、1 TB、T4）。PRINT 是 CPU 运算，本任务不使用 GPU。

- `rcapps8` 于 2026-10-19 22:59 EDT 有 453 GiB 可用、负载 0.15，但架构为 aarch64。共享环境的 R4.3.2 `Rscript` 为 x86-64，不能执行；系统 R 4.1.2 缺 `cladoRcpp`、`rhdf5`。本轮不在该机安装或修改环境。
- `rcapps3` 于 22:59 EDT 有 917 GiB 可用、72 核、负载 51.7。它与共享 beegfs 上的现有 PRINT/R/输入数据架构兼容。正式启动前须刷新 `uptime`、`free -h` 和允许 CPU 列表；若资源不足则暂停并报告。
- 已检查 `rcapps3` 与 `rcapps8` 的登录和系统资源。未提交 QSUB。

## 执行前门禁与拟定命令

当前 PR #8 `1664b565c7e52928b2d05f789e2887bcca05a3a7` 的 GPT 批准仅覆盖任务定义/文档，明确不授权计算。此更新必须推到同一 PR，并在固定 PMA 项目对话 `PMA｜固定阶段审核` 请求 exact-head 审核；只有当前完整 HEAD 明确 APPROVE 后才能运行 caller。用户已明确授权使用直接登录 standalone 节点；这覆盖旧文档中“不要用 standalone”的执行偏好。

在 `rcapps3` 运行前：

1. 确认 live PR HEAD 与本次审批一致；确认输入 BED/BAM、fragment 文件、runner 和 `print_shared` 模型/偏好文件存在且哈希符合已审数据清单。
2. 确认 x86_64 R 环境和依赖可用，特别是 worker 进程的 `R_LIBS` 包含 `/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib`，并用只读 R preflight 验证 `cladoRcpp`、`GenomicRanges`、`data.table`、`rhdf5`。
3. 将 PR 审核过的 `run_print.R` 单文件同步到仓库外的唯一临时执行目录，核验远端 SHA256；不得运行陈旧的 `/home/zz950/softwares/src/PRINT` 中旧 wrapper。
4. 选取 16 个当前允许的 CPU 核。保留原 `/home/zz950/PMA_fetch/pma_bg_gate_v2.sh` 的每进程 44-GiB `RLIMIT_AS` 与 CPU-only 环境，但该限制不是进程树总内存限制。
5. 启动单独 watchdog，每 2 秒读取主 R PID 及全部后代 `/proc/<pid>/smaps_rollup` 的 PSS 总和，写外部 status log；PSS ≥100 GiB 或 PID 树采样失败连续 3 次时对整组进程 TERM，宽限 60 秒后 KILL。总墙钟上限 24 h。若 watchdog 的覆盖范围/信号目标无法在启动前验证，fail closed、不运行。

拟运行调用（由经审查的外部 launcher 固化）：

```text
/usr/bin/time -v taskset -c <16-核列表> /home/zz950/PMA_fetch/pma_bg_gate_v2.sh BG_K562_PRINT_FULLPEAK_<RUNID> <external-launcher> print print
```

launcher 必须把 runner 的 `nCores` 设为 16、radii 设为 `10,20`，输出写到新的、仓库外 `.../processed/round1/runs_print_fullpeaks_<RUNID>/`，并在日志中记录 input/runner/model hashes、GNU time、每尺度 track/event 计数和哈希、PRINT timing TSV、watchdog PSS 峰值/终止原因。全过程不输出峰坐标到对话或仓库。任务正常退出后先核对两个尺度都有完整输出；失败保留所有日志，不自动重跑。

## 审核后状态

截至本交接写入时，PR #8 当前内容尚待本轮 exact-head GPT 审核；没有 PRINT 全峰集 caller 已启动。下一动作是推送并在固定 PMA 审核对话提交上面的执行范围，然后按审核决定执行。
