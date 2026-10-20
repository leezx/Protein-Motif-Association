# PRINT variable-width bias 输入契约修复

时间：2026-10-20 09:43 EDT
范围：仅 footprint PR #8；不涉及 ChIP BED6/PR #7。

## 起因

V6 在 `getPrecomputedBias()` 阶段失败，未进入 counts 或 footprint 计算。日志为 `Item 1597 has 28 columns, inconsistent with item 1 which has 100 columns`。固定 PMA 审核确认 `1597` 是 100 区域一块的块序号；159,628 个输入区域留下 28 个区域的短尾块。固定 PRINT `regionBias` 是矩阵，按行读取每个区域 bias，不能靠给不同宽度向量填 0 或 `fill=TRUE` 解决。V6 一次运行授权已消耗。

## 本地候选修复

保留完整原始 BED 区间、PRINT 模型、radii 10/20 和 native caller，不替换 summit windows、不填充区间、不改变每区间 bias/count 向量。新增 `print_variable_width.R`：

1. 用 chromosome 与精确区间宽度分组，使用全局 BED 行号保留重复坐标和原顺序。
2. 每次从 HDF5 读取一个染色体的 bias，按精确宽度构造行数×区间宽度矩阵并写入本次唯一 scratch 目录；拒绝不等长、非有限或错位 bias。
3. 对完整原始区域集只调用一次 `getCountTensor()`，每组按同一全局行号子集 countTensor；验证局部位置仍落在该原始区间内，保留空 count 元素。
4. 为每个组建独立 project/cache。固定 PRINT 的 `getFootprints.R` 内部引用 `.GlobalEnv` 的 `project`，代码在矩阵赋值和调用前绑定并断言当前组对象。
5. 按全局行号恢复 footprint 对象，随后用对应原始 BED 行写 score track 与 native events。track、bias、count 长度须与区间宽度相同；native event 直接按局部坐标转换，允许它越出 peak 但绝不静默裁剪。

最终代码审计发现并修正了分组对象赋值目标：bias 矩阵现在写入当前 `project_group`，随后立即重新绑定并断言 `.GlobalEnv$project` 指向更新后的对象；此前候选误写入基础 `project`，会丢失分组状态。监督器 runner SHA 已随修正同步。

监督器现在验证 `run_print.R` 和新 helper 的 SHA-256，并预留独立 V7 输出/日志路径。代码仍须 fixed-PMA exact-head 审查；V7 路径名不代表运行许可。

## 本地验证与限制

通过（在上述最后一处赋值修正之后重新运行）：

- `Rscript tests/test_print_variable_width.R`
- `Rscript -e 'parse("scripts/04b_footprint/run_print.R"); parse("scripts/04b_footprint/print_variable_width.R")'`
- `python3 -m py_compile scripts/04b_footprint/run_print_fullpeak_supervised.py`
- `bash tests/test_step4b_runner_contract.sh`
- `git diff --check`

合成用例覆盖组大小 1/99/100/101/128、混合宽度与交错染色体、重复输入坐标、精确 bias 矩阵行、countTensor 子集和空元素、无效位置拒绝、结果逆序恢复/重复与缺失行号拒绝、cache 路径隔离、`.GlobalEnv` active-project 绑定、BED track 坐标及越过 peak 边界的 native event 坐标映射。

该环境缺少 `hdf5r`，本地没有固定 PRINT checkout 和 Argos HDF5 文件；因此这些检查没有执行真实 HDF5 读取或 PRINT S4/并行端到端调用。固定 PMA 审核要求在代码级合并前验证 HDF5 分组和 project/cache 行为。不能将合成测试等同于生物学结果或全峰调用。

## 状态与门禁

PR #8 仍为 OPEN、未合并。实现提交 `e757e7c282a5b83f7456b3394f6b8f09988a1a17`、binding 修复提交 `4d6bc67` 与后续文档提交在原分支。固定 PMA 对 exact HEAD `d7b66d159c0136a201c02bc152cbbcf10f75d9c5` 的 L1/L2 代码审查发现 countTensor 全量来源被 active project 覆盖，返回 `REQUEST_CHANGES`；`4d6bc67` 已把完整 countTensor 与共享标签保存在独立绑定，并增加连续两组测试。固定 PMA 对 exact implementation HEAD `4d6bc671853ecca21a14ff81c8b82fdbeb8086f4` 复核：L1 finding 关闭、代码 `APPROVE`；L2 是 `BLOCKED / UNVERIFIED-critical`，因为未验证真实 HDF5 读取、PRINT S4 替换赋值、并行端到端及实际输出维度。该审核明确没有授权 Argos 访问、预检或 V7。V6 一次授权已消耗，V7 仍需新的单次人类授权和有效阶段门禁。

未访问 Argos、未读实验数据、未安装依赖、未运行 caller、未启动准确度或 motif 分析、未合并 PR。
