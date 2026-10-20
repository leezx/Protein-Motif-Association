# 最新阶段：PRINT 全部原始 ATAC peaks 的两尺度运行（2026-10-19 22:43 EDT）

用户把 ChIP BED6 交给 Claude；本 handoff 只推进 Step 4b footprint。用户已把即时目标收敛为：选择一个 ATAC 样本，在其同样本完整 peak BED 区间上运行 PRINT 的 motif-independent footprint calling，记录计算时间/资源与输出统计。不是逐碱基扫描全 hg38；不评准确度、不找 motif、不优化/移植代码、不运行其他 caller、不合并 PR。

## 目前已核实

- 样本：K562 `ENCSR868FGK`，ATAC BAM `ENCFF534DCE.bam`；用户只要求本次计算时间/资源，K562 的 ENCODE nucleosome-free-fraction 警告意味着不得把本次结果写成准确度证据。
- 同样本官方 peak 输入：`ENCFF993BAP.bed.gz`，Argos path `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-19/encode_k562/ENCSR868FGK/ENCFF993BAP.bed.gz`。固定 PMA 对话明确批准有限只读核验：压缩字节数、SHA-256、流式记录数；并另批准只输出区间长度总和和重叠合并后覆盖量，不输出坐标、不写解压文件。
- 核验结果：159,628 条原始 peak；压缩文件 3,651,342 bytes；SHA-256 `c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945`；原始区间长度总和 150,359,120 bp；合并重叠后的唯一覆盖 55,114,693 bp。用户估计的 20–40 万不是输入门槛；不得为凑数量换文件或扩展 peaks。
- 全部原始区间都应保留；不可替换为先前 77,668 个 1-kb 窗口，也不对原始区间去重/裁切。由于区间重叠，摘要必须区分 interval-width sum 和 union coverage。
- PRINT 输入 bias HDF5 存在，12,838,026,244 bytes。dispersion model 有 99 个半径文件，2–100 bp。固定 PMA 对话明确：不可据文件存在就跑 99 个，也不可结果后选尺度；本次采用当前 wrapper 已有的 `10,20` 两尺度参数，必须如实标成“两尺度”，不是完整 99 尺度。
- 本地 `scripts/04b_footprint/run_print.R` SHA-256 `cae788b22dfb8ffc6006bae168b356909b3082036faa4a73e853c496ce717abf`。wrapper 接收 peak BED、fragment table、核数、radius list；每尺度生成逐位点 `track.tsv.gz` 与 PRINT 原生 event BED，另有阶段 `timing.tsv`，不直接生成 BigWig。Argos 只读元数据检查看到 `/usr/bin/Rscript` 与外部 `cladoRcpp` overlay `/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib`。文件/路径存在不代表依赖已加载或调用成功；不运行 R/caller 作验证。
- 固定 PMA 对话确认 PRINT 原始 footprint calculation 不需要 motif/ChIP；“全局”在本任务中特指同一样本完整可及 peak 区间。

## 资源阻塞与下一门槛

用户授权在 Argos 用 QSUB 申请 16 核、80–100 GB；不使用 standalone gate。但最新只读检查显示：`normal.q` avail 0/32；`normal.q@rcGPUs` 为 E/QERROR（jobs 85/86）；`qconf -spl` 没有任何 PE。此前 queue config 查询还显示 `h_vmem`/`h_rss` 无界，h_vmem non-consumable，没有任务级内存预留/硬限制证据。节点总内存不能代替作业资源分配。**当前无可验证且可运行的 16核 + 80–100GB QSUB 命令；未提交作业，未运行 PRINT。**

需 Argos 管理员先恢复队列、提供单节点 PE 与 slot 语义，并提供覆盖主进程和全部 R workers 的 job-total 内存预约和强制上限。然后在同一 PR 写入确切 qsub 参数、16-worker 命令、wall limit、日志/输出路径和 preflight，固定 PMA 对话 exact-head APPROVE 后，才能提交唯一的 PRINT 任务。用户的执行授权不绕过该资源门槛/PR 审核。

PR #8 分支 `task_20261019_hint_overlay_smoke`，核对前 live HEAD `60a56d3974d92dd2301756d26acc4e10736b454e`，base `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`，OPEN、未合并。此处更新后待同步的新 HEAD/审查状态以 GitHub 为准。此前的四工具 / 77,668 窗口计划均为历史材料，不是当前运行范围。

## 2026-10-19 22:43 EDT — 证据来源与审查范围

固定 `PMA｜固定阶段审核` 对话依次批准：PRINT 在所有原始峰区间的任务定义；ENCFF993BAP 的 hash/bytes/records 只读核验；仅聚合区间宽度总和与 overlap-merged coverage 的只读核验；`10,20` 两尺度边界（非 99 尺度全跑）。上述审查均未放行 caller 或 QSUB 提交。队列/QSUB 查询仍是只读。

论文与官方实现：Hu et al., *Nature* 2025, [PRINT multiscale footprint paper](https://www.nature.com/articles/s41586-024-08443-4); [official PRINT repository](https://github.com/buenrostrolab/PRINT)。论文描述 footprint windows 覆盖 4–200 bp，原始 PRINT footprint 分析以 ATAC cut sites 和偏差校正为输入；seq2PRINT 是下游解释。本任务仅执行原始 footprint caller。

# 历史阶段：单样本全局可及窗口运行时间（2026-10-19 22:22 EDT）

用户已把 ChIP BED6 交给 Claude；本轮只做 footprint 计算时间/资源测量，不评准确度，不做 motif，不涉及 ChIP/PR #7 或合并。用户明确放行此 runtime-only 阶段，PR #8 exact-head GPT 审核仍是 Argos 运行前门禁。

## 固定执行方案
- 输入：已校验 K562 ENCODE `ENCSR868FGK` / `ENCFF534DCE.bam`，同样本冻结 `k562_speed_1kb.bed`，77,668 个非重叠 1-kb 窗口，合计 77.668 Mb。这里的“全局”指全部冻结ATAC可及窗口，不是逐碱基扫描hg38。K562仅用于时间测量，ENCODE NFR QC警告排除其作为准确度真值。
- 工具：HINT 16 chunks；PRINT 16 R workers；TOBIAS 16 cores；TraceBIND **PRINT-bias reduced mode** 16 R workers（无mtDNA fine-tuning/mito-FDR）。每工具一次、顺序执行，每个工具内部并行，总活动CPU上限16，避免同时运行高内存caller。
- 限制：每任务最多24 h、不可变 `pma_bg_gate_v2.sh` 44-GiB `RLIMIT_AS`，CPU-only/no-GPU；不安装、不调参、不重试、不改算法。既有依赖缺失则记录为blocked，不补装。
- 计时：wall、GNU-time user/system CPU、max RSS（注明统计范围）、工具版本/准确模式/核数、门禁、输出事件/track计数和SHA-256、退出/失败阶段。PRINT/TraceBIND使用同一BAM导出的既有片段表，转换wall 28:18.88单列并计入这两者from-BAM总耗时。片段表110,891,807行与独立过滤计数110,891,952不一致，保留两个口径，不用该差值归一化吞吐。
- 命令形态：HINT `run_hint.sh <hint-bin> <bam> <bed> <outdir> 16`；PRINT `Rscript run_print.R <print-repo> <print-shared> <bed> <fragments> <out-prefix> 16 10,20`；TOBIAS `run_tobias.sh <pmafp-bin> <bam> <bed> <hg38.fa> <blacklist> <outdir> 16`；TraceBIND `Rscript run_tracebind.R <pmafp-python> <model-dir> <bed> <fragments> <out-prefix> 16 0.05`。每条都经不可变Argos gate，使用独立任务、日志、结果目录；精确gate入口和依赖预检随当前PR exact-head 请求审核。
- 结论：只报时间/资源和原生输出数量，不由事件总数推准确度。四个工具全成功才称完整四工具时间比较，否则逐项报告耗时/失败原因，不替换、不重跑。

## 当前状态
本轮未启动Argos任务。PR #8 HEAD `7d0c015733f0c2f23b3bcdb53a51f6ea01a841dd` 的运行方案和准确命令审核待固定PMA对话明确APPROVE；此前不同核数的HINT/TOBIAS及失败PRINT不纳入本轮16核对比。

---

# Step 4b footprint：十轮内形成可行工具选择

> **当前操作方案（2026-10-19 22:05 EDT）**：用户要求停止扩展方案，只做一次可信、有限资源的
> 准确度与耗时评估。下方“十轮封顶计划”和更早的多方案文字均为历史记录，已由
> `docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md` 开头的“Current operative plan”取代；不要按历史表格
> 继续增加数据集、折叠方案、事件级替代、优化或额外轮次。
>
> 唯一候选为 HCT116 CTCF-degron 未处理 ATAC 与同克隆/同条件 CTCF ChIP+input。先只读核实 provenance、
> 独立生物重复、匹配对照、QC 及与工具开发数据的独立性；任一不合格，准确度结论为“不能排名”，不换
> 数据集。共同单位为预先冻结 CTCF motif 中心 20 bp；唯一主指标为四工具共同完整阈值前分数的 AP。
> 不调用缺失分数填零，不用阈值事件替代。HINT/TraceBIND 若仍无完整连续分数，则四工具准确度比较
> 即停止。若评估获准，四工具在同一 input/region list 各顺序运行一次，默认参数、最多 8 CPU、24 h、
> 不可变 44-GiB `RLIMIT_AS`；TraceBIND 必须标明当前 wrapper 的 **PRINT-bias reduced mode**（没有
> mtDNA fine-tuning / mito-FDR），不能称为完整 TraceBIND 默认流程或完整模式耗时。记录墙钟、user/system CPU、进程树峰值 RSS、共享/专属预处理、片段量、
> 评分位点数和退出状态。仅四项成功才作速度排名，否则只报观察值。是否允许在准确度资格失败后
> 仍做 speed-only 运行，固定 PMA 审核已原则同意，但要求先提供四条具体命令及 gate/计时包装，并确认依赖
> 已存在，再由用户作阶段放行。22:05 EDT 只读核验后，准确度已确定为“不能排名”；四方计时目前也未获放行。
> 当前 checked R4.2.2 library 中缺少 TraceBIND，且本阶段不安装、不修改环境，因此不能启动四方计时。

## 2026-10-19 22:10 EDT — existing HCT116 ctrl pilot timing summarized

固定 PMA 项目对话批准 exact HEAD `e44334e3b13e00ea53a67871b69f13f224172dfa` 后，只读了
HCT116 ctrl 2,000-window 四份 timing 表及对应任务 status/meta/GNU-time 摘要。没有启动 caller、
分析或新计时任务，没有安装软件或改动数据/环境；PR #7/ChIP BED6 仍由 Claude 负责。

Argos 外部目录 `processed/round1/runs_full_pr8_22667dc/ctrl/` 中的观察值：

| 工具/模式（任务） | wall | user+system CPU | GNU-time max RSS | 任务记录 |
|---|---:|---:|---:|---:|
| HINT (`BG_FULL_hint_ctrl`) | 2:02.64 | 81.82 s | 224,548 KB | EXIT=0 |
| PRINT r10+r20 (`BG_PRINT_FULL_ctrl_V1`) | 17:46.01 | 231.41 s | 37,524,900 KB | EXIT=0 |
| TOBIAS ATACorrect+FootprintScores (`BG_FULL_TOBIAS_ctrl_V2`) | 15:16.06 | 867.82 s | 411,100 KB | GNU-time exit=0 + completion marker |
| TraceBIND PRINT-bias reduced mode (`BG_TRACE_FULL_ctrl_V11`) | 2:28:53 | 33,396.85 s | 14,415,888 KB | EXIT=0 |

各 timing 表阶段秒数：HINT 123；PRINT bias/counts/r10/r20 为 64.117/178.002/423.285/386.422；
TOBIAS ATACorrect/FootprintScores/events 为 622/290/4；TraceBIND bias/counts/footprint 为
528.265/175.346/8,210.065。四项映射到相同 HCT116 ctrl 与 2,000 区域 BED；HINT/TOBIAS 读
BAM，PRINT/TraceBIND 读同一样本派生的 fragments。PRINT 的片段整理、TraceBIND 的片段与
序列预计算不在 caller 计时内；TraceBIND 用 4 个 R workers，其他 wrapper 执行形态不同。因此
这是同一小型 pilot 的实测资源描述，不能据此排速度名次或称端到端总时间。GNU-time RSS 只按
原记录报告，不声称是进程树聚合峰值。TraceBIND 这一项不是完整 mtDNA fine-tuned/mito-FDR
模式。

准确度仍是 **不能排名**：HCT116 CTCF ChIP 每条件只有一个生物学重复，且 HINT/TraceBIND
缺完整阈值前连续分数。当前结果不能给出准确度赢家、全基因组速度结论或 Cancer ATAC 运行授权。
只读提取时，SSH 输出包含这四个任务各自的 wrapper stdout 完成/进度行，用于对应退出、输出计数和结束时间；没有打开 BAM、fragment、peak、BigWig、score matrix 或其他生物数据文件，也没有打开其他任务的 status 内容。

固定 PMA 对 exact evidence-record HEAD `ee64e13f060b6fe25c81f6c1c1012689864307b5` 给出文档/事实记录 `APPROVE`，无阻塞 finding。唯一非阻塞建议是 PR body 不应把 TOBIAS 的 GNU-time exit/completion marker 概称为 parent task status；已按建议改为区分 HINT/PRINT/TraceBIND task EXIT=0 与 TOBIAS GNU-time exit=0 + completion marker。审核明确没有放行新的 caller、计时、Cancer ATAC 全局运行、安装、优化或合并。

更新时间：2026-10-19 16:46 EDT（UTC 20:46）
范围：仅 footprint→de novo motif；ChIP BED6 / PR #7 由 Claude 负责，本交接不涉及。  
PR #8：`task_20261019_hint_overlay_smoke`，OPEN、未合并。固定 PMA 对话 `PMA｜固定阶段审核` 对父 HEAD `03dbdd9a5bc8f54e1ef09056e3f4cc755e71ae2a` 批准第 3 轮公开研究元数据盘点；提交后的 HEAD `bfa06d4e86bbe77d4d4ebc84190f408fb6a216d9` 收到 `REQUEST_CHANGES`；三项 finding 已在同一 PR 修正并推送至内容提交 `6f9c04621dae462bb316366c0c0b41f79c4e12bd`；完整状态同步 HEAD `d15db7f4d292f6484f003c45035f7eb5449635e7` 获文档/方法和只读审计 `APPROVE`。之后按已批准的元数据范围核对 K562 候选，内容提交 `2eeb09deaf172885d31059124de03931415c5587` 已推送；状态同步 tip `08c334ddc3c436ea17ef7906ab277958dbcbeea0` 经复核，阶段关闭 HEAD `632eb4993f13d069e4d0bde4c984b747eab693e5` 获 round-3 文档/方法记录 `APPROVE`；随后按审核意见把两项非阻塞 attribution 修正同步到当前 tip `7746d8bf22324ed66426322f04efa1845cee154d`，无需另开复审。审查确认候选总结忠实，但提醒同一 biosample ID、旧平台或 audit 数量单独不能证明重复不独立或数据不可用。批准范围不包含实验数据文件、Argos、caller、分析、环境修改、ChIP 数据处理或合并。审核指出本手册上一时间行将 UTC/EDT 写反；此处已更正。未下载或读取 BAM、FASTQ、BED、BigWig、矩阵等实验数据文件。

## 2026-10-19 22:05 EDT — 一次性评估只读资格结论

固定 PMA 对话对 exact PR #8 HEAD `324d4e04a6652ff4f77a894b61fd7fcb52bd16cd` 的 APPROVE
只覆盖：核对现有 HCT116 输入完整性/标签来源、输出分数接口、实际运行模式、已安装依赖并将结果记录入同一 PR；不含数据下载/修改、环境安装、caller、计时任务或 PR merge。

- HCT116 四个官方 unfiltered ATAC BAM 的 `BG_HCT116_UNFILTERED_VERIFY_V3` 为 EXIT=0；byte count、ENCODE MD5、SHA-256、`samtools quickcheck`、chrM header 均通过。清单为 `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-19/encode_hct116_unfiltered/ENCSR328JGW_ENCSR260SWI/MD5SUMS.encode.tsv`。这不证明 ChIP 标签。
- 选定的 HCT116 CTCF-degron ENCODE ChIP 每条件只有一个 biological replicate（另有两个 technical replicates）；已核对的四个精确 ChIP accession 在范围内的 PMA 候选目录未找到文件。现有 metadata 已不满足冻结 label gate，因此 occupancy AP 不能计算。
- PRINT r10 与 TOBIAS bigWig 是候选连续轨；HINT wrapper 只输出阈值事件；TraceBIND wrapper 以 p=0.05 截断事件，且明确是 PRINT-bias reduced mode（无 mtDNA fine-tuning / mito-FDR）。四方 AP 不成立，结论为 **准确度不能排名**。
- 已见环境：TOBIAS 0.17.5 可用；HINT overlay 指向该 Python 环境且 `rgt` module 可见，独立 `pma_hint` launcher shebang 已失效；PRINT R4.2.2 与 `cladoRcpp` overlay 存在，但旧 K562 worker 忘记该 overlay 而失败；已检查 R4.2.2 library 未找到 `tracebind`，依赖探针 30 秒超时后停止。未安装软件、改环境或运行 caller。
- 已有 HCT116 HINT ctrl 10:03.94（32 chunks）、aux 10:10.11（32 chunks）；HCT116 两次不是拟定的最多 8 CPU 控制。K562 TOBIAS 1:02:16（16 cores）；PRINT 36:19.75 后因 `cladoRcpp` worker namespace 失败；无完整可比 TraceBIND 时间。因此只能作历史描述，不排快慢。

准确度目前可直接收敛为“不能排名”。四工具 time-only 虽获固定 PMA 原则同意，但 exact-head 尚未审核具体命令/gate wrappers，且 checked R library 中缺少 TraceBIND；当前禁止安装的范围下不满足“现有依赖可用”。没有启动或排队任何 caller/timing 任务。提交固定 PMA 对话审核是否可以只读提取已存在的 HCT116 ctrl 2,000 区域计时/状态记录，作为同一场景的资源观测（不称四工具速度排名、不读取生物输入、不启动新任务）；否则停止在“准确度不能排名、现有耗时不可比”。若要求新的完整四方 timing，必须另行解决 TraceBIND 依赖并审核具体命令，不能把当前历史时间拼成速度排名。
固定 PMA 对完整 HEAD `774a3498d7cc17904afe3dc4610711586fe56d82` 再次给出 `APPROVE`：四个 wrapper 的当前接口描述与 canonical §4 一致；缺失/不可评分/运行失败不能混为零；标签、共同分数和折外证据仍缺。无阻塞 finding。仅有一项非阻塞措辞修正：将“二值 BED”改为“阈值后事件 BED”；即使事件列保留 p/score，也不能恢复完整阈值前排序空间。该修正与本次审核记录一并纳入后续文档同步，无需另起重复审查轮次。
审核明确的科学结论：目前不能确定哪个工具准确度最高。occupancy/扰动标签测的是指定场景的预测一致性，不是碱基级 footprint 边界真值；裸 gDNA 也不是通用真阴性。没有合格标签、四工具共同可评分集和验证过的折外分数，因此没有四工具 AP 排名。审核建议在同 PR 记录此结论，并只用仓库现有源码/文档完成接口与验收规格只读核对。后续复审前从 GitHub 读取完整 live tip，handoff 不自引用其自身 SHA。
审核边界：此前 `fd0b041` 的 APPROVE 仅覆盖方法文档；`525f0d4` 收到的时间、状态来源、折外边界和事件级备选 findings 已在同 PR 修复，并获当前 `0829b08` 方案级批准。15:41 EDT Argos 队列读取来自当时用户明确要求的 15 分钟监控 heartbeat；只读取调度与已有状态文件，没有读取实验数据，也没有核查 detached processes。该监控授权不扩大为 caller 执行授权。

## 现在能确定什么

### 第 3 轮：公开元数据准入盘点（已关闭；2026-10-19）

| 候选体系 | 公开元数据观察 | 当前准入结论 |
|---|---|---|
| HCT116 CTCF degron，ENCODE `ENCSR059BCO` 未处理 / `ENCSR160GVO` 6 h 1 μM 5-Ph-IAA；分别匹配 `ENCSR229ZIR` / `ENCSR862XXV` control ChIP | 每条件各 1 个 biological replicate、2 个 technical replicates；GRCh38 文件 assembly 有记录。配套 ATAC `ENCSR328JGW` / `ENCSR260SWI` 各有 2 个 biological replicates。ENCODE 对两个 ChIP experiment 标记 `unreplicated experiment`；不能把技术重复计为独立重复。 | **与当前 §4 资格不符**：未达到至少 3 对独立 biological replicates；peak/QC、抗体/audit 详情、spike-in 和逐样本对应仍未核实。不可据此生成标签。 |
| HCT116 CTCF degron，GEO `GSE179540` | GEO 样本标题为 untreated CTCF `GSM5420199/201`、Auxin+ CTCF `GSM5420200/202`；对应条件各列 input 样本 `GSM5420215/217` 与 `GSM5420216/218`。样本方法记录为 **500 μM 3-indole acetic acid、6 h、hg19**；ENCODE 用 **1 μM 5-Phenyl-1H-indole-3-acetic acid、6 h**，是不同试剂标注和浓度，不能当成同一处理。样本级生物独立性与固定 spike-in 未确认。 | **候选，但当前不合格**：每条件 2 个 replicate 编号不足现行 §4 门槛，且编号不证明独立培养来源；处理体系不同、不能直接配对；hg19 需经审核的坐标方案。此处不推断文件 QC 或 ChIP 标签质量。 |
| K562 CTCF ChIP，ENCODE `ENCSR000DMA` / input control `ENCSR000DMB` | ENCODE 官方 experiment 页列 3 个 isogenic replicate，每个 technical replicate=1，三行均链接 biosample `ENCBS775AAA`；同页显示 `Audit not_compliant 2 / warning 1`、ENCODE2、Illumina Genome Analyzer，外部引用为 GEO `GSM822311` 与 `UCSC-ENCODE-hg19`。其 input control `ENCSR000DMB` 页面明确为 input library、unreplicated、单个 replicate，`Audit not_compliant 1 / warning 1`，平台同为 Illumina Genome Analyzer。公开页面没有证明三个 ChIP replicate 是独立培养物，也不是 3 对独立 ChIP/input。 | **仅为另一个静态 occupancy 候选，当前不能作为已合格 benchmark**：旧 ENCODE2 记录的审计标记和单次 input 使独立标签可靠性未建立；也不等于 HCT116 degron 验证。不能无新冻结设计/审核替换当前方案。 |
| HCT116-RAD-mAC CTCF ChIP，4DN experiment `4DNEXFB8OQ21` / replicate set `4DNES5X392R6` | 官方 set 标题为 HCT116-RAD-mAC、CTCF、auxin-0h；公开页显示 Bio Rep 1 / Tec Rep 1、PBC 0.74、NRF 0.75、filtered/deduped reads 58.33m。尚未确认 matched control、auxin 配对系列、spike-in、assembly 与这些 QC 指标是否满足本项目门槛。 | **待核实且背景不匹配**：虽有一个生物重复和可见 QC，不是已确认的 canonical CTCF degron biosample；不能当成已验证 HCT116 degron 标签。 |

**第 3 轮结论（阶段关闭）：在本次已列候选中，尚未建立符合现行 HCT116 canonical §4 的标签集。**因此当前不能计算独立占据一致性 AP，也不能选出最准确工具。此结论不代表公开数据中不存在其他合格 occupancy benchmark；不同细胞系/静态 occupancy 需先冻结为另一个方案。公开候选不等于实验数据已核实，更不等于标签已建立。round-3 元数据阶段没有访问/下载实验数据文件或访问 Argos。其后按用户单独授权做了 16:44 EDT 只读 Argos 状态监控；边界与结果记录见下方，不代表任何 benchmark 数据/计算获准。

来源：ENCODE experiment records [`ENCSR059BCO`](https://www.encodeproject.org/experiments/ENCSR059BCO/?format=json)、[`ENCSR160GVO`](https://www.encodeproject.org/experiments/ENCSR160GVO/?format=json)、[`ENCSR229ZIR`](https://www.encodeproject.org/experiments/ENCSR229ZIR/?format=json)、[`ENCSR862XXV`](https://www.encodeproject.org/experiments/ENCSR862XXV/?format=json)、[`ENCSR328JGW`](https://www.encodeproject.org/experiments/ENCSR328JGW/?format=json)、[`ENCSR260SWI`](https://www.encodeproject.org/experiments/ENCSR260SWI/?format=json)、[`ENCSR000DMA`](https://www.encodeproject.org/experiments/ENCSR000DMA/)、[`ENCSR000DMB`](https://www.encodeproject.org/experiments/ENCSR000DMB/)；GEO series [`GSE179540`](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE179540) 和样本 `GSM5420199`–`GSM5420202`、`GSM5420215`–`GSM5420218`；4DN experiment `4DNEXFB8OQ21` / replicate set [`4DNES5X392R6`](https://data.4dnucleome.org/experiment-set-replicates/4DNES5X392R6/)。上述仅为公开页面/API 中的元数据和所示 QC 摘要；没有下载任何关联 data file。

**阶段关闭决定**：round 3 公开元数据盘点到此结束。结论仅针对本次已列候选和 HCT116 canonical §4，不声称不存在其他公开 occupancy benchmark。下一阶段需要先决定是否冻结一个不同的静态 occupancy 设计并取得新的阶段授权；当前不运行 Argos、不下载/读取实验数据、不生成标签或 caller 输出。

2026-10-19 16:44 EDT 只读 Argos 监控：固定 PMA 审核对话澄清，用户最新 heartbeat 单独授权本次查看 `qstat` 和既有运行状态日志；仍不授权启动/停止/修改任务、读取生物数据或运行 caller/analysis。`qstat -u zz950` 无排队作业；按 footprint caller/gate 名称筛选的进程查询未找到活跃 footprint 进程。状态文件显示 K562 TOBIAS 速度任务 EXIT=0、PRINT 速度任务 EXIT=1，HINT K562 速度和 HCT116 ctrl/aux HINT motif 探索 EXIT=0，ctrl PRINT/TOBIAS/TraceBIND motif 探索 EXIT=0。任务状态不等同于可比速度或准确度；没有 eligible 独立标签或统一有效四工具分数，准确度仍不能排名。未读取生物数据，也未启动、停止或修改任务。PR #8 HEAD `168e011b8e9cad2d76fa549123190ef21c59e452`，OPEN、未合并。

2026-10-19 15:41 EDT Argos 只读核查：按当时用户的 15 分钟监控指示运行 `qstat -u zz950`，未列出该账户的调度作业。没有检查 detached/background processes，因此不能据此声称 Argos 上“没有任务”。只读取已有任务状态文件，未读取实验数据。状态文件在 `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`。

- HCT116 unfiltered BAM verify V3：EXIT=0；四个 ENCODE BAM 的字节数、MD5、SHA-256、`samtools quickcheck` 和 chrM header 均通过。这只证明输入完整，不产生 ChIP 真值标签。
- K562 TOBIAS 速度任务：EXIT=0；固定 77,668 个 1-kb 窗口，3,319,912 个事件，墙钟 1:02:16，最大 RSS 1,267,312 KB。该 K562 输入有 NFR QC 警告，当前只作工程速度观测。
- K562 PRINT 速度任务：EXIT=1；39/39 chunk 后 R worker 缺少 `cladoRcpp`，墙钟 36:19.75、最大 RSS 34,130,552 KB。失败运行不构成有效速度或准确度结果。
- K562 fragment prep：EXIT=0，110,891,807 fragments。GNU `time -v` 子进程 elapsed 为 28:18.88；job start/end 时间戳相减为 28:24，两值来自不同计时口径，首选进程 elapsed。独立 K562 过滤基准为 110,891,952 proper pairs，存在 145 条差异，分母口径需先对齐；预处理时间计入 PRINT/TraceBIND end-to-end 时间。
- HCT116 HINT→STREME 探索：ctrl 90,387 对、aux 88,444 对，分别 10 个 motif，任务 EXIT=0。背景为同窗口 GC 匹配、`selected_only` 排除。仅是探索性 motif 输出；不能算 B4 的重复性/家族恢复证据，也不是准确度标签、独立真值或已验证 motif 库。
- HINT 全窗口 caller 任务此前报告 77,668 K562 窗口上 16:53.47、781,863 events；边界 QC 有 3,125 个跨窗口事件，聚合进程峰值内存未直接测得。运行通过不等于边界发布 QC 通过。
- 原始 smoke 为四工具各在 control、aux、naked gDNA 的相同 2,000 区域调用/描述统计；这些结果不能按事件数或 caller 原生阈值排准确度。

## 十轮封顶计划

每轮只交付该轮表格所列的一项验收物。不得因为某项失败静默更换终点、标签、搜索空间或工具模式。缺数据/实现时记录阻塞及最小解除条件；最多一次针对性工程修复，之后将该工具标为不合格/不可评分。所有重计算只在 Argos，CPU-only、每作业 44 GiB `RLIMIT_AS`、无 GPU；数据和结果留在仓库外。

| 轮 | 交付物 | 冻结验收 / 停止条件 |
|---|---|---|
| 1（本轮，已核对） | 四工具运行状态与可信性清单 | 仅 EXIT=0 且输出完整者算有效；PRINT 失败不算成绩，HCT116 BAM 校验不算标签，STREME motif 数不算准确度。输出已记录在本文。 |
| 2（人类已选终点） | 目标与唯一主终点冻结 | 用户选择“与独立 ChIP/CUT&RUN occupancy 标签的一致性”，而非碱基级 footprint 边界准确度。主终点是共同、独立标注位点上的 held-out AP；HCT116 CTCF degron最多支持该局部保留/耗竭场景，不得声称通用真值或 pan-cancer 排名。标签不合格即允许结论为“当前不能排名”。 |
| 3（已关闭：当前不能排名） | 候选准入表 | 本次候选尚未满足或证明满足现行 HCT116 §4：ENCODE ChIP biological replicate 不足；GEO 的试剂/剂量、assembly、重复独立性需进一步核实且样本数低于冻结门槛；4DN 是 HCT116-RAD-mAC、仅见一个生物重复，尚未证实为目标 degron 配对；K562 可作为另一个静态 occupancy 设计的候选，但不得无审核替换 HCT116 主方案。该结论不表示所有公开数据均不合格；当前 HCT116 主标签资格 BLOCKED，不产生标签或排名。 |
| 4 | 每工具 adapter/模式资格表 | 冻结四工具版本、模式、资源哈希、连续分数字段、方向/单位、阈值前覆盖和 missingness。当前 PRINT/TOBIAS只是候选连续轨；HINT/TraceBIND当前 wrappers 为阈值事件，缺失事件不能填 0。无法阈值前打分的工具退出 AP 主比较，不能虚构四方 AP。TraceBIND 的 reduced PRINT-bias 与完整 mtDNA-calibrated 模式分开记账。把一次最相关作者基准的小规模模式核对/复现并入本轮；失败最多做一次针对性修复，然后如实标记不可复现。 |
| 5 | 公共输入和折外执行清单 | 同一 BAM/核内 fragment 过滤谓词、固定候选窗口/callable mask、hg38 资源哈希；按设计冻结 1-Mb block folds，并逐工具核实最大 score-context radius。允许 frozen caller 将 held-out reads/sequence 作为预测输入；禁止以 held-out 标签或其分数分布拟合、适配、选参、定阈值或选择工具。需要 sample-specific adaptation 的 caller 必须仅用训练折拟合，并隔离其所需上下文与 embargo；不能隔离则不参加严格 OOF AP。 |
| 6 | 主准确度结果或事件级备选／不可评分报告 | 若合格连续分数和标签存在，报共同位点 pooled OOF AP、覆盖、有效 n、paired block bootstrap 和六对校正。若任何工具无连续分数，则不造 AP；若所有比较者都能生成合法调用，使用预先冻结的事件级备选：一对一事件匹配、共同匹配窗口及定位误差；阈值只在训练折校准到预设标签召回，测试折报告实际召回和 naked-DNA false-event density，并补固定 event/bp budget 下召回。单阈值工具不能达到共同召回时只报原生工作点和 Pareto 关系，不声称匹配灵敏度。缺标签/共同终点/合法调用时，交付“不可排名”与具体缺项，不补造数据。 |
| 7 | B1–B2 方向/特异性报告 | B1 用训练折阈值在 naked DNA 报 false-event density，不称传统 FPR；B2 使用冻结 paired control→aux 标签。固定同一 callable 分母、事件 NMS、深度匹配、missingness；这两项不能单独判定主 AP 赢家。 |
| 8 | B3/B4 独立性报告 | B3 必须用工具开发集之外的正交 occupancy 真值；B4 报重复性和 motif-family recovery。作者自有数据或 motif 富集只能标为支持性/重分析，不能冒充独立准确度。若没有独立数据，明确“泛化未验证”。 |
| 9 | 公平速度/端到端癌症试用，若有合格候选 | 统一线程、资源、输入和过滤；包含 fragment prep 的端到端 wall、core-hours、峰值聚合 RSS、输出完整性。只对最多两个有资格的候选做冻结癌症 ATAC 全可及区域 footprint→STREME/TOMTOM 试用；motif 数不回流作准确度。若没有合格候选，不启动新试用，改交不可排名/证据缺口。若精度赢家慢，先 profiler 定位热点，后续另立 C/C++ 优化；本十轮不重写。 |
| 10 | 最终工具决策备忘录；若适用则交付 de novo motif | 若同一场景有可靠领先证据且 B1–B3 不冲突，选择该场景工具；准确度不可区分时可按可用性/端到端速度选部署工具，但必须写“准确度未证优”；若准确度/特异性/速度冲突，保留最多两个 Pareto 候选；资格不满足则以“当前数据不能排名”封板，写清缺少什么以及工程基线的局限，不强求新 footprint/motif 结果。只有此前资格和人类阶段门禁均通过，才交付工具的 footprint、背景匹配、de novo motif 与稳定性/QC。第十轮后不再扩展 benchmark。 |

## 对 `525f0d4` 审核反馈的修正（已推送并获方案审核）

固定 PMA 项目对话对 `525f0d4` 返回 `REQUEST_CHANGES`。同 PR 修订及 handoff-sync 已推送：不再把空 `qstat` 解释为无后台任务；把 15:41 队列读取归因于用户的 15 分钟监控指示，并与实验数据访问分开；将 GNU `time` 子进程 28:18.88 与 job 时间戳 28:24 标明为不同口径；允许 held-out 输入用于冻结 caller 的预测，同时禁止用 held-out 标签/分数分布进行拟合、适配或选择；补充连续分数不可用时的事件级备选，并允许第十轮以不可排名结束。HCT116 HINT→STREME 输出改列为探索性 motif 结果，不作为 B4 验证。复审前从 GitHub 确认完整 live branch tip，并在固定 PMA 对话审核该 SHA。

固定 PMA 对话对精确 HEAD `0829b08` 审核为 `APPROVE`。审核确认：空 qstat 仅表示无队列作业；状态查询授权与实验数据访问已分开；时间/HEAD/计时口径已说明；允许冻结 caller 预测时使用 held-out 输入，禁止利用 held-out 标签/分数拟合或选择；事件级替代与“不能排名”停止条件已写明；HINT-STREME 仅属探索。仍未建立真值、共同连续分数或折外 score。此 APPROVE 只放行基于仓库现有材料整理准入/adapter/fold-exclusion 清单和同 PR 审计记录，不放行 Argos、实验数据、分析、环境改动或 caller 运行。

## 评分接口只读核对（2026-10-19 16:02 EDT）

本次按固定 PMA 审核建议只检查 PR #8 中已有 caller wrapper 和 canonical benchmark design；没有访问 Argos、实验数据或结果，没有运行 caller，也没有改实现。

| 工具 | 源码可见的当前输出 | 对中立排序的意义 / 最小缺口 |
|---|---|---|
| PRINT | `run_print.R` 将 `aggregateScores` 写入逐位置 `.r<radius>.track.tsv.gz`，另写原生事件 BED；设计指定 r10 候选轨。 | 有候选连续分数接口，但需要锁定软件/偏差与 dispersion 资源哈希、确认方向/坐标与全 callable 覆盖，并实现合格标签上的折外评分；现有速度任务失败不构成准确度成绩。 |
| TOBIAS | `run_tobias.sh` 产生 `footprints.bw`，然后 `events_from_track.py` 再阈值化成事件 BED。 | BigWig 是候选连续轨；AP 应读原 track 并把缺失/非有限值记不可评分。阈值后事件 BED只保留过阈值的事件，不能恢复完整分数空间或把缺失分数填 0。还须核实共同过滤分母、mask、方向、参数/资源哈希与折外运行。 |
| HINT | `run_hint.sh` 汇总并排序 RGT 的 `fp.bed` 到 `events.bed`。 | 当前接口为阈值事件；没有阈值前逐候选连续分数接口，不能进入连续 AP。保留原生区间和工作点做事件级/描述性比较；边界 QC 与聚合 RSS 仍是调用产物发布前缺项。 |
| TraceBIND | `run_tracebind.R` 运行 NB footprinting 后调用 `binding_sites_pval(..., pval_threshold=...)`，只写过阈值事件及其调整 p 值。 | 已截断事件不能提供完整排序；本 wrapper 明确是 PRINT-bias reduced mode，不代表完整 mtDNA-calibrated TraceBIND。保持该原生工作点；除非来源接口证明完整阈值前分数/阈值空间，否则不报 AP 或匹配召回。 |

统一候选 adapter 的验收：固定列/坐标和 score 方向；逐候选行输出 finite、unscorable、missing、run_failed 状态及原因；对四工具共同可评分集计算折外 AP，另报覆盖率、正负例数和同步 genomic-block 配对不确定性。PRINT/TOBIAS 的连续轨不能自动让 HINT/TraceBIND 可评分；不得把“无事件”编码为 score=0。若独立标签或任何必要接口缺失，第 10 轮结论应为当前不可排名；如需部署工程基线，单独按完成率/端到端时间选择并标注准确度未证优。

## 仓库证据资格清单（只读审计，2026-10-19）

下表只根据 PR 分支源码、设计文档及既有 handoff 记录判断；本轮没有重新访问 Argos/实验数据。`eligible` 表示可以进入相应准确度比较的前置资格，不表示结果已生成。

| 项目 | 仓库证据 | 当前判定 | 解除条件 / 允许的结论 |
|---|---|---|---|
| 独立 occupancy/扰动标签 | 设计 §4 要求同一 HCT116 CTCF 体系的匹配 ChIP、输入、独立生物学重复和可解释校准。CODEX_HANDOFF 既有记录称候选 ChIP 文件/manifest 尚未在此前搜索的 PMA raw/processed 路径验证，已有的是 ATAC BAM 与校验清单。 | BLOCKED；不得把 ATAC 校验或 HINT footprint 当 ChIP 真值。 | 先有可追溯、独立重复、匹配对照和 QC 的标签资产；否则第 3 轮记录无合格标签并停止准确度排名，或另选经阶段审核的标签体系。 |
| PRINT score | `scripts/04b_footprint/run_print.R` 写 `.r<radius>.track.tsv.gz`，列 `score = aggregateScores`，并另写原生事件；设计固定 r10 作为候选连续轨。 | CANDIDATE；当前速度尝试 EXIT=1，不能作为成绩。资源哈希、正式输出完整性和折外计算均未通过。 | 先完成有效运行、固定代码/参数/资源摘要与完整 callable coverage，再判断能否提供严格 OOF continuous score。 |
| TOBIAS score | `scripts/04b_footprint/run_tobias.sh` 输出 `footprints.bw` 连续 track，再调用 `events_from_track.py` 生成 BED。 | CANDIDATE；工程速度 EXIT=0，但既有 handoff 报告与其他工具的过滤数不一致且 K562 有 NFR 警告；无准确度资格。 | 对齐片段谓词/分母和 BW mask；确认分数方向、完整性、参数/资源哈希及 fold-excluded 生成。 |
| HINT output | `scripts/04b_footprint/run_hint.sh` 只运行 RGT caller 并汇总 `events.bed`。 | 当前仅阈值化事件；不进入 AP。已知 K562 全窗口任务有 3,125 个跨边界事件，32 路聚合 RSS 未测。 | 如需连续 AP，须添加和冻结文档化 threshold-free adapter；否则仅按第 6 轮事件级方案比较，先修事件边界/聚合内存审计。 |
| TraceBIND output/mode | `scripts/04b_footprint/run_tracebind.R` 对每区段跑 NB footprinting 后以 `p_threshold` 输出事件 BED；注释明确本 wrapper 是 PRINT-bias mode，无 mtDNA fine-tuning、无 mito FDR。 | 当前 threshold-truncated，输出不能当连续轨；full TraceBIND 不等同本 wrapper。 | AP 前须提供阈值前全分数且冻结 full/reduced mode；若仅有事件，走合法事件级比较；完整模式须记录 mtDNA 校准资格。 |
| 缺失值/公共 score 集 | 设计 §4.3 指明 absent event 不是 0；`events_from_track.py` 的事件输出不适合作 AP adapter。 | BLOCKED；PRINT/TOBIAS 是候选连续轨，HINT/TraceBIND 目前没有共同连续输出。 | 每工具显式区分 finite score、missing/unscorable、run failure；锁定共同 candidate mask 和共同可评分集合。四方 AP 仅在共同完整覆盖成立时可报。 |
| 折外隔离 | 当前 caller wrappers 接受整份 BAM/regions 或全量 fragments；本审计在 `scripts/04b_footprint/` 未发现已实现的 1-Mb folds、embargo、OOF score manifest 或适配训练折隔离。 | BLOCKED；当前没有验证过的 fold-excluded scores。 | 先落地并经静态/小型合成核对的 fold manifest、context-radius 说明、训练/测试读段隔离与 embargo 审计。不能证明则不报严格 held-out AP。 |
| B1 负控与事件比较 | `scripts/04b_footprint/eval_round1.py` 只按 native thresholds 统计相同窗口的 event rows / callable Mb；脚本声明不做准确度排名。 | 仅描述性；不同阈值未匹配灵敏度。 | 在合格训练标签上冻结目标召回与参数，测试报告 recall、naked-DNA false-event density；一对一匹配、共同定位窗口及固定事件/bp预算按第 6 轮执行。 |
| 癌症全局 caller 与 de novo motif | 当前 HCT116 HINT-STREME 是已记录的探索结果，不等于独立 B4；Cancer ATAC 全区域结果尚未在本 PR 证据中形成经 QC 的统一产物。 | 暂缓选择/生产发布。 | 只对符合准确度/特异性门槛或明确标注工程基线的最多两个候选启动后续阶段；第 10 轮允许不可排名，不用 motif 数反推准确度。 |

**本轮可测进展：**把“缺什么才可能排准确度”从概念写成逐工具准入表。当前可行结论仍是：尚不能可信地宣布四工具中谁最准；现有证据支持 HINT 是已测工程基线、TOBIAS 有一次有效速度记录、PRINT 有一次失败记录、TraceBIND wrapper 是 reduced mode。要在十轮内给出答案，必须在第 3–6 轮拿到合格标签/可用事件终点；若未拿到，第 10 轮明确报告“当前数据不能排名”，不追加无期限工具工程。

## 本轮 Review (Quick)

固定 PMA 项目对话已对 PR #8 exact HEAD `0829b0886777637a88fb3925ce9d1f511b1a00dd` 给出文档/方法 `APPROVE`，且批准范围明确不含执行。L1：PASS（GitHub PR 与三份文件核对）；L2：BLOCKED（无合格共同真值、连续分数和验证的折外结果）；独立性 LIMITED。方向 ON TRACK：十轮内先判断能否可信排名。进展 PARTIAL：首次把现有脚本状态变成逐工具资格表，仍没有准确度结果。可信性 usable with limits。观察到：TOBIAS 有一次可用工程速度，PRINT 失败，HINT 有事件边界/内存缺项，TraceBIND wrapper 是 reduced mode。支持：现有证据不能定准确度赢家。未确立：四工具 AP、可靠排名或泛癌赢家。GPT 只批准了基于仓库材料的准入/adapter/fold-exclusion 清单；人类阶段接受及任何计算授权仍未获得。**HUMAN DECISION: PENDING**。

## 下一项唯一高价值动作

准入/adapter/fold-exclusion 清单已按批准范围写入本交接。下一步仅补齐可实现的评分接口与验收协议并在固定 PMA 对话审核新 HEAD；此审核不自动许可 Argos 计算。执行阶段仍需独立的具体范围批准和人类阶段接受。

## 准确度排名接口与冻结验收协议（第 2 轮文档交付）

本节把“中立排名”定义成可以成功、失败或不可排名的检验，不按工具原生阈值、输出数量或 motif 数排位。

### A. 连续分数主分析（仅标签和适配器准入后）

每个工具/模式的 score adapter 输出逐候选位点长表，至少包含：`tool_id`、`mode_id`、软件/容器与参数/参考资源哈希、`sample_id`、`condition`、`fold_id`、`chrom`、0-based 半开 `start/end`、`score`、`score_status`、`missing_reason`、固定分数方向/单位、源文件/track 和已核实的最大上下文半径。合法 `score_status` 至少区分 `finite`、`unscorable`、`missing`、`run_failed`；非有限值、未输出事件和失败运行绝不填成 0。分数方向须由该固定版本的已记录统计定义/源码确认；若无法确认则该分数不可评分。主分析不根据训练标签翻转方向；若另做训练标签定向，只能单列为监督校准敏感性分析，不并入主 AP 排名。

- PRINT：候选原始连续值为当前 r10 track 中 `aggregateScores`（设计定义为越高越强的 `−log10(p)`）；先核实其坐标覆盖、方向、资源哈希及可重复性。
- TOBIAS：候选原始连续值为 ATACorrect 后的 `footprints.bw` (`footprint` score)，不是 `events_from_track.py` 生成的阈值后事件 BED。BigWig 未定义/NaN 必须标成不可评分，不能转零；事件 BED保留分数列也不等于保留了完整的阈值前排序空间。
- HINT：当前 wrapper 只输出阈值事件 BED；除非找到/实现并冻结阈值前连续统计量，否则不进入 AP。
- TraceBIND：当前 wrapper 为 `PRINT-bias` reduced mode，按 `p_threshold` 截断输出；不能把已截断 BED score 当完整连续轨。full mtDNA-calibrated mode 是另一个 `mode_id`，须单独验收。

主分析按已存在的 `docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md` §4 冻结：HCT116 的 control-ChIP CTCF summits 是候选位点，在每个 summit ±50 bp 取处理后 ATAC footprint 连续分数的最大值；标签仅限经过该设计规定的匹配 ChIP/重复/校准 QC 后的 `retained` 对 `depleted`，不把 ATAC 自身或无 ChIP 峰当真值。这衡量的是对独立 occupancy/扰动标签的预测一致性，不是 footprint 碱基边界的真值准确度。四方 AP 仅在共同候选位点上四方均有合法分数时计算；否则可报告明确标名的 pairwise/subset AP，但不能称四工具排名。报告每工具 pooled OOF AP、共同覆盖率、有效正负例数、六个两两比较及 1-Mb block 配对 bootstrap。每折 held-out 原始分数按相应训练折的经验百分位转换后再合并，避免各折分数尺度不可比；分数方向、单位和映射区间均预先冻结。一个工具只有对其余三家的 Bonferroni 同时校正 99.1667% AP 差异区间下界全大于 0，才达到局部领先判据。若最终只有 HCT116 CTCF retained/depleted 标签，结论只适用于该扰动/TF 场景，不外推为普适 footprint 真值或泛癌赢家。裸 gDNA 仅用于特异性/背景密度，不作为蛋白占据真值的通用负类。

### B. 连续分数不可得时的事件级备选

事件比较只在有独立实验标签且各工具事件定义/坐标合法时启用。冻结同一 callable mask、候选窗口、核内片段谓词与深度匹配规则。连续分数工具可使用 canonical §4 冻结的单一 event adapter（21-bp 标准事件、局部峰代表点、21-bp NMS）作 B1 的统一假事件密度；这不是原生 footprint 边界评估。对阈值截断的 HINT/TraceBIND BED，保留工具原生区间宽度和原生工作点；有工具明示 peak/summit 时用该坐标，否则固定用区间中点作为代表坐标。一对一匹配半径、定位误差和未匹配位点数须在揭盲前固定，不能把原生区间重写成 21-bp 后声称测到边界准确度。

只有工具能合法生成完整可排序事件集合（连续分数，或经源码/接口验证的预设阈值网格覆盖全部候选）时，才允许在训练折选达到 80% training retained-site recall 的最高 cutoff，并原样用于测试折；每训练折至少 20 个 retained/depleted 标签，否则阈值不可估。已有阈值截断 BED 中的 p-value/score 只描述已通过阈值的事件，不能筛选掉事件来恢复完整排序，也不能保证达到共同召回或固定 event/bp budget。若 HINT/TraceBIND 无法导出完整排序或验证阈值网格，就仅报原生工作点与 Pareto 关系；matched-recall 和固定预算比较标记不可用。另报 naked-DNA false-event density（每 callable Mb 和每百万可用 fragment ends；不是 conventional FPR）。无事件、不可评分、运行失败、窗口不可调用分别计数。没有独立标签、共同 callable 候选集或合法一对一匹配时，事件级方案也停止为“不可排名”。

### C. 折外隔离和数据准入合同

按 canonical design 固定分折：`int(SHA256("PMA-4b-20261019|" + chromosome + ":" + block_start)[0:8], 16) % 5`；`block_start` 是冻结 hg38 `chrom.sizes` 顺序下 1-Mb block 的 0-based 起点。按哈希把不同 1-Mb blocks 独立分配；同一调控位点、配对条件/标签和重复记录不得跨折，但不因相邻区块而合并或重新分折。跨折依赖仅按 canonical embargo 规则处理。每个 caller 的 `C_j`（最大影响 score 的序列/读段/平滑上下文）必须从源码/实现证据确定。测试区块边缘按 `E_j=max(50 kb, 50 bp+C_j)` 排除可能跨边界泄漏的训练/适配证据，并排除完整依赖区间与 embargo 相交的评分候选；四工具使用同一最终保留候选位点集。记录 fold manifest/hash、embargo 参数、候选数和每折输入/输出摘要。Held-out reads 可作为冻结 caller 的预测输入；不得用 held-out reads 做样本特异性偏差拟合/归一化或从 score 分布挑参数。

冻结 caller 可把 held-out BAM/序列作为预测输入；held-out 标签、标签派生筛选、score 分布、阈值和工具选择不得参与拟合/适配/调参。需要样本特异性训练的校准资源必须逐折只由训练折生成，并证明未触及 embargo 区；不能做到者不进入严格 OOF AP/事件主排名。标签准入表必须记录 accession、细胞/处理、独立生物重复、matched input、spike-in 类型与加样时点、参考基因组、开发集是否重用及 QC；缺任何决定性来源项即 fail closed，不能把无 ChIP 峰区域直接当真阴性。

### D. 排名冻结与停止规则

1. 在揭盲测试折前冻结主要标签、位点宇宙、分数/模式、匹配半径、目标召回、bootstrap 单位与多重比较方案，并保存 manifest/hash。
2. 工具资格按完整输入输出链判定；失败运行不是低分，缺失轨不是零分。最多允许一次针对性修复一个可复现工程故障，之后标记该模式不可评分。
3. 只有一个工具在独立 held-out 主终点上稳健胜过全部对手、B1 特异性不劣且 B2/B3 不矛盾，才可称“本数据/场景中准确度最佳”；否则报告并列/场景性 Pareto 候选，或“当前数据不能排名”。
4. 十轮结束后停止扩建 benchmark。若缺标签或同一可评分集合仍未建立，第 10 轮交付不可排名结论和精确缺口，不因任务期限放宽真值标准。

**本轮可测推进：**已将连续分数、事件级备选、缺失值、折外泄漏和终止判据定义成表结构/计算合同。它尚未产生标签、连续 score adapters、折外预测或准确度数值；当前仍没有工具赢家。PMA 审核指出三项需消歧（哈希分折 vs 邻块、训练定向分数、截断 BED 的事件阈值能力），已在同 PR 作最小修订，等待复核；之后仍需人类接受方法阶段和具体执行授权。

## 2026-10-19 22:30 EDT — Argos 任务级资源限制核验；按要求 fail-closed

固定 PMA 对话 `PMA｜固定阶段审核` 先后批准只读检查不可变 gate、既有 K562 runner/meta、既有工具路径，以及当前 CPU/cgroup 限制；明确不批准任何 caller、计时、进程启动/停止、作业提交、安装或环境修改。核验只读取配置、脚本、路径元数据及 cgroup 字段，没有读取 BAM、BED、片段、FASTA、blacklist、score 或 footprint 文件。

- 不可变 gate `/home/zz950/PMA_fetch/pma_bg_gate_v2.sh` SHA-256：`3776778b950be90cad124c04937eee422c81466154eccdadfe9e57d58224253c`。源码设置 `NSLOTS=1`、单线程 BLAS/OpenMP 环境、清空 `CUDA_VISIBLE_DEVICES`，并对每个进程设置 `ulimit -Sv/-Hv 46137344` KB。它不限制任务进程树总 RSS，也不限制总 CPU。
- `/proc/self/status` 为 `Cpus_allowed_list=0-71`。当前为 cgroup v1：CPU quota `-1` / period `100000`（不限核）；SSH service memory limit `9223372036854771712` bytes（近似无限制），当前使用 `48031723520` bytes，历史 max usage `398863462400` bytes。账号对当前 cpu、memory、cpuset 控制文件均无写权限；`/run/user/68067/bus` 不存在。`taskset`、`timeout`、`systemd-run` 可执行文件存在，但没有证据证明可创建受限任务 cgroup；未执行这些工具。
- 现有四 wrapper（代码 commit `44b9c1153692effb528b888129136ef2a920201f`）SHA-256：HINT `ab652df81d3ccf7e10e6ee4ea6def5a938ec646fc2cfaae6d7f2f7066d848663`；PRINT `cae788b22dfb8ffc6006bae168b356909b3082036faa4a73e853c496ce717abf`；TOBIAS `e94789f3e542e371df038f9be1542f64d7c431a16960e0491dd732e15c8fa9ef`；TraceBIND `b77ae55c0bc32018757e697062110f07ec96586bf70921041e65045cbe19c22d`。路径/依赖只做存在性检查，未运行程序或 import 探针。已知 PRINT `cladoRcpp` overlay 与 TraceBIND R 包路径存在；bounded PMA_fetch 搜索未找到 TraceBIND 模型文件，但这不证明其他根目录不存在。

**决定：不启动任务。** 用户要求单任务内存不超过 50 GB，而现有 44-GiB `RLIMIT_AS` 是逐进程的；cgroup 当前无限制且账号无法写入。`taskset` 只能限制 CPU affinity，不能封顶总内存；抽样 RSS watchdog 也不能作为严格硬上限。因此不能声称满足内存合同，必须等 Argos 管理侧提供任务级 memory cgroup / 等价硬隔离及可验证启动接口。该能力确认后，再将具体 16 核、24 h、逐工具命令写进本 PR 并作 exact-head 复审。此前计划中的 16 核 K562 测速仍是方案，不是运行结果；HINT 32-chunk 与 TOBIAS 16-core 旧时长是不同调用条件下的历史观察，不能拼成排名。准确度未评估，未做 motif discovery，未运行任何新任务，未处理 ChIP/PR #7。


固定 PMA 对话随后对 PR #8 exact HEAD `e3f4035822f91b21a7c8a65ab2910989df1529f1` 作出 **APPROVE**，范围仅限上述文档／事实记录及 fail-closed 决定；reviewer 明确没有独立访问 Argos 原始证据，也未授权计算、PR #7 或合并。PR 当前保持 OPEN、未合并。该批准不解除任务级内存硬限制缺失这一阻塞。
