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

### 2026-10-18 11:18 EDT 实时状态：F2.1/F2.2 修复待 exact-HEAD 复审

GPT 对 PR #5 的完整 HEAD `8d3e72d11ad82d4612f0ea4b61dc26b0c882b33b` 给出 `REQUEST_CHANGES`。剩余两项 blocker：F2.1，实际 `python -m pip wheel`/build backend 子进程须在启动时先初始化并验证 external setuptools/distutils；F2.2，builder 当前进程与后续子进程须检查所有已加载第三方模块来源，拒绝宿主 `site-packages` 的传递依赖。其余直接模块、metadata、版本、distutils 与 exact SHA 检查通过。

同一 PR 的定向修复尚未提交：新增 `sitecustomize.py`，通过 builder 子进程继承的 `PYTHONPATH` 与 external Python root 在解释器启动阶段执行 fail-closed startup probe；builder `require_builder()` 直接审计当前进程中的全部已加载模块。来源 allowlist 包括 Python 标准库/runtime、builder 脚本目录和锁定 external toolchain。新增真实 `python -m pip` 子进程启动检查、在 Argos external toolchain 可用时执行真实 `pip wheel --no-build-isolation` 的临时 sdist 测试，以及宿主 site-packages 传递依赖注入负例。

用户要求计算资源使用 Argos，Mac mini 不再跑测试/构建/分析。遵守 exact-head 门禁，本轮没有向 Argos 下发命令；本地未运行测试。已完成 Git 状态/完整 diff 静态检查，`git diff --check` PASS；未运行单元测试、py_compile 或 shell 测试。代码和 handoff 已完成审阅与更新；下一步提交推送同一 PR 并请求 GPT exact-head APPROVE。获批后先在 Argos 运行合同与真实 pip-wheel 子进程测试，再在第三个全新 external workspace 执行已授权的 artifact-only G2 和既有 offline preflight。已有失败 workspace `/home/zz950/PMA_fetch/pma_pr5_g2_ede0f81/`、`/home/zz950/PMA_fetch/pma_pr5_g2_1c60023/` 保持原样；不改环境、不跑 HINT/smoke/full analysis、不合并 PR #5。

较早的 F9 状态记录：PR #5 当时已推送 HEAD 为 `222a82690ee8e41beab407c6e18c0a41de2b0071`，GPT 要求同步审计摘要。该状态已被后续提交和审查取代；以本文件最新时间戳状态为准。

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

## 2026-10-18 11:07 EDT — G2-F2 修复 setuptools/distutils 导入顺序冲突

在已获 GPT exact-head APPROVE 的 `1c600230918cf3a50a94b0abd0965c8d609e8240` 上，于全新外部工作区 `/home/zz950/PMA_fetch/pma_pr5_g2_1c60023/` 重跑 G2。六个锁定 wheel 下载、SHA-256 校验和解包通过；随后 `prepare_hint_argos_toolchain.py` 的 import probe 失败。完整 traceback 位于 `toolchain/toolchain-import-probe.log`：`setuptools._distutils_hack.ensure_local_distutils()` 看到 `pmafp/lib/python3.11/distutils/core.py` 而断言失败。只读重现确认，同一解释器、PYTHONPATH 和目录下先导入 pip 再导入 setuptools 会失败，先导入 setuptools可从 external `setuptools/_distutils` 加载。GPT 独立诊断建议显式固定 `SETUPTOOLS_USE_DISTUTILS=local`，先初始化锁定的 `_distutils_hack`/setuptools、再导入 pip，并验证 distutils、第三方模块及 distribution METADATA 来源；在 preparation 和 builder 入口重复该来源 probe。

按诊断在同一 PR 本地修复：新增 `probe_hint_argos_toolchain.py`，验证 distutils policy、`_distutils_hack` 来源、setuptools-first 导入、`distutils.core` 确实来自 external `setuptools/_distutils`、六个锁定模块版本与来源、六个 METADATA 来源及已加载第三方 `sys.modules` 路径。准备步骤和 builder 入口调用同一 probe；Argos wrapper 将 local 策略传给 builder/pip 子进程。测试覆盖外部导入通过、宿主 metadata/distutils 误选与 stdlib policy fail closed、builder 入口重验和 wrapper 环境传递。

本地验证：`python3 -m unittest tests/test_hint_bundle_build_contract.py`（37 PASS）；相关 Python `py_compile`、wrapper `bash -n`、`git diff --check` PASS。新增修订目前尚未提交/推送或复审，因此不得在 Argos 重试。两个失败工作区都保留；`pmafp` 前后 Conda/pip manifest 相同、`PMAFP_INTEGRITY_OK`；未运行 solver、bundle、ABI audit 或 offline preflight，未创建/安装环境、未运行 HINT/分析。下一步是核对 diff、提交推送同一 PR #5、同步 PR 描述并请求新完整 HEAD 的 GPT exact-head review；APPROVE 后才可在第三个新工作区重试 artifact-only G2。

### 最新门禁状态（2026-10-18 11:18 EDT）

前述 11:07 记录是 G2-F2 修复前的历史执行和本地测试结果。当前 PR #5 远端 HEAD 为 `8d3e72d11ad82d4612f0ea4b61dc26b0c882b33b`，GPT 对其返回 `REQUEST_CHANGES`（F2.1/F2.2）。随后新增的启动 hook、builder 当前进程来源校验与测试目前尚未提交；本轮未在 Mac mini 跑测试，未向 Argos 发命令。静态审阅已完成，`git diff --check` PASS；其余验证待 Argos 门禁许可。修订推送同一 PR 并再次请求 GPT exact-head review；明确 APPROVE 后才在 Argos 运行合同测试及 G2。不得触碰两个已失败 workspace，不修改 Conda 环境，不运行 HINT/smoke/full analysis，不合并 PR #5。
