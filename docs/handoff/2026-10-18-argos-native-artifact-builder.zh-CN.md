# Step 4b-1 Argos 原生 bundle builder 交接

时间：2026-10-18 10:05 EDT  
仓库：`Protein-Motif-Association`  
基线：PR #4 merge commit `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`，目标分支 `step4b-atac-footprinting`  
当前分支：`task_20261018_argos_artifact_builder`  
PR：[#5](https://github.com/leezx/Protein-Motif-Association/pull/5)，当前代码提交 `f692499ff9bbdd38c36940cf35ea2c68bb994c13`；GPT 精确 HEAD 审核待提交。

## 目标与范围

PR #4 已按用户指示合并。为了继续使用 Argos 完成 HINT bundle 准备，新分支正在增加无需 Docker/容器权限的 Argos-native builder。所有工具、包缓存、bundle、证据均放在仓库外的 external workspace。此阶段只覆盖 bundle 构建和现有离线 preflight。创建新 Conda 环境、安装、HINT CLI、smoke/小 BED、正式首轮分析仍须后续 stage gate。

在新 PR 的完整 HEAD 获得 GPT 明确 `APPROVE` 前，不执行 Argos 下载或构建。不能合并新 PR，除非用户另行明确要求。

## Argos 现场事实

- SSH 可用：`zz950@rcapps3.dfci.harvard.edu`，解析到 `rcGPUs.dfci.harvard.edu`；只读检查见 72 CPUs、约 1 TiB RAM。
- 有 Docker CLI，但账号无法访问 `/var/run/docker.sock`。
- `/usr/games/singularity` 是 Debian 游戏启动脚本，不是 Singularity/Apptainer。
- `pmafp` 当前是 CPython 3.11.17，没有 `auditwheel`、`pyelftools`；RGT 还因 NumPy 2.4.6 移除 `numpy.mat` 无法导入。
- 部分 `pma_hint` 缺少 `bin/python` 和 `conda-meta`，必须保留。
- `/data/.../atac_footprint/processed/round1` 已存在；不能覆盖。此前 HINT CLI preflight 以 `HINT_CLI_PREFLIGHT_FAIL` 结束，未启动分析。

结论：Argos 资源可访问；旧流程的镜像 builder 权限/工具依赖不适用。主机环境与旧 bundle 入口之间的缺口由本分支解决。

## 本分支变更

- `scripts/04b_footprint/build_hint_bundle.py`：新增 `argos-native` 模式、独立外部工具链导入验证、Conda 缓存隔离、solver 冻结记录、本地标准 repodata、离线 LINK 身份比对、主机来源记录，以及 URL 凭据/查询参数清理；保留 Docker 模式。
- `scripts/04b_footprint/prepare_hint_argos_toolchain.py`：按锁文件哈希下载纯 Python wheel，校验名称、版本、依赖闭包并解压到外部目录；不安装进 Conda prefix。
- `scripts/04b_footprint/run_hint_bundle_builder_argos.sh`：验证输出位于 workspace 且不触及 checkout、Conda 前缀、DATA 根目录；保存 `pmafp` 前后 Conda/pip 清单并限制内存。
- `tests/test_hint_bundle_build_contract.py`：增加 URL 清理和本地 repodata 的合同 fixture。

## 当前验证

已运行并通过：Python `py_compile`、新 wrapper `bash -n`、`git diff --check`。未运行单元测试套件（本轮尚无用户要求运行测试）；未执行网络下载、Argos 命令、bundle 构建、环境变更或分析。Conda 实际 solver 对本地 repodata 的兼容性、wheel/ELF 真实审计仍待批准后的 G2 验证；遇到缺包或不匹配必须 fail closed，保留日志，不绕过。

## 下一步

1. 完成 PR #5 的 handoff/worklog 审计同步并推送，确认 GitHub 当前完整 HEAD。
2. 将 PR 完整 HEAD 提交到持久 PMA GPT 对话，等精确 SHA 的 `APPROVE`。`REQUEST_CHANGES` 时仅按当前 findings 在同一 PR 最小修复，再完整复审。
3. 获批后，才在 Argos 的 external workspace 准备工具轮子和 bundle；之后执行既有离线 preflight。收集主机 provenance、wheel/Conda 哈希、solver/offline solver 结果和完整失败日志供下一轮审阅。
4. 不安装、不运行 HINT CLI 或 smoke/正式分析，除非后续 stage gate 与用户授权明确放行。
