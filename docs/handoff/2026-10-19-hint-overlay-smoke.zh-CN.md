# Step 4b HINT 隔离环境与真实小样本调用

时间：2026-10-19 00:19 EDT。分支：`task_20261019_hint_overlay_smoke`，基于已合并 PR #4 的 `step4b-atac-footprinting` 头 `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`。本 PR 只修复 HINT 分块输出目录；所有包、BAM、BED 和结果均在仓库外。

## 目标与证据

现有 `pmafp` 内 RGT/HINT 1.0.2 的 CLI 因 NumPy 2.4.6 缺少 `numpy.mat` 而失败。Argos 上新建 `/home/zz950/PMA_fetch/pma_hint_overlay_v1`，通过 `venv --system-site-packages` 读取原 `pmafp` 包，仅在 overlay 内安装 NumPy 1.26.4 和 SciPy 1.11.4。两个 Linux CPython 3.11 manylinux2014 wheels 的 SHA-256 分别为 `666dbfb6ec68962c033a450943ded891bed2d54e6755e35e5835d63f4f6931d5` 和 `530f9ad26440e85766509dbf78edcfe13ffd0ab7fec2560ee5c36ff74d6269ff`。外部安装脚本及日志在 `/home/zz950/PMA_fetch/pma_hint_overlay_v1_jobs/`。源 `pmafp` pip-freeze SHA-256 在安装前后均为 `5d413fd24ed1f812ff05aa562e960f30a2c83fdc33ad72478d4b052216d3a207`。

作业 `59` 安装 NumPy 后，HINT 导入因新版 SciPy 不再提供 `scipy.integrate.trapz` 而退出 1；保留了失败日志。作业 `60` 在同一 overlay 内安装 SciPy 1.11.4 后，RGT 导入与 `rgt-hint --help` 成功，退出 0，`qacct maxvmem=2.314G`。作业 `61` 用仓库 `run_hint.sh` 处理已有 HCT116 control 的 20 个区域和 BAM，算法计算后因脚本未创建 `r_000.out` 目录而退出 1；分块日志显示 `FileNotFoundError`，`maxvmem=2.326G`。本 PR 在调用每个分块前执行 `mkdir -p "$f.out"`。

作业 `62` 用相同 BAM、20-region BED 和 HINT CLI 参数，在预建的新目录直接运行成功：`fp.bed` 共 234 行，SHA-256 `ec51ecd31ca5d8bac90bc959d9a812a67b6bb0b5706d0f002a4e75dd195e223e`，`qacct exit_status=0`、`ru_wallclock=13 s`、`maxvmem=2.317G`。结果位置：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_smoke_overlay_20261019_direct/ctrl/hint/`。该输出证明小样本 CLI 可运行；尚不证明预测准确，也不能用于选工具。

四个 Grid Engine 作业均使用 `normal.q` 单槽、`h_vmem=44G`，未使用 GPU。源环境与历史失败的部分 `pma_hint` 均保留。下一步将本 PR 的脚本同步到 Argos，在全新输出目录对 gdna、ctrl、aux 分别运行 HINT smoke，并检查每个真实结果；随后并行推进 PRINT、TraceBIND、TOBIAS 的同输入比较。首轮比较和 B1–B4 尚未完成。PR 合并需要用户单独确认。

## 00:22 EDT 更新：修复脚本的三组 smoke 完成

Argos checkout `/home/zz950/PMA_fetch/pma_pr8_hint_smoke_22667dc` 干净且 HEAD 精确为 `22667dc2afac7dfdf320f41b5cf1213783174f0b`。使用旧 smoke 的同一 BAM 和 20-region BED，调用修复后的 `run_hint.sh`，每组一个 Grid Engine 单槽 `h_vmem=44G` 作业，输出在仓库外的 `processed/round1/runs_smoke_pr8_22667dc/`：

| 组 | 作业 | exit | BED 行数 | BED SHA-256 | qacct maxvmem | wall |
|---|---:|---:|---:|---|---:|---:|
| gdna | 63 | 0 | 66 | `8e382c119f1be43e99000c5dccc9f563fae7c47c08269f0f662b4bcd40764b9d` | 2.333G | 25 s |
| ctrl | 64 | 0 | 234 | `ec51ecd31ca5d8bac90bc959d9a812a67b6bb0b5706d0f002a4e75dd195e223e` | 2.318G | 15 s |
| aux | 65 | 0 | 214 | `beaf7283e258cb4a17c3b500617358bdbf4acc6db371dbb19614ef4116212572` | 2.332G | 15 s |

三个分块均无 `failed.txt`，结果文件存在，作业 stderr 的 `/usr/bin/time -v` 均记录 exit 0。ctrl 的哈希与作业 62 直接调用相同，验证一行目录修复没有改变结果。Quick 阶段检查：L1 对这组三个 HINT smoke 为 PASS；L2 对准确度和全基因组速度仍为 BLOCKED，因为这些仅是 20 个区域、没有真值/对照指标；L3 向四工具比较的方向为 ON TRACK、REAL progress，尚不能选工具，`HUMAN DECISION: PENDING`。继续现有授权范围内的同阶段比较，不据 smoke 结果作科学结论。

## 00:38 EDT 更新：四工具 smoke 扩展及完整区域输入

TOBIAS 的相同 20 区域 gdna/ctrl/aux 作业 72/73/74 均退出 0，输出 BED 分别为 845/834/816 行；SHA-256 为 `3482f4be05f0568cf6669ee759feb34358029fd13330c31cb0d19e3999cbb849`、`648607c0b4a0a68ddec054a6dc2ce8088b04dc67f3b62a7ba320fd67f1f64298`、`f0c60db6173a0a99bc804ef056bdb04029ddf55802477e75cd2ad82047bf581c`。qacct wall 为 102/67/66 秒，maxvmem 为 5.334/5.286/5.222G。真实日志在 `/home/zz950/PMA_fetch/pma_pr8_tobias_smoke_jobs_22667dc/`。

PRINT/TraceBIND 第一批作业 66–71 仅进入 `conda activate r4p3`，被环境自带 `activate-r-base.sh` 的 `R CMD javareconf` 卡住，未进入分析，故取消；qacct 的 137 是取消退出，非内存超限。脚本及日志保存在 `/home/zz950/PMA_fetch/pma_pr8_other_smoke_jobs_22667dc/`。改为直接调用同一 `r4p3` 的 `Rscript` 并明确设置库路径后，PRINT 作业 75/76/77 进入真实算法。75 和 77 暴露缺失 `cladoRcpp`；76 因相同可复现依赖问题提前取消。Argos 作业 84 从 CRAN 源码 `cladoRcpp_0.15.1.tar.gz` 在独立库 `/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib` 安装并验证 `rcpp_convolve`，不修改 `r4p3`；源码 SHA-256 为 `326c5168a61ffce6e7cd468e28a7fab1125efc0ce367fe88498c9bbabdf14a57`，作业退出 0，maxvmem 952.305M。PRINT 以该隔离库重启为作业 86/87/88，运行中。

TraceBIND 直接 R 环境的 78/79/80 在 `reticulate` 内部再次调用 conda 激活，故取消并保留日志；作业 85 使用显式 `RETICULATE_PYTHON` 对 ctrl 试跑，运行中。若成功，再启动 gdna、aux。完整 2,000 区域 BAM 的准备作业 81/82/83 同时在 Argos 运行：ctrl、aux 已生成并通过 BAM/index 检查，分别含 871,464/819,464 fragments，BAM SHA-256 `520a5470fd159341aebf19c455db08e75ef38874bd0a1b01d4b3ebc6b3987e97` / `72f53785d53c638bdd0c9392bd8a22405924f5cd06f5e0834689fbe5017e1221`；gdna 仍在生成。所有任务均在 `normal.q`、单槽、`h_vmem=44G`、无 GPU，数据与输出仍在仓库外。ChIP-Atlas BED6 作业 58 持续扫描原始峰文件，此时压缩输入读到约 6.08/21.40 GB。下一验收是所有四工具 smoke 的真实退出码/结果 QC，以及 2,000 区域三组 BAM；不从 smoke 事件数推断准确度。

## 00:49 EDT 更新：Argos 队列错误后的受限后台运行

PRINT 86/87/88 再次使用节点 `/tmp`，并行解压使其 54-GB 根盘耗尽；ctrl、aux 日志出现 `Fatal error: cannot create 'R_TempDir'`，gDNA 占用的 6.3-GB 临时目录由作业退出后自动释放。已保留失败日志，重启为外部 DATA 临时目录的 `BG_PRINT_SMOKE_{gdna,ctrl,aux}_V4`，目前正在运行。TraceBIND 原试跑 85 即使显式设置 Python 也仍进入 conda，因为用户的 `~/.Renviron` 在 R 启动时覆盖了 `RETICULATE_PYTHON`。隔离配置 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/Renviron.tracebind` 通过 `R_ENVIRON_USER` 指向 `pmafp` Python；后台探针 `BG_RETIC_V5` 退出 0，实际 `py_config()` 指向 `/home/zz950/softwares/miniforge3/envs/pmafp/bin/python`，NumPy 2.4.6；TraceBIND ctrl 的 `BG_TRACE_CTRL_V5` 已启动，尚待结果。

作业 85/86 异常使唯一的 `normal.q` 被 Grid Engine 标为 QERROR；`qstat -f -explain E` 明示这两个作业，`qmod -c normal.q@rcGPUs.dfci.harvard.edu` 返回当前账户无修改队列权限。已取消所有未启动的排队作业 89–96；运行中的 58（BED6）与 81（gDNA BAM）不受影响。为继续已授权的 Argos 计算，使用交接指南允许的后台方式：`/home/zz950/PMA_fetch/pma_bg_gate.sh` 为每个进程设置软硬 `RLIMIT_AS=44 GiB`、单线程环境、禁用 GPU，写独立的 PID、日志、元信息和退出码到 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`。临时数据实际位于仓库外 DATA 目录，短路径 `/home/zz950/PMA_tmp` 仅是指向它的符号链接；任何结果仍写在 `processed/round1/`。

2,000 区域 HINT 的 control/auxin 后台任务 `BG_FULL_hint_ctrl` / `BG_FULL_hint_aux` 均退出 0，分别输出 20,233 / 20,531 个事件，SHA-256 `277e5826e788255e7a88db9283efb45cbc3b6a9af18f2ffb941b725ebf536864` / `413917a3267f3e0f702626186cb516991a9d13bb4359e09330b468d9dde1a803`，wall 2:02.64 / 2:00.64，最大 RSS 224,548 / 213,872 KB。首次 TOBIAS 全量后台任务因临时目录路径过长触发 `OSError: AF_UNIX path too long`，日志保留；改用短符号链接后 `BG_FULL_TOBIAS_{ctrl,aux}_V2` 正在运行。HINT/TOBIAS 的事件数仍只证明调用完成，不构成准确度比较。

## 05:38 EDT 更新：三工具 2,000 区域结果、gDNA 与 TraceBIND

Argos ctrl/aux 的完整 2,000 区域调用已有真实文件：HINT 20,233/20,531 行（SHA-256 `277e5826e788255e7a88db9283efb45cbc3b6a9af18f2ffb941b725ebf536864` / `413917a3267f3e0f702626186cb516991a9d13bb4359e09330b468d9dde1a803`）；TOBIAS v2 84,513/83,344 行（`85171edd15057b1c40b1186ebcacb8d9aa4e4a3a46a866bf389363445c4b94ae` / `33ec6be16b92ce813e7170548240c827e80cc49cdea74868f44d3bf122d49af2`）；PRINT r10 4,455/4,564 行、r20 2,756/2,711 行。PRINT 的任务退出码均 0，约 17 分钟、最大 RSS 37.1–37.5 GB；TOBIAS 约 15 分钟，子日志 exit 0 且文件非空。TOBIAS 的旧 launcher 状态文件缺失，因为早期运行时覆盖了 launcher；已改用不可变的 `/home/zz950/PMA_fetch/pma_bg_gate_v2.sh`。结果都在外部 `runs_full_pr8_22667dc/`，不据事件数选工具。

裸 gDNA 的 PRINT 20 区域 `BG_PRINT_SMOKE_gdna_V5` 退出 0，r10/r20 37/23 行。其索引切片 `gdna_smoke.frags.tsv.gz` 有 217,961 行；全量 2,000 区域切片 `gdna_full.frags.tsv.gz` 有 17,544,605 行，SHA-256 `151951282b92775428ed9ff8fa6f3cbd95cd8a5e96bd97afaeb5fca4fa8833fb`。全量 gDNA HINT、TOBIAS、PRINT 分别为 `BG_FULL_GDNA_HINT_V1`、`BG_FULL_GDNA_TOBIAS_V1`、`BG_PRINT_FULL_gdna_V2`，运行中。TraceBIND ctrl v7 到达偏好模型与 count 阶段后，因缺少 `foreach` 导致 `%dopar%` 不可用而退出 1；保留失败日志。在 R runner 补 `library(foreach)` 后，ctrl/aux/gdna v8 smoke 已启动，结果待核对。`eval_round1.py` 仅为尚未运行的描述性密度汇总；B1 匹配灵敏度、B2–B4 和速度门槛都未完成。

## 05:42 EDT 更新：TraceBIND ctrl smoke 与 gDNA HINT 完成

`BG_TRACE_CTRL_V8` 在修复 `foreach` 导入后退出 0，20 区域原生事件 31 行。aux 与 gDNA v8 smoke 仍在运行；gDNA 使用相同 20 区域的索引片段切片。ctrl/aux 2,000 区域 TraceBIND PRINT-bias 模式已以 4 CPU worker、44 GiB 软硬地址空间上限启动为 `BG_TRACE_FULL_{ctrl,aux}_V10`。此前 V9 因外部传输脚本无执行权限退出 126，未进入分析且无结果；修复权限后重启，失败日志保留。gDNA 2,000 区域 HINT 已退出 0，7,810 事件，SHA-256 `64c6b6c42c8b3eca2391990b9c0288a37f103bbe6d0d4cc784fa7965fddc7862`，wall 12:35.33。此事件数不代表工具优劣。

## 05:47 EDT 更新：四工具三组 smoke 全通过

TraceBIND v8 的 gDNA/ctrl/aux 20 区域任务均退出 0，事件 363/31/29 行；SHA-256 分别为 `e301eb2dbab9deb5012aa7894a81a773304fb92a6303db73523c8de7453eb3d5`、`de627ade7c4e05af906104287b69315633e024f7a39cd86aa22e9c5f8ab49360`、`5a273533d40c2dd57ab9e66ea1793a9edcbe8b6a40687e688381bd07643f19cb`；wall 9:08.76/8:56.61/8:26.31，最大 RSS 1,469,368/8,091,172/7,907,668 KB。加上已有 HINT、TOBIAS、PRINT，四工具三组 smoke 均已跑通。Quick 阶段核查：L1 对执行和文件 PASS；L2 对准确度与全基因组速度 BLOCKED；方向 ON TRACK、真实进展 REAL；L3 human acceptance 待定，尚不选工具。gDNA 2,000 区域 TraceBIND PRINT-bias 已启动为 `BG_TRACE_FULL_gdna_V10`，ctrl/aux 同规模任务仍在运行；均为 Argos 受限 CPU 任务。

## 05:49 EDT 更新：gDNA 2,000 区域 PRINT 完成

`BG_PRINT_FULL_gdna_V2` 退出 0；PRINT r10/r20 原生事件 2,943/1,376 行，SHA-256 `e12a6d1784b66feb2e1e8fa6260c78d592da8fe0395195722f1ef9207f8f9bd8` / `ff1421c173da71e748a831a57941de62853878b4db59bcf50423f20ebd549b6d`。调用 wall 17:12.08、最大 RSS 30,121,176 KB；索引片段切片预处理另耗约 76 秒。结果位于外部 `runs_full_pr8_22667dc/gdna/print_v2*`。这是 B1 的原生阈值输出，不是匹配灵敏度后的 FPR 比较。

## 05:50 EDT 更新：全基因组速度门槛的输入准备

已在 Argos 启动 `BG_BAM_MERGE_{ctrl,aux}_V1`，将已校验的 ENCODE filtered BAM 按条件合并并建立索引：ctrl = ENCFF784ATG + ENCFF794FUH，aux = ENCFF877LRY + ENCFF745WLX。四个输入通过 `samtools quickcheck`，头部标记为 coordinate sorted。每项设置 44 GiB 软硬地址空间上限、单 worker、无 GPU；输出在外部 `processed/round1/bam/genome_wide/`，准备时间与 caller 速度门槛分开记录。任务尚未完成，不能宣称已跑全基因组 footprint。

## 05:54 EDT 更新：首轮汇总输入清单已冻结

已把 PR #8 的 `eval_round1.py` 复制到 Argos 仓库外代码暂存，SHA-256 `d5b85b1a3d9946d8da8c8e4a59dfd3e9b9ab2a3aa4e50361026c6a2abe417570`；外部 spec `processed/round1/benchmark_round1/spec_77d8556.json` SHA-256 `13fc4061742d9e399795d32bd570cb3ae956a9a97cae0d96c4b0f4aa2a73e184`，逐组固定 2,000 区域 BED 与 HINT、TOBIAS、PRINT r10/r20、TraceBIND 的原生结果路径。因 gDNA TOBIAS 与完整 TraceBIND 尚未完成，汇总尚未运行；输出只能是原生阈值的描述性密度，不能据此选工具。

## 2026-10-19 06:06 EDT：全样本 BAM 与 HINT 速度实测

Argos 的 ctrl/aux 双重复 BAM 合并和索引均退出 0，分别为 4,960,640,917 与 4,877,771,562 字节，SHA-256 为 `a87821a4c33544f6534d7a1d51c6a54241af0f09c98dca7e652e491dd5ed452d` / `2259792d005017284166fad448783418dd4d97bcf16bff8c743e2df6dc47ca88`，`samtools quickcheck` 通过。合并准备时间与 caller 时间分开记录。06:06:37 EDT 已用完整 ctrl BAM、91,210 个预设 HCT116 peak 窗口、32 个 HINT 分块启动 `BG_HINT_GENOME_ctrl_32_V1`，44 GiB 软硬地址空间上限、CPU-only；日志在 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`，结果在外部 `processed/round1/runs_genomewide_pr8_77d8556/ctrl/hint_32`。尚无退出码、全量输出或速度门槛结论；gDNA TOBIAS 与三组 TraceBIND 首轮仍在运行。

## 2026-10-19 06:18 EDT：TraceBIND 序列 I/O 修复

检查已安装 `tracebind::get_bias()` 后确认：若工作目录有 `regionSeqs.txt`，它会跳过对远端 2bit 文件逐区域反复执行的 `getSeq()`。原三组 V10 运行约半小时仍无结果，抽查 worker 已各自读取 15–24 GB 远端 2bit；因此主动停止，仅这三组进程树收到 TERM，gate 记录退出码 143，日志完整保留。新增脚本从已索引、已校验的 hg38 FASTA 预计算区域两侧各 50 bp，20 区域 ctrl 小样例与原 BSgenome 输出逐字节一致、退出 0。ctrl/aux/gDNA 的 2,000 区域预计算均在 44 GiB CPU-only 任务下退出 0，序列 SHA-256 为 `c071c1cd80e229510ac2f96ac552548e70b3e41ec8fdeea11c6e24ab82f5e91a`、`c071c1cd80e229510ac2f96ac552548e70b3e41ec8fdeea11c6e24ab82f5e91a`、`d821f7654bab067df730112bfb1979748bd179331756aedf784370ad819bbfff`。已用同一原生 R 统计调用和预计算序列启动三组 V11；退出与事件文件仍待核验。新外部汇总 spec 为 `spec_trace_v11_77d8556.json`，SHA-256 `2f182a61960a39606b5712e97e7c68d11799e1362bfafacf5064c4a2debe08a0`。尚无准确度结论。

## 2026-10-19 06:22 EDT：HINT 全样本实测与片段数

ctrl HINT `BG_HINT_GENOME_ctrl_32_V1` 退出 0：91,210 个预定 peak 窗口、32/32 分块结果齐全，wall 10:03.94，927,584 条原生 footprint 事件，SHA-256 `ea2b730c79e82637a63bf18f0493b689d3ad40f8f6c81b011ebeaee8660225d5`；单子进程最大 RSS 239,532 KB，32 进程抽样合计约 7.25 million KiB。独立 Argos 片段计数任务退出 0，合并 ctrl BAM 中 MAPQ≥30、primary、proper-pair 的 read1 数为 46,158,731。因此此结果是真实全样本运行，但未达到预设 1 亿片段速度门槛，不可声称通过门槛。已启动 aux 的相同 HINT 运行和片段计数；gDNA TOBIAS、三组 TraceBIND V11 仍在运行。需要真实 1 亿片段 ATAC 样本再做正式速度门槛。
