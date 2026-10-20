# PRINT 持久评分调度与 8-peak 验收候选

时间：2026-10-20 13:06 EDT

范围：PMA Step 4b footprint，仅 PR #8。ChIP BED6/PR #7 由 Claude 负责。

## 当前状态

用户授权修改本地 PRINT 源码。固定 `PMA｜固定阶段审核` 对话建议：保留 PRINT 原生计数/评分语义，实现持久评分 worker 调度后，先用 8 个原始 peak 做一次实现验收。该答复是技术建议，不是当前代码 exact-head 审核或 Argos 运行许可。

此前 64-peak、2-worker 的 PRINT V2 一次运行在 30 分钟预算时退出 124，caller 已运行 1,710.18 秒；采样进程组 RSS 峰值约 17.09 GiB；105 次评分调用完成、106 次开始。没有完整 track、event BED 或 timing TSV。该运行不支持准确度或全峰时间推断。V1/V2 均已消耗，不得重试。

## 本次本地候选改动

- `run_print.R` 保留原生 `getCountTensor()`，生产路径使用其 `returnCombined=FALSE` 磁盘分块 count tensor，不重新扫描/转换 fragments 文件。
- 评分按原始 BED 顺序分块：最多 500 个峰或累计 1,000,000 bp，先到者切分；单个超长峰完整处理。
- 父进程逐批读取 native count chunk 和 HDF5 bias slice；不向 workers 广播整个 count tensor、bias HDF5 handle 或全染色体 bias。
- 建立一个 16-worker PSOCK 评分池并跨块复用；每个 worker 任务处理一个原始 peak 的 r10/r20 两尺度。
- 使用 pinned `regionFootprintScoring()` 的原公式，显式 `scoreType="pval"`、`flankRadius=radius`、原始区间、count、bias、cell/group label 和返回设置。
- 单 bulk 组时 PRINT 原 scorer 内部 `sapply()` 会丢掉 singleton 维度。兼容包装只在 `sapply()` 恰有一项且结果为向量时补回一列矩阵，并给字符组标签列名；多组行为保持不变。函数公式不改。
- 逐峰检查位置×1组矩阵形状、完整原始宽度和轨道坐标；每个完整 chunk 的 track/event part 原子写出，并逐 chunk 保存 row/interval/hash manifest。最终两尺度先分别通过行数、part SHA 与 gzip 完整性验证，再发布最终文件；最后生成 `.complete.tsv`。
- V4 实现验收固定原有 8 个 peak，16 workers、r10/r20、强制 3/3/2 chunk，和旧分组 `getFootprints()` caller 路径逐峰比较 16 个 peak-radius 结果；最终 gzip track 和 event BED 重读后再次核对坐标及数值。V4 不代表全峰结果或准确度排名。

## 验证证据

本地通过：

- R parser：`print_variable_width.R` 与 `run_print.R`。
- `Rscript tests/test_print_variable_width.R`：原始顺序、3/3/2 分块、500 峰/1 Mb 双上限、超长单峰、singleton bulk matrix、多组路径不变、duplicate rows、空 event BED、part hashes/行数及 completion marker。
- `python3 -m py_compile`：PRINT wrappers 与监督测试。
- `python3 tests/test_print_speed64_supervisor.py`。
- `python3 tests/test_select_print_integration_smoke.py`。
- `python3 tests/test_print_smoke_deadline.py`。
- `bash tests/test_step4b_runner_contract.sh`。
- `git diff --check`。

contract test 中的 `BAM_CONVERSION_FAIL` / `BAM_PREP_FAIL` 是预期失败分支，最终 fixture 显示 PASS。Mac 本地 R 缺少 `hdf5r`、`survcomp`；未在 Mac 处理 ATAC 数据，也未运行 PRINT S4/PSOCK caller。故真实 HDF5、远程依赖与 scorer 等价性仍未验证。

候选源码 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `scripts/04b_footprint/run_print.R` | `e3be118cda14f028b458a111e38be0b260ef1f54b368e5d7890a11bb31ec3caa` |
| `scripts/04b_footprint/print_variable_width.R` | `d2f6a30b9c712bc22d8fd70d945bd84c85eb5ed0643386050930f21af21fdaab` |
| `scripts/04b_footprint/run_print_fullpeak_supervised.py` | `f5fcee3a1d768758042b5edae0e1265fb5be4a518cf622cf5b297415819ac710` |
| `scripts/04b_footprint/run_print_integration_smoke_supervised.py` | `5982c5a30c27ba7f22a30cbf1f63661b1018505d9d9656b0c570ba70d8d5dffb` |

## 唯一下一步与边界

代码和 handoff 已在现有分支提交为 `d60ca250d53318c2b2232ddeb01b330687d6499d` 并推送；PR #8 OPEN。加入本次提交/验证记录后，先推送最后的审计增量、核验 GitHub live exact HEAD，再在唯一固定 PMA 项目对话请求 Quick L1/L2 review，要求明确审查该最终 HEAD，并只请求一次 V4 8-peak Argos gate 调用放行。不得在审核前建远程 code-stage、发 gate、安装/更新依赖或运行分析。批准后仍必须 fresh-check 主机、CPU/RAM、输入/模型/immutable gate 哈希、依赖、路径权限、无残留；复制五个精确审查文件并核验 SHA。任何一项不符即停止。调用 V4 后无论成功/失败都不重试。

V4 固定：16 workers；r10/r20；30 分钟端到端执行预算；每进程 44 GiB `RLIMIT_AS`；采样进程组 40 GiB RSS soft-stop（不是硬 aggregate cap）；CPU-only；复用既有 fragment file。运行只提供实现/计时/资源证据，不测准确度，不授权全峰、不改环境、不合并。

### Review-task 状态

- L1：本地静态/合同验证 PASS；真实 Argos caller 集成未验证。
- L2：bulk singleton 维度修复和 native scorer 语义需 8-peak 实测，当前 UNVERIFIED-critical；准确度不在此步骤测。
- L3：用户方向仍是从 bulk ATAC peak 内调用 motif-free PRINT footprint；当前没有新 footprint 输出，进展是候选实现准备完毕。
- Trust：本地验证高；真实运行正确性和全峰资源推断目前低/未建立。
