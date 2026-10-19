# Step 4b HINT 隔离环境与真实小样本调用

时间：2026-10-19 00:19 EDT。分支：`task_20261019_hint_overlay_smoke`，基于已合并 PR #4 的 `step4b-atac-footprinting` 头 `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`。本 PR 只修复 HINT 分块输出目录；所有包、BAM、BED 和结果均在仓库外。

## 目标与证据

现有 `pmafp` 内 RGT/HINT 1.0.2 的 CLI 因 NumPy 2.4.6 缺少 `numpy.mat` 而失败。Argos 上新建 `/home/zz950/PMA_fetch/pma_hint_overlay_v1`，通过 `venv --system-site-packages` 读取原 `pmafp` 包，仅在 overlay 内安装 NumPy 1.26.4 和 SciPy 1.11.4。两个 Linux CPython 3.11 manylinux2014 wheels 的 SHA-256 分别为 `666dbfb6ec68962c033a450943ded891bed2d54e6755e35e5835d63f4f6931d5` 和 `530f9ad26440e85766509dbf78edcfe13ffd0ab7fec2560ee5c36ff74d6269ff`。外部安装脚本及日志在 `/home/zz950/PMA_fetch/pma_hint_overlay_v1_jobs/`。源 `pmafp` pip-freeze SHA-256 在安装前后均为 `5d413fd24ed1f812ff05aa562e960f30a2c83fdc33ad72478d4b052216d3a207`。

作业 `59` 安装 NumPy 后，HINT 导入因新版 SciPy 不再提供 `scipy.integrate.trapz` 而退出 1；保留了失败日志。作业 `60` 在同一 overlay 内安装 SciPy 1.11.4 后，RGT 导入与 `rgt-hint --help` 成功，退出 0，`qacct maxvmem=2.314G`。作业 `61` 用仓库 `run_hint.sh` 处理已有 HCT116 control 的 20 个区域和 BAM，算法计算后因脚本未创建 `r_000.out` 目录而退出 1；分块日志显示 `FileNotFoundError`，`maxvmem=2.326G`。本 PR 在调用每个分块前执行 `mkdir -p "$f.out"`。

作业 `62` 用相同 BAM、20-region BED 和 HINT CLI 参数，在预建的新目录直接运行成功：`fp.bed` 共 234 行，SHA-256 `ec51ecd31ca5d8bac90bc959d9a812a67b6bb0b5706d0f002a4e75dd195e223e`，`qacct exit_status=0`、`ru_wallclock=13 s`、`maxvmem=2.317G`。结果位置：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_smoke_overlay_20261019_direct/ctrl/hint/`。该输出证明小样本 CLI 可运行；尚不证明预测准确，也不能用于选工具。

四个 Grid Engine 作业均使用 `normal.q` 单槽、`h_vmem=44G`，未使用 GPU。源环境与历史失败的部分 `pma_hint` 均保留。下一步将本 PR 的脚本同步到 Argos，在全新输出目录对 gdna、ctrl、aux 分别运行 HINT smoke，并检查每个真实结果；随后并行推进 PRINT、TraceBIND、TOBIAS 的同输入比较。首轮比较和 B1–B4 尚未完成。PR 合并需要用户单独确认。
