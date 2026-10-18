# Step 4b-1 HINT bundle review repair handoff

- 日期：2026-10-18
- 分支：`task_20261018_step4b_setup_fix`
- PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)，OPEN，未合并
- 范围：GPT 对 PR HEAD `4a07dc5dfe5a7dd97cae2978e49ca913c96505fa` 的 F1/F2 findings 及后续验证收尾。

## 已完成

- `6c59bd4` 将 Conda 锁定包与已校验的 repodata filename/name/version/build/SHA 绑定，比较可用的 solver LINK subdir/filename，并在验证完整 solver closure 后通过 `@EXPLICIT` 安装准确的本地归档 URL。
- Wheel 验证覆盖目标 CPython 3.11/Linux x86_64、Requires-Python、目标 marker、Requires-Dist、native/glibc tag 边界；未知 kernel release/version marker 与不满足 glibc 证据的裸 `linux_x86_64` tag fail closed。
- 此后 GPT 指出 pip dry-run 可能因源 `pmafp` 已安装 RGT 而跳过目标 wheel 检查。本地加入 `--ignore-installed`，令离线 dry-run 检查锁定 wheel，而不实际修改源环境。
- 最新本地验证：shell syntax、validator compile-in-memory、`tests/test_hint_env_builder.sh`、`tests/test_step4b_runner_contract.sh`、`git diff --check` 均通过；HINT bundle/runner 测试通过。均为本地/mock 验证。

## 当前状态与门禁

- 已知远端 PR HEAD 为 `991879055d087f17c8b483e21186db503e0586fb`。GPT 对前一完整 HEAD `4a07dc5...` 给出 `REQUEST_CHANGES`；`6c59bd4` 和 `9918790` 已推送，但新完整 HEAD 尚待 GPT 复审。
- `--ignore-installed` 修正和本次审计同步仍待显式暂存、提交、推送；推送后要再读取 PR 远端 HEAD 并更新 PR 描述，然后要求 GPT 审核精确完整 SHA。
- 在 GPT 对当前完整 HEAD 明确 `APPROVE` 前，禁止任何 Argos 命令或外部分析。既有部分 `pma_hint` 和源 `pmafp` 必须保留；无 HINT CLI/small-BED/smoke/round-1 结果；不合并。
- 获批后才按用户此前 §6 授权，先构建/审计外置 Linux 离线包并做 Argos preflight、安装至新前缀、确认源环境不变，再验证真实 HINT CLI 与 small-BED，之后重试 smoke。所有 smoke caller 通过及输出检查后才可运行 12 个 round-1 jobs。

## L1/L2/L3 快速评估

- L1：本地 mock 与语法检查 PASS；Argos 真实包闭包、Conda/pip 兼容及 HINT runtime UNVERIFIED。
- L2：BLOCKED，真实目标环境尚未建立/验证，不能据 mock 推断 benchmark 可运行。
- L3：方向 ON TRACK；进展 PARTIAL（明确了 F1/F2 修复边界和新增 pip 检查，但尚无新科学结果）；人类接受待定。

原始输入和分析输出均保存在仓库外。
