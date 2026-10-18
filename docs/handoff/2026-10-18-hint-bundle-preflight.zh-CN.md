# Step 4b-1 HINT bundle preparation and preflight handoff

- 日期：2026-10-18 05:10 EDT
- 分支：`task_20261018_step4b_setup_fix`
- PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)，OPEN，未合并
- 当前代码与执行计划审核：GPT 已 APPROVE 完整 HEAD `b6a9b294b1daf7ee09977e189021426e1a996dad`。此次记录须随新 PR HEAD 再审核，之后才能开始本阶段外部操作。

## 本阶段范围

1. 在仓库外准备面向 Linux x86_64、CPython 3.11、glibc ≤2.23 的 HINT 离线包。
2. 记录每个 Conda/wheel 工件的来源、完整依赖闭包、SHA-256、目标平台依据及 bundle 总摘要；任何来源、依赖或兼容性无法验证时停止，不生成可安装包。
3. 将 bundle 传到 Argos 后只运行离线 preflight。缺失工件、哈希不符、marker/依赖闭包/平台不匹配或 solver 结果未经验证时，必须在创建环境前停止并保留报告。

## 不在本阶段执行

- 不创建或修改任何 Conda prefix；尤其保留 `pmafp`、部分失败的 `pma_hint`，不创建 `pma_hint_v2`。
- 不调用 HINT CLI，不运行 small-BED、smoke 或 12 个 round-1 jobs。
- 不联网回退，不修改原始数据，不将 bundle、日志或结果写入 Git 仓库。
- 不合并 PR；合并仍须用户另行明确确认。

## 已知状态与后续门

- 上次 Argos 的 offline clone 因本地缓存缺包失败；`pmafp` Conda/pip manifests 前后相同，部分 `pma_hint` 须保留。
- 最近的真实 HINT CLI、small-BED、smoke 与 round-1 均未通过/未运行。
- 本阶段通过并完成 GPT 对结果的复核后，才为新前缀安装阶段另建带时间戳 handoff/worklog 并重新取得 PR 审核。安装成功也不会自动放行 caller 或 smoke。
- 所有机器数据、包、日志和结果都在仓库外。

## 审核状态

- 对 `b6a9b294b1daf7ee09977e189021426e1a996dad` 的 GPT 回复明确为 `APPROVE`，只确认该 audit-only 更新与预定计划一致、无阻断发现。
- 本 handoff、worklog 与 PR 描述需随新增提交同步；GPT 对包含这些记录的精确新 PR HEAD 审核通过后，才进行本阶段 bundle 准备和 Argos preflight。
- HUMAN DECISION：待定。PR 合并：未经授权。
