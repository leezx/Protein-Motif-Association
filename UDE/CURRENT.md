# PMA 当前状态索引

本页由 [`CURRENT.yaml`](CURRENT.yaml) 的 **2026-10-26 15:59 EDT 快照**整理；机器可读状态只在 YAML 中维护。后续任务必须先核对 Git、PR、数据和审核记录，不得把本页当作实时运行监控。

**总体：AMBER。** 项目目标和分步设计有来源；执行证据分散在已集成基线、开放 PR、其他未合并分支以及原 checkout 的本地文件。U/D/X 版本均为 `unknown`，没有推定的统一批准版本。

| 层 | 当前可依赖的来源 | 边界 |
|---|---|---|
| [Understanding](understanding/CURRENT.md) | 章程与冻结 v0.2 项目问题 | 后续假说和科学结论须逐项核验 |
| [Design](design/CURRENT.md) | 冻结 v0.2、Step 4a/4b 合同等 | 新的坐标唯一 BED6 和 atlas 范围尚在其他分支 |
| [Execution](execution/CURRENT.md) | `origin/step4b-atac-footprinting` 的提交 `6c2e323` | PR #5–#8、后续分支和未跟踪结果没有自动并入此基线 |

**六门核对：** 项目身份 PASS；理解证据 PARTIAL；理解→设计 PARTIAL；设计→执行 PARTIAL；版本与审批 PARTIAL；朝章程交付物收敛 PARTIAL。当前没有足够证据评为 GREEN。

**最重要的差异：** Step 4a 基线合同是一条记录对应一个实验峰；PR #6–#7 引入坐标唯一 BED6 的另一设计/实现路径。对它们做接受、替换或并存决定之前，不能把两种产物叫成同一基线。README 的“当前 Step 1 pilot”描述已过时，现以本索引定位各工作流。

**下一步：** 审核本 UDE 索引；分别核验并决定 PR #6–#8 及后续分支的纳入方式；将获接受的结果及其真实验收证据再写入 U/D/X。任何 PR 合并仍需要用户针对该 PR 单独确认。
