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
| `scripts/04b_footprint/run_print.R` | `f388b705d021862ff99e45cda576c43194b3234fc457b2afc79308f49f135c31` |
| `scripts/04b_footprint/print_variable_width.R` | `6657838e9e1d95ff08124b95fc78da9aae266ddce5b83e255c59d4d5ad8069b0` |
| `scripts/04b_footprint/run_print_fullpeak_supervised.py` | `af29005f2ec0101100303be50227fe0f94a13d9cb25cb5a07a8a6159efaa44c0` |
| `scripts/04b_footprint/run_print_integration_smoke_supervised.py` | `34f3d550da0ca74e2f1d4f5c0b03d81dcd3a2000e0ce904b54caeb9e3d5a0ea5` |
| `scripts/04b_footprint/select_print_integration_smoke.py` | `7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856` |

## 唯一下一步与边界

代码提交 `d60ca250d53318c2b2232ddeb01b330687d6499d` 与后续审计提交已推送到同一分支；PR #8 OPEN、未合并。V4 候选经过后续 review repair，具体情况见下方。

V4 固定：16 workers；r10/r20；30 分钟端到端执行预算；每进程 44 GiB `RLIMIT_AS`；采样进程组 40 GiB RSS soft-stop（不是硬 aggregate cap）；CPU-only；复用既有 fragment file。运行只提供实现/计时/资源证据，不测准确度，不授权全峰、不改环境、不合并。

### Review-task 状态

- L1：本地静态/合同验证 PASS；真实 Argos caller 集成未验证。
- L2：bulk singleton 维度修复和 native scorer 语义需 8-peak 实测，当前 UNVERIFIED-critical；准确度不在此步骤测。
- L3：用户方向仍是从 bulk ATAC peak 内调用 motif-free PRINT footprint；当前没有新 footprint 输出，进展是候选实现准备完毕。
- Trust：本地验证高；真实运行正确性和全峰资源推断目前低/未建立。

## 2026-10-20 13:19 EDT — 修复固定 PMA 对 V4 候选的两项 review finding

固定 `PMA｜固定阶段审核` 对 exact HEAD `8b60f31c480736046ec62c9cc85de81a819d9d63` 给出
`REQUEST_CHANGES`。第一项指出原 `footprint_r10/r20` 实际计的是 scorer 已完成后的轨道/事件整理与分块写出；第二项指出旧分组
`getFootprints()` oracle 在执行前已被全局替换为 bulk-safe scorer，因而不独立。

同 PR 最小修订：

- 在 `parLapplyLB()` 周围单独累计联合 `r10+r20` 评分派发墙钟，字段为
  `score_dispatch_r10_r20`；各尺度分块表构造、part 写出/哈希字段改为
  `output_materialization_r10/r20`。`pipeline_wall_through_validation_including_legacy_oracle`
  明确包含旧路径对照成本；外层 watchdog 的 caller wall 是独立总运行时间。
- 保存源自 pinned PRINT 的未包装 scorer。旧 `getFootprints()` 路径临时在其词法环境绑定原 scorer，
  并通过 `on.exit` 在成功和异常时恢复 bulk-safe worker scorer。新 worker 继续使用包装版。
- 回归 fixture 断言 oracle 使用 native scorer，并在正常及错误返回后恢复包装器。监督器计时门槛改成
  要求新的联合评分派发与输出物化/发布字段。

本地重新运行：R 测试/解析、两个监督器 Python 编译、PRINT speed supervisor 测试、8-peak selector
测试、deadline 测试、runner contract fixtures 与 `git diff --check` 均通过。contract fixture 输出的
`BAM_CONVERSION_FAIL` / `BAM_PREP_FAIL` 是其预期负向分支，最终 PASS。真实 HDF5/S4/PSOCK 路径仍未验证。
未访问 Argos、未 staging、未调用 gate。本修订后仍需推送，并在同一固定 PMA 对话复审新 exact HEAD；
旧的 V4 单次提议不视作批准，需新的明确放行才可运行。

计时监督器现在接受两种明确的 runner pipeline wall 字段（常规路径和包含 oracle 的验证路径），并强制
检查联合评分派发字段及两个尺度的输出物化/发布字段；对应单元测试验证两种合法形式和缺失评分字段。
