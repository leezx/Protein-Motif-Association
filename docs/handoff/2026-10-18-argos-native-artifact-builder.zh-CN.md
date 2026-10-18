# Step 4b-1 Argos 原生 bundle builder 交接

更新时间：2026-10-18 10:43 EDT
仓库：`Protein-Motif-Association`
基线：PR #4 merge commit `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`，目标分支 `step4b-atac-footprinting`
工作分支：`task_20261018_argos_artifact_builder`
PR：[#5](https://github.com/leezx/Protein-Motif-Association/pull/5)

## 状态与边界

### 2026-10-18 10:55 EDT 实时状态

PR #5 仍 OPEN、未合并；GPT 已明确 APPROVE 精确 HEAD `ede0f811e14c3d1e133b120c6afafaf433f91cd6`，允许 G2 外部 bundle 构建和既有 offline preflight。Argos SSH 可用。为避免更改运行中的 `/home/zz950/PMA_code_4b`，已在 `/home/zz950/PMA_fetch/pma_pr5_code_ede0f81` 创建独立 checkout，并核对其完整 SHA 与批准值一致。

G2 首次直接执行 wrapper 因脚本文件模式为 664（不可执行）退出，未创建工作目录。第二次使用 `bash` 执行时，宿主默认 Python 3.5.2 无法解析仓库的 f-string 校验器，也在写入前退出。随后仅将既有 `pmafp/bin` 放到 `PATH` 前端，使 `python3` 指向已有 Python 3.11.17；未修改任何 Conda prefix。此调用下载并按 lock 校验了 6 个工具 wheels，接着因 `setuptools-80.9.0` 含多个合法的嵌套 vendored `.dist-info` 被验证器误报而停止：`ARGOS_TOOLCHAIN_WHEEL_METADATA_INVALID`。原始 wheel 的 SHA-256 为 `062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922`。wrapper EXIT 审计生成 `PMAFP_INTEGRITY_OK`；Conda explicit 与 pip freeze 前后清单逐字节一致。没有进行 Conda 在线/离线求解、bundle 生成、offline preflight、环境安装、HINT CLI 或分析。失败工作区及已下载证据保留在 `/home/zz950/PMA_fetch/pma_pr5_g2_ede0f81/`。

只读 Conda 清点确认 `pmafp`、`argos-codex` 是登记的环境；`pma_hint` 仅是 2026-10-18 04:07 创建的部分目录，无 `conda-meta/history`，也不在 Conda 登记列表，故不能称为已完成环境。三者均未修改。失败 G2 工作区和下载证据保存在 `/home/zz950/PMA_fetch/pma_pr5_g2_ede0f81/`。

同一 PR 的本地修复已将 wheel 元数据识别收紧到由 wheel filename 推导的唯一根级 canonical `.dist-info/METADATA` 与 `WHEEL`，同时仍扫描全部成员路径及 native payload；正向 fixture 覆盖合法嵌套 vendored metadata，负向 fixture 拒绝额外/不匹配根级 `.dist-info`、缺失 canonical `METADATA`（即便 vendored metadata 存在）和重复根级 `METADATA`。GPT 独立诊断确认根因，认为该最小修复方案可接受，但要求代码提交并经 exact-HEAD review 后才允许重试 G2。目前 32 项合同测试、`py_compile`、wrapper `bash -n`、`git diff --check` 均通过，且 Argos 下载的真实 setuptools wheel 在本地验证通过。该修订尚未提交、推送或审核；新的 exact HEAD 获 GPT APPROVE 前不重试 G2。现有 `pmafp` 与残留 `pma_hint` 均保留，不合并 PR #5。

科研软件 Quick review：L1 本地合同测试/语法/差异检查 PASS；L2 真实 Conda 求解、bundle ABI 审计和离线 solver preflight 尚未通过，故 G2 未完成；L3 人类接受待定。

PR #5 当前 OPEN，base 为 `step4b-atac-footprinting@6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`，已推送 HEAD 为 `222a82690ee8e41beab407c6e18c0a41de2b0071`。GPT 对该 exact HEAD 的结论是 `REQUEST_CHANGES`，唯一剩余项 F9：当前状态摘要与已推送 HEAD 不一致。F1–F8 的实现审核通过。当前只做 Worklog、CODEX_HANDOFF、dated handoff 与 PR body 的审计状态同步；新 HEAD 获得明确 APPROVE 前，不在 Argos 下载或构建。

Argos 接入路径已由交接指南和此前只读 SSH 核对确认：`ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu`。Argos 主机有计算资源；旧 Docker 路线受限于账号无 Docker socket 权限，不代表 Argos 不可用。记录中的 `pmafp` Python 3.11.17 环境和部分 `pma_hint` 必须原样保留。新 PR HEAD 获得明确 APPROVE 后，按 G2 授权先核对 Cloud Code 建立的环境与现存 prefix，再执行 artifact-only 构建和离线预检。

Argos 资源可访问：此前只读检查显示 72 CPU、约 1 TiB RAM、约 923 GiB 可用内存及充足外部存储。此前受阻的是 `zz950` 无 Docker socket 权限且没有可用容器运行时；Argos 并非没有计算资源。PR #5 未改动 `pmafp`；部分 `pma_hint` 需要保留。此前 HINT CLI preflight 曾以 `HINT_CLI_PREFLIGHT_FAIL` 结束，没有启动分析。

PR #5 的阶段范围是外部 HINT bundle artifact 构建及既有 offline preflight。不得创建/安装新 Conda 环境、运行 HINT CLI、smoke/小 BED 或正式首轮分析；这些步骤需要后续阶段门。不得合并 PR #5，除非用户另行明确要求。

## GPT findings 与当前本地修复

- F1：mock 显式接收 Conda `env`，核对外部缓存和 dry-run prefix 不变量。已关闭。
- F2：之前 wrapper 在 builder 非零退出时受 `set -e` 影响，跳过 stdout 脱敏。新增 `run_redacted_command.py`，逐行流式脱敏后写日志并返回子进程原始退出码；行为测试检查带 token 的 URL 和 exit 23。
- F3：EXIT trap 在工具准备失败后仍采集、脱敏并比较 `pmafp` 前后 Conda/pip 清单。已关闭。
- F4：在线求解前后分别留存 `linux-64/noarch` 原始 `repodata.json` 到外部 evidence/work，并写 sidecar 记录 snapshot id、subdir、文件名、清理后的 URL 与原始 SHA-256；solver closure/provenance 引用使用的 after snapshot 和 LINK identities。测试校验保留文件的字节 hash。
- F5：PATH 优先选择审计过的 Conda 所在目录，并比较 builder 解析到的可执行文件。已关闭。
- F6：验证 wheel `Requires-Python`、文件名与 WHEEL tags、`Root-Is-Purelib` 和 py3-none-any 文件中的 ELF/native payload。已关闭。
- F7：数据输入根目录已与 `PMA_DATA/atac_footprint` 比较；输出保护名单现在还加入规范化的整个 `BIO_DATA` 和 `PMA_DATA`，防止 work/cache/evidence 写进同一数据树。wrapper 测试覆盖 PMA_DATA 下错误 work path。
- F8：工具准备前设置 `PIP_NO_CACHE_DIR=1`，并把 `PIP_CACHE_DIR` 与 `TMPDIR` 指向 external workspace；测试检查传给准备步骤的环境值。
- F9：更新 Worklog、CODEX_HANDOFF、dated handoff 的当前状态，记录已推送 SHA `45b785b...` 的 `REQUEST_CHANGES`、本地修复、测试数字与下一步。

本轮测试还发现 host provenance inline Python 使用 `shutil.which` 但缺少 `import shutil`；已补上，并由完整 wrapper failure-path test 覆盖。

## 当前验证

当前本地代码：

- `python3 -m unittest tests/test_hint_bundle_build_contract.py`：27 项通过；
- 修改的 Python 文件 `py_compile`：通过；
- `bash -n scripts/04b_footprint/run_hint_bundle_builder_argos.sh`：通过；
- `git diff --check`：通过。

均为本地合同/mock 检查，未证明 Argos 上真实 Conda solver、上游 repodata、工具 wheel 下载、RGT wheel/native ABI audit、完整 bundle 或 offline preflight 成功。上述代码修复已在 `222a826` 推送；该 exact HEAD 的 GPT review 仅要求 F9 状态同步，修订后的新 SHA 尚待复审。

## 下一步

1. 提交并推送 F9 审计状态同步，只包含本任务 Worklog、CODEX_HANDOFF 和本 handoff；更新 PR body 到新的完整 SHA。
2. 在持久 PMA GPT 对话中请求 exact-head review；若有新 finding，在同 PR 最小修复并再次复审。
3. 新 HEAD 获得明确 `APPROVE` 后，按授权范围在 Argos external workspace 做 bundle 构建和离线 preflight。
4. 每个外部命令、退出码、日志目录、manifest、bundle hash 和失败原因写入 Worklog/handoff。数据、缓存、bundle 和结果不得进入仓库。preflight 失败则停下并保留完整证据，不修改 `pmafp` 或部分 `pma_hint`。
