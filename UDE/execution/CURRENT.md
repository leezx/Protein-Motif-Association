# Execution：集成状态、未合并工作与记录差异

**版本：UNKNOWN。** 设计基线：`origin/step4b-atac-footprinting@6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`。执行是否符合各设计，以原始运行记录、校验和与对应审核判定为准；本页不把"脚本存在"或"分支存在"当作运行成功。

## 1. 可核对状态

| ID | 2026-10-26 观察 | 证据 / 下一验收 |
|---|---|---|
| X-01 | 基线 `6c2e323` 是 PR #4 的合并提交；该分支包含 motif reference（Step 1–3b）、Step 4a 构建记录与 Step 4b setup/修复工作。 | [`Worklog.md`](../../Worklog.md)、[`docs/handoff/`](../../docs/handoff/)、[`CODEX_HANDOFF`](../../docs/CODEX_HANDOFF.md)。需按 Q-07 核对 Step 4a closure。 |
| X-02 | PR [#5](https://github.com/leezx/Protein-Motif-Association/pull/5) HEAD `c1f9329`、[#6](https://github.com/leezx/Protein-Motif-Association/pull/6) `3c0e48e`、[#7](https://github.com/leezx/Protein-Motif-Association/pull/7) `3b2c6dc`、[#8](https://github.com/leezx/Protein-Motif-Association/pull/8) `01fc1c6`，均为 OPEN。 | 分别读取当前 PR HEAD、审核与外部结果；不得从开着的 PR 推定已集成。 |
| X-03 | 分支 `task_20261019_bed6_independent_verify`、`task_20261020_chipatlas_light_bed`、`task_20261020_fpbench_v2`、`task_20261021_footprint_db_tracks`、`task_20261021_repo_data_links` 各自独立，未合并到基线。 | 按各分支 commit、设计、结果与审核核验后再决定整合。 |
| X-04 | 原 checkout `task_20261018_step4b_setup_fix@7eccace` 有已修改 `Worklog.md`，未跟踪 `Figures/`、`benchmark/`、`design/protein_binding_resources.md`。 | 本 UDE 分支未搬运、暂存或清理；所有者、来源、数据放置与 PR 归属待核（Q-06）。 |
| X-05 | PR [#9](https://github.com/leezx/Protein-Motif-Association/pull/9)：分支 `task_20261026_ude_index`，HEAD `4a656a9`，仅新增/修改 UDE、README、Worklog 与 handoff 文档。 | 待 PMA 固定审核会话给出结论；合并需用户单独确认。 |
| X-06 | 记录差异：Worklog tracker 仍写 Step 3/4/5 "not started"、总体 20%；CODEX_HANDOFF 写 33%；handoff 的"last live-verified HEAD"停留在 `ba26845`/`515cd76`，而合并后 tip 为 `7eccace`/`6c2e323`。README 的"Step 1 pilot"已在 PR #9 更新。 | 由 Q-08 决定进度口径；handoff 的 HEAD 差异按已合并 PR #4 理解，不据此重写历史。 |

## 2. 与设计的对应关系

| 设计 | 执行证据 | 结论 |
|---|---|---|
| D-01（v0.2 冻结范围） | 尚无 association matrix 或 Figure 1/2 的完整真实计算结果；Step 4a occupancy 与 motif reference 是输入层。 | 未完成；不得以输入层完成度替代交付物。 |
| D-02（motif reference） | Step 1–3b 结果文档与分支已合并；压缩 benchmark（P-09）未做。 | 报告级完成，验收口径待确认。 |
| D-03（Step 4a 逐实验峰） | 有构建记录与行数统计；closure check pending。 | 未 closure。 |
| D-04（Step 4b benchmark） | 外部运行在 smoke 前失败，无 benchmark 结果。 | 未产生可判定结果。 |
| D-05（坐标唯一 BED6） | PR #6–#7 开放，未合并；与 D-03 冲突未决。 | 不能与 D-03 同时称为当前基线。 |
| D-06（后续 footprint） | PR #8 与两个分支未合并。 | 仅作参考，不纳入执行基线。 |

## 3. 收敛规则

近期只按章程 100% 定义收敛：先解决 D-03 与 D-05 的交付口径（HD-01），再确认 Step 4a closure（Q-07），随后完成 Step 4b 评测并进入关联统计框架设计（Q-03）。KB 外部提案中的 pan-cancer/BAF/DBD/DL 与 region-centric 模型（P-01、P-04、P-06、P-08）不在关键路径上；在 HD-02 决定前不排期、不运行。

本页不批准任何新外部运行、数据变更或 PR 合并。
