# Step 4b-1 HINT bundle review repair handoff

- 日期：2026-10-18
- 分支：`task_20261018_step4b_setup_fix`
- PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)，OPEN，未合并
- 范围：GPT 对 PR HEAD `4a07dc5dfe5a7dd97cae2978e49ca913c96505fa` 的 F1/F2 findings 及后续验证收尾。

## 已完成

- `6c59bd4` 将 Conda 锁定包与已校验的 repodata filename/name/version/build/SHA 绑定，比较可用的 solver LINK subdir/filename，并在验证完整 solver closure 后通过 `@EXPLICIT` 安装准确的本地归档 URL。
- Wheel 验证覆盖目标 CPython 3.11/Linux x86_64、Requires-Python、目标 marker、Requires-Dist、native/glibc tag 边界；未知 kernel release/version marker 与不满足 glibc 证据的裸 `linux_x86_64` tag fail closed。
- 此后 GPT 指出 pip dry-run 可能因源 `pmafp` 已安装 RGT 而跳过目标 wheel 检查。本地加入 `--ignore-installed`，令离线 dry-run 检查锁定 wheel，而不实际修改源环境。
- GPT 对完整 HEAD `2bf931c34727137a161a93224725db1c897c70e9` 复审结果为 `REQUEST_CHANGES`：F1 已解决；F2 尚有 extras 依赖 fail-open，即 validator 没有递归展开类似 `A → B[foo] → C` 的依赖。
- 本地已实施 fail-closed 修复：只要某条依赖在目标 marker 下生效且声明非空 `Requirement.extras`，validator 报 `UNSUPPORTED_PIP_EXTRAS` 并失败；新增带真实 wheel metadata 的 A → B[foo] → C mock bundle，确认缺少 C 时 preflight 不能通过且不创建 prefix。
- 最新本地验证：shell syntax、validator compile-in-memory、`tests/test_hint_env_builder.sh`、`tests/test_step4b_runner_contract.sh`、`git diff --check` 均通过；HINT bundle/runner 测试通过。均为本地/mock 验证。
- GPT 对完整 HEAD `b76da4d9f2bb8a32126cc83b55537e1325f6e060` 已明确 `APPROVE`，确认 F1/F2/F2-B/F3 均解决、无剩余代码阻断项。该 approval 仅针对代码和审计，不是执行或合并授权。用户此前对 Step 4b §6 的独立执行授权仍有效。

## 当前状态与门禁

- 最后实时核验的远端 PR HEAD 为 `b76da4d9f2bb8a32126cc83b55537e1325f6e060`，PR #4 OPEN、未合并；GPT 已 APPROVE 该完整头。
- 在任何 Argos 命令之前，先将拟执行动作及停止条件加入同一 PR 的 Worklog、handoff 和 PR 描述，推送后获取对精确 audit-only HEAD 的 GPT 审核。通过后，才能在既有 §6 授权范围内执行：在仓库外准备并审计 Linux CPython 3.11/glibc ≤2.23 bundle；Argos preflight 全通过才可创建全新 `pma_hint_v2`；缺包/哈希/closure/platform 任何失败都在创建前停止，不回退联网；安装失败保留 partial prefix、日志与源 `pmafp`，不写 READY、不启动 caller；安装成功且审计通过后才验证真实 CLI/reference、small-BED/smoke。所有数据和结果留在仓库外；smoke 每个 caller 通过后才进入 12 个全量 jobs；合并仍须用户单独确认。
- 此前最后一次 Argos 操作是离线 `pma_hint` clone 失败。部分 `pma_hint` 与源 `pmafp` 必须保留；无 HINT CLI/small-BED/smoke/round-1 结果；不合并。
- GPT 已批准代码 HEAD `b76da4d9f2bb8a32126cc83b55537e1325f6e060`。在 Argos 前仍须将计划中的外部动作和停止条件记入同一 PR 并获得对 audit-only 新 HEAD 的 GPT approval；只有该审计门禁通过后，才按用户此前 §6 授权执行。先在仓库外准备/审核 Linux 离线包，再依序执行 Argos preflight、安装到新前缀、确认源环境完整性、验证真实 HINT CLI/small-BED、smoke；所有 smoke caller 通过且输出检查合格后才可运行 12 个 round-1 jobs。

## L1/L2/L3 快速评估

- L1：本地 mock 与语法检查 PASS；Argos 真实包闭包、Conda/pip 兼容及 HINT runtime UNVERIFIED。
- L2：BLOCKED，真实目标环境尚未建立/验证，不能据 mock 推断 benchmark 可运行。
- L3：方向 ON TRACK；进展 PARTIAL（明确了 F1/F2 修复边界和新增 pip 检查，但尚无新科学结果）；人类接受待定。

原始输入和分析输出均保存在仓库外。
