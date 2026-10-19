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
