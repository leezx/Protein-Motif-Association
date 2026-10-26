# Design：基线与待审变化

**版本：UNKNOWN。** 本索引采用已集成 `origin/step4b-atac-footprinting@6c2e323fc80cc3e05f9de05282d1bbce49ba98fa` 作为 Git 基线；它不是独立的人类设计接受记录。设计所依赖的项目理解是[冻结 v0.2](../../design/PMA_pseudo_figures_v0.2.md)（来源提交 `d4a05dc`）。

| ID | 设计来源 | 权威与状态 |
|---|---|---|
| D-01 | [v0.2 项目范围](../../design/PMA_pseudo_figures_v0.2.md)、[章程](../../docs/PROJECT_CHARTER.md) | README 标为冻结范围；100% 定义仍以章程为准。 |
| D-02 | [Step 1](../../docs/STEP1_MOTIF_PILOT_DESIGN.md)、[Step 2](../../docs/STEP2_MOTIF_IMPORT_DESIGN.md)、[Step 2c](../../docs/STEP2C_DENOVO_SOURCES_DESIGN.md)、[Step 3](../../docs/STEP3_MOTIF_CLUSTERING_DESIGN.md)、[Step 3b](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md) | motif reference 分步合同；不要搬到 UDE 后改变其引用路径。 |
| D-03 | [Step 4a](../../docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md) | 文件称经审核修订；基线产物为**逐实验峰** BED6+18，明确排除跨实验峰合并。 |
| D-04 | [Step 4b](../../docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md) | 文件称设计获批并修订；定义无 motif calling、B1–B4 和速度门槛；不等于已选定工具。 |
| D-05 | PR [#6](https://github.com/leezx/Protein-Motif-Association/pull/6)、[#7](https://github.com/leezx/Protein-Motif-Association/pull/7) | 坐标唯一 BED6 设计/实现链；2026-10-26 查为 OPEN，须与 D-03 的不合并要求显式协调。 |
| D-06 | PR [#8](https://github.com/leezx/Protein-Motif-Association/pull/8)及分支 `task_20261020_fpbench_v2`、`task_20261021_footprint_db_tracks` | 后续 footprint 方案和报告，不在本 Git 基线中；需核对最新提交、审批、输入与验收。 |

`README.md` 原有“Step 1 pilot 为当前工作”的描述滞后；它不是新版本设计依据。结果稿、图件和本地未跟踪文件不自动成为合同。
