# Step 4b-1 smoke 故障与修复交接

- 日期：2026-10-18
- 当前 PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)
- 分支：`task_20261018_step4b_setup_fix`，base `step4b-atac-footprinting`
- 最近已审运行代码：`229ad968489c3c9ec7bc2d090b9f38f7d5e0bb2e`
- 数据与结果路径均在 Argos 的仓库外：`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/`

## 最新运行

2026-10-18 03:05–03:13 EDT，按此前用户对 §6 首轮评测的独立授权运行 driver PID `16305`，日志：`/home/zz950/PMA_fetch/fp_4b1_229ad96_20261018.log`。设置阶段通过；prep 生成 91,210 个区域，其中 90,992 个有正 gDNA 覆盖，恰好选择了 2,000 个 B1 tiles；缺少的 chrY 上有 3 个 peak，215 个可查询区域为观察到的零覆盖。BAM 转换统计为 gDNA 577,891、ctrl 11,438、aux 11,687 fragments。

Smoke 最后输出 `SMOKE_FAIL`，未启动 full round 12 个 caller jobs。没有遗留 Step 4b 进程，raw input 未改动。

## 失败证据

- HINT 的 gdna/ctrl/aux 共 12 个 chunk 全部在 RGT 导入时失败：`ModuleNotFoundError: No module named 'pkg_resources'`。每组 `failed.txt` 均记录四个失败 chunk，`hint/events.bed` 为 0 bytes；没有 HINT 结果可供科学解释。
- 只读环境检查：pmafp 是 Python 3.11.17、setuptools 84.0.0，`pkg_resources` 不可导入；RGT 1.0.2 的 `rgt/__init__.py` 仍导入该模块。setuptools 官方版本历史确认 82.0.0 移除了 `pkg_resources`。
- TOBIAS 三组都生成 events。PRINT 与 TraceBIND 没有日志或输出；总控日志出现 6 次 `GDAL_DATA: unbound variable`。只读查看 r4p3 的 GDAL activation hook 确认其在 `set -u` shell 下无默认值地读取该变量。R 子进程在 conda activate 阶段退出是目前推断，尚待修复后 smoke 验证。
- 原 `run_round1.sh` 的无参数 `wait` 没有聚合所有后台 caller 的退出码；`run_4b1.sh` 只用文件存在检查，不能识别 0-byte HINT events。这次 driver 因 PRINT/TraceBIND 输出缺失而停下，但 gate 仍需 fail-closed 修复。

## 同一 PR 内的最小修复

本地正在修改：

1. 增加 `setuptools==80.9.0` 约束，并在 setup/prep 前检查其版本、`pkg_resources` 和 RGT 是否可导入；此依赖尚未安装到 Argos 环境。
2. HINT 每个 chunk 单独等待、检查退出码和输出路径；失败时不合并，非零退出。
3. `run_round1.sh` 逐项等待并汇总所有 callers 状态；任一失败即返回非零。
4. R conda activate 前安全初始化 GDAL 环境变量，并显式传播激活失败。
5. Smoke driver 要求 smoke 成功并检查预期产物及 HINT failed marker，失败绝不进入 full round。

这些修复不改变数据、caller 方法、阈值或 benchmark 范围。修复和本交接记录需经当前 PR HEAD 的 GPT 明确 `APPROVE` 后，才能更新 Argos 环境或再次执行命令。下一次仅在既有用户授权内修复环境、验证 HINT/R caller smoke；smoke 全部通过前不得启动 full round。PR merge 仍需用户单独确认。

## GPT 诊断与来源

已向 PMA 项目的持久 GPT 对话提交独立诊断。其结论为 HINT 直接错误已确定，建议固定兼容 setuptools，并修复 smoke 的失败传播；没有批准新的代码或 Argos 运行。setuptools 版本历史：[官方文档](https://setuptools.pypa.io/en/latest/history.html#v82-0-0)。
