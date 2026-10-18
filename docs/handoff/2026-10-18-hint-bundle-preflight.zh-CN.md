# Step 4b-1 HINT bundle preparation and preflight handoff

- 日期：2026-10-18；最近状态更新 05:50 EDT
- 分支：`task_20261018_step4b_setup_fix`
- PR：[#4](https://github.com/leezx/Protein-Motif-Association/pull/4)，OPEN，未合并
- 基线代码与阶段范围：GPT 已 APPROVE 代码 HEAD `b76da4d9f2bb8a32126cc83b55537e1325f6e060` 和阶段审计 HEAD `62868bf4a42e04e5959901636e59077064211c05`。GPT 对后续 audit-only HEAD（最新已批准 `9c3a0735b3761378236949f00a03d383269feb8e`）确认原阶段范围仍有效；不必为未变化的范围重复申请批准。新增 builder 代码仍须对新完整 PR HEAD 复审后才可运行。

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
- GPT 已于 2026-10-18 对精确 HEAD `826e90cfe840a3e99c8afe8bcfde91cfcd2c4d02` 返回 `APPROVE`：审计准确、当前状态一致、scope-control PASS、无阻断项。GitHub 正式 review 仍因集成 HTTP 403 无法登记。此次 approval 只覆盖 audit-only 状态记录。
- 本 handoff、worklog 与 PR 描述需随新增提交同步；GPT 对包含这些记录的精确新 PR HEAD 审核通过后，才进行本阶段 bundle 准备和 Argos preflight。
- GPT 对 HEAD `c86b01a69c3a6352ebf364a9927413cd84a33770` 的 audit-only 同步再次 `APPROVE`：审核记录和当前状态准确、无阻断项。GitHub formal review 登记 HTTP 403。该批准不包含 builder 代码、Docker 管理员授权或 Argos 操作。
- HUMAN DECISION：待定。PR 合并：未经授权。

## 构建器缺口与当前阻塞（05:21 EDT）

- GPT 核对后建议先实现最小可审计的 bundle builder/contract，再用固定镜像 digest 的 Docker `linux/amd64` 构建；不要手工拼装后声称可复现。建议的增量仅生成 bundle，不具备 Argos 安装能力；新代码 HEAD 必须先通过同一 PR 的 GPT 审核。
- 必须区分 Conda 完整 solver 闭包、本地 channel/repodata 与 RGT wheel ABI 审计；Conda 闭包和 wheel 的 GLIBC/GLIBCXX/动态库证据需要分别验证。若要求的 `.tar.bz2` 工件、依赖闭包或 glibc 证据不可得则停止，不放宽锁或绕过 validator。
- 本机为 macOS arm64。发现 Docker Desktop 已安装但 daemon 未启动；启动后 Docker 后端请求系统管理员授权以配置 privileged port mapping。未接受该授权，Docker socket 尚未建立。无 Podman、nerdctl、Buildah、Lima 等替代运行时可用。
- 当前没有 bundle 构建、Argos 访问、目标环境修改或 caller/benchmark 运行。只有在 builder 代码获得 GPT 审核，且 Docker daemon 可用后，才继续仓库外构建；Argos 仍只运行经审核的 offline preflight。

## 2026-10-18 05:50 EDT 状态更新：builder 本地草稿，外部执行暂停

- GPT 在持久 PMA 对话中核验 PR #4 的 `9c3a0735b3761378236949f00a03d383269feb8e` 后判定：既有阶段范围批准有效；新增 builder 未审；本地静态开发可以继续；真实 bundle 构建须等待 builder 新完整 HEAD 审核及合规 Linux x86_64 构建主机；Argos 仅可在完整 bundle 形成后进行离线 preflight。该答复不批准 Argos 构建、环境安装、HINT CLI、small-BED、smoke 或 full jobs。
- 本地新增未提交草稿：`scripts/04b_footprint/build_hint_bundle.py`、`scripts/04b_footprint/Dockerfile.hint-builder`、`tests/test_hint_bundle_build_contract.py`。草稿仅设计为外部 bundle 构建器；尚未经过 GPT 代码审核、尚未运行于 Linux/Docker，也没有生成 bundle。
- 本地/mock 验证通过：builder 合同单测 5 项、`tests/test_hint_env_builder.sh`、`tests/test_step4b_runner_contract.sh`、`git diff --check`。这些结果不证明 Linux 兼容性或真实 Conda/pip 求解。
- PR #4 远端仍 OPEN、未合并；本次检查时完整 HEAD 为 `9c3a0735b3761378236949f00a03d383269feb8e`。下一步完成代码自审和审计记录，显式暂存任务文件，在同一 PR 提交/推送后请 GPT 审核精确完整 HEAD。Docker Desktop 管理员授权仍未接受、daemon socket 不存在；不得绕过权限。Argos 之前的任务已结束，当前无评测运行。
- 不相关未跟踪文件 `design/protein_binding_resources.md` 保持原样。PR merge 仍需用户单独确认。
