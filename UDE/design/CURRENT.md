# Design：基线与未批准的提案

**版本：UNKNOWN。** `based_on_understanding`：冻结 v0.2（`design/PMA_pseudo_figures_v0.2.md`，来源提交 `d4a05dc`），人类接受记录仍为 `unknown`。本页采用已集成 `origin/step4b-atac-footprinting@6c2e323` 作为 Git 基线；它不是独立的人类设计接受记录。

## 1. 现行设计来源

| ID | 设计来源 | 权威与状态 |
|---|---|---|
| D-01 | [v0.2 项目范围](../../design/PMA_pseudo_figures_v0.2.md)、[章程](../../docs/PROJECT_CHARTER.md) | README 标为冻结范围；100% 定义仍以章程为准。章程 non-goals 明确排除 recruitment grammar、Fig. 3+ 与 perturbation。 |
| D-02 | [Step 1](../../docs/STEP1_MOTIF_PILOT_DESIGN.md)、[Step 2](../../docs/STEP2_MOTIF_IMPORT_DESIGN.md)、[Step 2c](../../docs/STEP2C_DENOVO_SOURCES_DESIGN.md)、[Step 3](../../docs/STEP3_MOTIF_CLUSTERING_DESIGN.md)、[Step 3b](../../docs/STEP3B_V03_INTEGRATION_DESIGN.md) | motif reference 分步合同；保留原路径，不因 UDE 索引改变引用。 |
| D-03 | [Step 4a](../../docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md) | 文件称经审核修订；基线产物为**逐实验峰** BED6+18，明确排除跨实验峰合并。 |
| D-04 | [Step 4b](../../docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md) | 文件称设计获批并修订；定义无 motif calling、B1–B4 和速度门槛；不等于已选定工具。 |
| D-05 | PR [#6](https://github.com/leezx/Protein-Motif-Association/pull/6)、[#7](https://github.com/leezx/Protein-Motif-Association/pull/7) | 坐标唯一 BED6 设计/实现链；2026-10-26 查为 OPEN，须与 D-03 的"不跨实验合并"显式协调。 |
| D-06 | PR [#8](https://github.com/leezx/Protein-Motif-Association/pull/8)及分支 `task_20261020_fpbench_v2`、`task_20261021_footprint_db_tracks` | 后续 footprint 方案和报告，不在本 Git 基线中；需核对最新提交、审批、输入与验收。 |

`README.md` 原有"Step 1 pilot 为当前工作"的描述滞后；它不是新版本设计依据。结果稿、图件和本地未跟踪文件不自动成为合同。

## 2. 外部设计来源：KB 对话档案（未批准）

- 文件：`/Volumes/Stelligen_SSD/Stelligen/Zhixins-KB/2026-GPT-Project-PMA.md`（仓库外）。
- 指纹：sha256 `ff50036f54f31dd94924c097764a56c87a8b8a49c5a0dba7087a3e342e934faa`，273,975 bytes，mtime `2026-10-21 19:22 EDT`。
- 分类：**GPT 对话档案**，内容是逐步演化的探索，不是单一时点的设计稿。按内容拆分为 Understanding 假说（见[理解层](../understanding/CURRENT.md)）与**未批准设计提案**（本页第 3 节）。
- 权威性：**无**。它没有仓库提交、没有人类 L3 接受记录、也没有对应 PR 审核。引用它时只能说"某提案建议"，不能说"设计要求"。
- 数字处理：文中 `29,778 motif profiles` 是早期计数，与仓库 v0.3 结果（101,228 unique / 24,194 core）不一致，标为历史值；`39,099 experiments` 与 Step 4a 合同一致，但仍以[结果文档](../../docs/CODEX_HANDOFF.md)为准。

## 3. 未批准提案清单

分级按 UDE：**L1** 信息/证据更新；**L2** 设计影响评审或有限变更；**L3** 目标、交付物或范围改变，须暂停受影响执行并重新批准。

| ID | 提案 | 来源锚点 | 分级 | 与现行基线的关系 | 状态 |
|---|---|---|---|---|---|
| P-01 | Region-centric regulatory evidence matrix：以 hg38 区域为行，ChIP/ATAC/motif/footprint 为注释列；不把"≥n ChIP + n ATAC + motif"当作所有潜在区域的准入条件 | §PMA Human Regulatory Region Reference (L2)；§saturation (L447) | **L3** | 改变主数据模型：D-01/章程的交付物是 protein–motif association matrix，不是区域注释表 | 未批准 |
| P-02 | Motif instance 饱和/可穷尽性：genomic / motif-model / biological 三层饱和，G(n) 覆盖曲线 | §saturation (L447)；§可以穷尽motif吗 (L1920) | **L2** | 可作为 reference 的表征指标；若变成项目主问题则升为 L3 | 未批准 |
| P-03 | Bias-aware post-hoc footprint validation：raw 多尺度检测 + 多模型 Tn5 bias annotation + 置信度，而非先校正再检测 | §PMA的footprint部分重大创新 (L4094) | **L2** | 改变 D-04 的检测/评估语义；需修订 Step 4b 合同与 benchmark，不自动选工具 | 未批准 |
| P-04 | 五项扩展筛选：信息饱和度、DBP hotspots、hotspot-guided footprint、Tn5 bias atlas、normal–cancer atlas | §PMA整体重大进展 (L4541) | **L3**（③④⑤） | 原文自己判定 ③④⑤ 为独立研究；纳入即扩大 D-01 范围 | 建议 park |
| P-05 | bigWig 数学定义（tf/proteins/cap/experiments）与 normalized occupancy `R_p(x)`、`S(x)` | §ChIP-Atlas 整合 (L4863) | **L2** | 定义 Figure 1/2 与 QC 不变量（如 `P(x) ≥ TF(x)`）；不改变项目目标 | 未批准 |
| P-06 | DBD–motif joint embedding；反向只做候选 DBD family 排序，不做结构生成 | §PMA-DBD-motif model (L5227)；§结构生物学 (L6211) | **L3** | 新的研究轨道，不在章程 100% 定义内 | 未批准 |
| P-07 | 不新建通用 de novo motif reference，复用 Factorbook/ENCODE 等，专注去重、癌症注释、provenance、motif→protein 证据 | §de novo DB (L6697)；§PMA denovo motifs (L6872) | **L1** | 与 D-02 现有方向一致；作为范围约束记录，不新增交付物 | 信息性约束 |
| P-08 | Genome Biology 架构：pan-cancer regulatory interactome、四应用、Fig. 1–5、BAF case study、DL 模块、G1–G5 go/no-go | §genome biology架构 (L6995) | **L3** | 直接冲突：章程 non-goals 排除 Fig. 3+、recruitment 机制；v0.2 只冻结两张主图 | 未批准 |
| P-09 | Application 1 benchmark：full raw vs representative-only vs representative + member-rescue scanning 的下游归因比较 | §genome biology架构 §6 (L7514) | **L2** | 为 D-02 的压缩假设增加验收 benchmark；可与 100% 定义中的 motif 质量要求兼容 | 未批准 |

## 4. 影响分析（只记录，不执行）

- **P-01 + P-08 + P-06 + P-04 是 L3。** 任何一项被采纳，都必须先更新 D-01（交付物与范围）、在章程 Part 1 记录偏离理由、暂停受影响执行，并取得用户明确的设计接受；GPT 工程审核不能代替该接受。
- **P-01 的核心未决问题是 region 定义**（原文亦称其为比 affiliation 算法更重要的设计决定）。在 region 定义、边界重叠规则和背景匹配未定之前，不能把 region-centric 表与 association matrix 当作同一产物。
- **P-03 与 D-04 的冲突是语义级的**：D-04 规定 benchmark 的输入/输出语义，P-03 改变"bias correction 在流程中的位置"。两者不能同时声称是同一合同；需先决定是修订 D-04 还是把 P-03 作为独立方法研究。
- **P-08 与章程 non-goals 冲突**。若用户希望走 pan-cancer/BAF 路线，最小合规路径是新建独立项目或在章程中显式修订 non-goals，而不是在 PMA 内静默扩图。
- **P-05 可作为 L2 的图件定义澄清**：它不改变交付物，但会改变 Figure 1/2 的指标语义与 QC；采纳时需同步 D-01 的图件说明与结果文档。
- **P-07 是唯一与现行方向一致的提案**：它支持"不扩建通用 de novo 库"，但其中的 29,778 计数不得写入设计。

## 5. 处理规则

1. 本页不批准任何 P-*；它们的状态固定为 `proposed_unapproved` / `informational_constraint` / `park`。
2. 变更请求写在所属层文件（本页或[执行层](../execution/CURRENT.md)），不新建第四个 UDE 目录。
3. 采纳 L2 需给出受影响 D/U ID、验收影响和迁移状态；采纳 L3 需用户决定 + 重新批准 Design。
4. 任何采纳都先改 `CURRENT.yaml`，再改本页与相关层页；Git 提交保存历史。
