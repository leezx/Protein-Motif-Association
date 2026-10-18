# Step 4b-1 Argos 原生 bundle builder 交接

## 2026-10-18 12:15 EDT — 当前门禁：fd35a31 的 F4/F5 修复待提交和复审

PR #5 仍 OPEN，base 为 `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`，远端 HEAD 为 `fd35a31b087e9472006d8315863722e1e74448c3`。持久 PMA GPT 对这个完整 HEAD 给出 `REQUEST_CHANGES`：F4 要求检查真实 `sys.path` 的完整 allowlist，拒绝任意 `.pth` 注入的 `other_python_libs` 之类路径；F5 要求真实 `pip wheel` build backend 证明 `packaging` 来自锁定 external root、`jaraco` 来自锁定 setuptools `_vendor`，且无宿主 site-packages 模块。已认可前一轮 Python 3.11 选择、vendor 优先级方向和 canonical fixture。

同一 PR 的本地最小修复：startup probe 检查所有实际搜索路径，只准仓库脚本/根目录、Python 标准库、锁定 external root，以及 protected external workspace 内的**当前工作目录**；宿主 site-packages 路径继续删除，预先加载的宿主模块继续 fail closed。Wrapper 显式传递 protected workspace，builder 核对其与 toolchain 父目录一致。测试增加任意非 site-packages 路径负例、真实 pip wheel 后端的 packaging/jaraco/distutils/已加载模块来源断言。用户指定计算只在 Argos，故 Mac mini 未运行测试、构建或分析；新代码也尚未向 Argos 下发命令。需先提交/推送并取得新完整 HEAD 的 GPT `APPROVE`，然后仅在 Argos 执行合同测试；通过后才可继续 artifact-only G2/offline preflight。失败日志与旧 external workspace 保留，不修改 Conda 环境，不运行 HINT CLI/smoke/full analysis，不合并 PR #5。

本 PR 只推进 PI 目标二的 HINT runtime 前置条件，尚未形成四工具 benchmark；目标一的 raw human hg38 archive 已在 Argos，但唯一坐标 BED6 尚未设计和构建。下一次科学验收仍是四工具同输入 smoke 与 BED6 契约/产物 QC。`HUMAN DECISION: PENDING`。

## 2026-10-18 12:00 EDT — 三项 Argos 合同失败的同 PR 修复待审核

本 PR 对 PI 的第二项目标只提供 HINT runtime 前置条件，尚未产生 footprint benchmark；下一科学验收为 PRINT、TraceBIND、HINT、TOBIAS 四工具同输入 smoke。第一项目标的 21 GB raw hg38 archive 已在 Argos，现有 443,029,514 行、24 列处理文件不符合“全部 human ChIP-seq、坐标唯一 BED6”，需另行定稿聚合语义并在 Argos 生成。

持久 PMA GPT 对当前已推送 HEAD `46f973278e5801b25b85e7b1a1d6b98c4c1c9ae1` 给 audit-only APPROVE；Argos 上此前 40 项合同测试 3 个失败仍是阻断门禁。按 GPT 的定向意见，本地同 PR 修复尚未提交：wrapper 在首个 Python 调用前固定 pmafp/bin/python 并核验 3.11；startup probe 先拒绝已加载宿主模块，再删除 Conda host site-packages 搜索路径，把已锁定 setuptools wheel 自带的 `_vendor` 放在 external 顶层包路径之后；builder 只接受审计过的两段 PYTHONPATH。测试 fixture 使用 canonical root 和明确解释器，并覆盖 vendor/locked 优先级、宿主模块拒绝、反转或额外路径。未削弱 origin fail-closed。

静态 `git diff --check` 通过；未在 Mac mini 运行测试或分析，未向 Argos 发新命令，没有环境改动/构建/CLI/smoke/full-run。下一步提交推送、同步 PR body、请求新完整 HEAD GPT 复审；只有明确 APPROVE 才在 Argos 跑合同测试，通过后才进入 artifact-only G2/offline preflight。失败证据和所有旧 external workspace 保留；PR #5 OPEN，禁止未经用户单独确认合并。15 分钟 heartbeat 已改为持续监控两项最终目标。

## 2026-10-18 11:48 EDT — 目标对照与实时状态

**PI 两项最终产出：** (1) human-only ChIP-Atlas 的坐标唯一标准 BED6，允许一个 region 对应多个 ChIP-seq experiment；(2) 对比全部 motif-free footprint callers 的 genome-wide 无偏检测、准确度和运行速度，再与冻结 motif reference 整合。后续每次 PR/GPT review 都要列出对其中哪项的推进、可验证产物和下一验收条件。

**十轮验收路径：** BED6 语义定稿 → builder/fixtures → Argos 产物与 QC → HINT runtime → 四工具同输入 smoke → 首轮调用与速度/事件统计 → matched-recall 准确度评估 → B2/B3 验证 → genome-wide run 与工具选择 → footprint-motif 整合报告。每轮 review 记录轮次及可测产物；失败时记录具体 blocker 和修复，不宣称完成。

ChIP-Atlas 原始 hg38 21 GB archive 与 `experimentList.tab`、`fileList.tab` 已在 Argos；现有处理文件是 443,029,514 行、24 列的 BED6+18，按有限 antigen classes 过滤，不能当作用户要求的 reference。可以复用现有下载；去重与多实验字段规则须纳入新设计并审核。

Footprint 的 fragment/region inputs 已就绪、当前无 caller 进程。Argos 有 TOBIAS 0.17.5、RGT 1.0.2 和用于 PRINT/TraceBIND 的 r4p3 R stack。RGT 在共享 `pmafp` 中与 NumPy 2.4.6 冲突，因此需要独立 HINT runtime。PR #5 builder 只推进这个前置项，尚无 caller benchmark 结果。

PR #5 exact approved HEAD `6ec6fc230aec422c1124aeb42ee71c308d23de81` 的 Argos contract suite 已运行 40 tests、3 failures：import-origin fixture 的路径顺序不匹配；pip wheel 因 host `pmafp/site-packages/jaraco` 被 fail-closed probe 拒绝；wrapper test 由于 PATH 选中 Argos 系统 Python 3.5.2 而失败。完整日志：`/home/zz950/PMA_fetch/pma_pr5_g2_tests_6ec6fc2/contract-tests-discovery.log`。`py_compile`、`bash -n` 通过，`pmafp` manifests 前后相同。没有 bundle、环境变更、HINT/smoke/round-1。错误日志保留，不得绕过 gate；PR #5 修复需同一 PR 最小变更和新 exact-head GPT approval。

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

用户要求计算资源使用 Argos，Mac mini 不再跑测试/构建/分析。遵守 exact-head 门禁，本轮没有向 Argos 下发命令；本地未运行测试。已完成 Git 状态/完整 diff 静态检查，`git diff --check` PASS；未运行单元测试、py_compile 或 shell 测试。修复提交 `da8e9b464ead2acde39207ee1e3e69add06f9a39` 已推送到同一 PR #5，PR body 已同步；当前待 GPT exact-head review。获批后先在 Argos 运行合同与真实 pip-wheel 子进程测试，再在第三个全新 external workspace 执行已授权的 artifact-only G2 和既有 offline preflight。已有失败 workspace `/home/zz950/PMA_fetch/pma_pr5_g2_ede0f81/`、`/home/zz950/PMA_fetch/pma_pr5_g2_1c60023/` 保持原样；不改环境、不跑 HINT/smoke/full analysis、不合并 PR #5。

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

### 最新门禁状态（2026-10-18 11:38 EDT）

PR #5 仍 OPEN、未合并；base 为 `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`。GPT 对 predecessor `e078a8d4df23bc446ed921e3ef2af245785c1513` 的 APPROVE 仅允许合同测试与此前限定的 artifact-only G2/offline preflight。Argos 启动测试在 Python `sitecustomize` 阶段 fail closed，exit 78：`ARGOS_TOOLCHAIN_DISTUTILS_ORIGIN_MISMATCH` 指向 `pmafp/lib/python3.11/distutils/core.py`；完整日志保留于 `/home/zz950/PMA_fetch/pma_pr5_g2_tests_e078a8d/toolchain-startup-test-failure.log`。测试未进入 unittest discovery；未运行 solver、bundle/ABI audit、offline preflight、HINT CLI、smoke 或分析，未改任何环境。

只读 Argos 重现确认 pmafp `.pth` 加载的 external `_distutils_hack` 与 external setuptools 在 pip 查询前能正确解析到 `setuptools/_distutils`；导入完整 probe 模块本身没有预加载 distutils。原 `probe_startup()` 在 setuptools 初始化后执行 `importlib.util.find_spec("pip")`，触发 setuptools 80.9.0 finder 的 pip 特例，清理 local distutils 并禁用 finder。生产修复已改为直接核验 external `root/pip/__init__.py` 与 distribution metadata。GPT 对当前 HEAD `e8d8b51afc4ab0af98651a14401635bb1186c028` 给出 `REQUEST_CHANGES`，唯一 finding G2-F3-T1：fake finder 被放在共用 fixture，导致正常 `python -m pip` 正向测试也会触发清理；真实 `pip wheel` 测试还须断言 build backend 使用的 `distutils.core` 来自 external `setuptools/_distutils`。当前按 finding 的最小修订在本地进行，未跑测试。

下一步：把 fake finder 限定到专门的 regression fixture，并在真实 `pip wheel` 的临时 setup.py 中断言 `distutils.core.__file__` 来源；更新 Worklog/PR 描述，提交并推送同一 PR #5，再请 GPT 审核新的完整 HEAD。必须取得新的 exact-head APPROVE 才能在 Argos 继续。随后先跑合同套件和真实 `pip wheel` 子进程测试，通过后才在新的 external workspace 续跑 artifact-only G2 与既有 offline preflight。两个失败工作区保持不动；`pmafp` 与部分 `pma_hint` 不改；不运行 HINT CLI/smoke/full analysis，不合并 PR #5。
