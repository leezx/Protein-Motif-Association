# Step 4b-1 Argos 原生 bundle builder 交接

更新时间：2026-10-18 10:22 EDT
仓库：`Protein-Motif-Association`
基线：PR #4 merge commit `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`，目标分支 `step4b-atac-footprinting`
工作分支：`task_20261018_argos_artifact_builder`
PR：[#5](https://github.com/leezx/Protein-Motif-Association/pull/5)

## 状态与边界

PR #5 的代码 HEAD `483c38bf40b258b2ee2d42a45086f13dcc26d0d9` 已由 GPT 精确审查，结果为 `REQUEST_CHANGES`，finding F1–F7。修复正在同一 PR 的本地工作树进行，尚未推送或复审。该 HEAD 没有获得 APPROVE；不得据此在 Argos 下载、构建或运行分析。

Argos 资源本身可访问：此前只读检查显示 72 CPU、约 1 TiB RAM、约 923 GiB 可用内存以及充足外部存储。此前受阻的是 `zz950` 无 Docker socket 权限且找不到可用容器运行时；Argos 并非没有计算资源。已有 `pmafp` 未被本 PR 改动，部分 `pma_hint` 需要保留。旧 HINT CLI preflight 曾以 `HINT_CLI_PREFLIGHT_FAIL` 结束，没有启动分析。

PR #5 的已授权范围是外部 HINT bundle 构建和既有离线 preflight。当前改动获批后仍不得创建/安装新 Conda 环境、运行 HINT CLI、smoke/小 BED 或正式首轮分析；这些步骤需要后续阶段门。不得合并 PR #5，除非用户另行明确要求。

## GPT F1–F7 和本地修订

- F1：Conda dry-run mock 接收并核对 `env` 参数与外部包缓存。
- F2：拒绝含凭据、query、fragment 的 Conda channel；持久化 solver 证据和环境清单前清理 URL；测试扫描完整证据目录。
- F3：在成功记录 pmafp 前置清单后立即注册 `EXIT` trap；准备工具失败时仍收集后置 Conda/pip 清单、比较并记录完整性状态。新增模拟准备失败的 wrapper 集成测试。
- F4：比对 LINK dependency/constraint 与冻结上游 repodata；归档 `info/index.json` 的差异只有存在冻结 repodata URL/hash 和 solver 记录时才接受，并把差异写入 provenance。添加 hotfix 正例和无证据负例。
- F5：PATH 优先加入审计过的 Conda 所在目录；builder 必须比较 `which conda` 和 host report 所指 Conda 的解析路径。
- F6：wheel 校验 Python 版本约束、文件名 tag 与 `.dist-info/WHEEL` tag 一致、`Root-Is-Purelib` 和 py3-none-any 内容中不含 ELF/native 文件；添加负例。
- F7：wrapper 从仓库 `config/pma_env.sh` 读取 `PMA_DATA`，数据入口必须等于规范化后的 `PMA_DATA/atac_footprint`；添加错误 DATA 根目录负例。

## 当前验证

最近运行：

- `python3 -m unittest tests/test_hint_bundle_build_contract.py`：25 项通过；
- 对修改的 Python 文件执行 `py_compile`：通过；
- `bash -n scripts/04b_footprint/run_hint_bundle_builder_argos.sh`：通过；
- `git diff --check`：通过。

均为本地合同/mock 检查，未证明 Argos 上真实 Conda solver、外部工具下载或 bundle/preflight 成功。PR #5 修订仍处于本地未提交状态，完整 HEAD 待生成。

## 下一步

1. 检查完整 diff 与状态；显式提交仅包含本任务代码、测试、`Worklog.md`、`docs/CODEX_HANDOFF.md` 和本 handoff 的文件。
2. 推送同一 PR #5，同步 body 到新的完整 SHA，在持久 PMA GPT 对话中请求对精确 HEAD 的复审。
3. 若 GPT 返回 `REQUEST_CHANGES`，在同 PR 按 finding 最小修复、复跑受影响测试并复审；若返回 `APPROVE`，按既有范围在 Argos external workspace 做 bundle 构建和离线 preflight。
4. 每个 Argos 命令、退出码、日志目录、manifest、bundle hash 和失败原因写入 Worklog 与 handoff。数据、缓存、bundle 和结果不得进入仓库。preflight 失败则停下并保留完整证据，不修改 `pmafp` 或部分 `pma_hint`。
