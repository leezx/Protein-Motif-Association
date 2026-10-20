# PRINT 64 peak 速度候选运行包

时间：2026-10-20 11:22 EDT
项目：PMA Step 4b footprint；仅 PR #8。Claude 负责 ChIP BED6/PR #7，本次不涉及。

## 目的与范围

为 PRINT 的真实 ATAC-seq peak-level 调用补一个有界速度样本。该实验只测运行时间和资源，
不做准确度排名，不做 de novo motif，也不调用其余 footprint 工具。8 peak V3 证明过集成
路径能产出结果，但样本过小且固定读入开销显著，不能据此线性外推到全量 159,628 peaks。

## 冻结输入与选择

- K562 ATAC：`ENCSR868FGK`，BAM `ENCFF534DCE.bam`；对应片段文件沿用 V3 已核验输入。
- Peak BED：`ENCFF993BAP.bed.gz`，SHA-256：
  `c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945`。
- 共用 BAM→fragments 预处理已经完成：`BG_K562_FRAG_PREP_V1 EXIT=0`，110,891,807 fragments；
  BAM SHA-256 `1ed9d63b38d2430bc037493187fc3c0f73478d204dc55d6f1ed7c329f17105df`，fragment SHA-256
  `238367780a1b7a2a24595a4259bdbe91cb8be439c2e5fda210831ad60d77544f`。GNU time 实测 wall
  28:18.88，user 1,701.40 s、system 26.29 s、CPU 101%（约1.01平均核）、最大 RSS
  4,196,976 KiB（约4.00 GiB）；Argos gate `RLIMIT_KB=46137344`（44 GiB）。
- 完整 BED 预期 159,628 行；选择器按原始文件行序抽取 64 个中点分位行，不改坐标、不筛选，
  输出原始行 map 和 SHA-256。若行数、哈希或至少两条染色体条件不符，fail closed。
- 64 个 peak 用于一个 PRINT caller 样本，radii 10/20，生产 chromosome-wise bias 路径；不启用
  8 peak direct comparison。

## 拟议资源与记录

- Argos `rcapps3/rcGPUs`，CPU-only，2 workers。
- 30 分钟总预算；每进程 `RLIMIT_AS` 44 GiB；采样进程组 `VmRSS` 达 40 GiB 时软停止。
- `VmRSS` 求和可能重复计共享页，也可能漏掉短命或脱离进程组的成员；仅近似软停止信号，不是
  真实峰值、保守上界或硬内存限额。
- 分开记录 BED selection、监督器 preflight、caller wall/CPU、PRINT bias/count/r10/r20 阶段；
  保留 GNU time 和每条 R warning。
- 64 峰任务复用既有片段文件，30 分钟预算不含已经发生的 BAM→fragments 转换；若报告从
  BAM 起算的总时间，须另列并相加这次 28:18.88 预处理 wall。转换是一次共享成本，复用文件时不重复计费。
- immutable gate 元数据显式提供 `ctrl print`。

## 精确候选身份

- PR #8 review target：推送后再记录的 live exact HEAD；目前未获审批。
- Run ID：`BG_K562_PRINT_PEAK_SPEED64_20261020_V1`。
- Code stage：`/home/zz950/PMA_fetch/pma_print_peak_speed_code_20261020_v1`。
- Evidence root：`/home/zz950/PMA_fetch/pma_print_peak_speed_rcapps3_20261020_v1`。
- Scientific output：
  `/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_peak_speed_rcapps3_20261020_v1`。
- Wrapper SHA-256：`8b0579e9bcde9d8b72c3cd57f901c7da91cfce3f2ca5a898ca09e078d39bda70`。
- Selector SHA-256：`105be1be89c94d466e46dccdee98402d74ec7dfba1781f1c7a91740342932b46`。
- PRINT runner SHA-256：`0c7c26f303f079a18d5f1f110faa2e516d631c8826dbd5e5517fc26d4aff22bb`。
- Helper SHA-256：`5f5da1b9cf3179f40850792d26ecce6862ed8c3a5dfd82ad39fa8ab07d51d4ca`。
- Base supervisor SHA-256：`7d594c58de85c012cc3ff08d93c8c67252be65f9cd860497243bc9295ef0a234`。
- Immutable gate SHA-256：`3776778b950be90cad124c04937eee422c81466154eccdadfe9e57d58224253c`。

建议 gate command：

```sh
PMA_PRINT_SPEED64_EXPECTED_SHA256=8b0579e9bcde9d8b72c3cd57f901c7da91cfce3f2ca5a898ca09e078d39bda70 \
  bash /home/zz950/PMA_fetch/pma_bg_gate_v2.sh \
  BG_K562_PRINT_PEAK_SPEED64_20261020_V1 \
  /home/zz950/PMA_fetch/pma_print_peak_speed_code_20261020_v1/run_print_speed64_supervised.py \
  ctrl print
```

## 验证与门禁

本地已完成 Python 编译检查、R 语法 parse、`git diff --check`。Argos 上未读取数据、未上传脚本、
未修改环境、未运行调用。候选必须先提交到同一 PR #8，在固定 PMA 对话审查推送后的 exact HEAD，
并获得本命令范围的一次性明确 APPROVE。任何失败保留日志并停止，不自动重试；未授权 merge。

此候选只会给出 64 peak runtime/resource 观测；其数据不能替代全量 caller，也不能用线性外推
宣称完整 159,628 peak runtime。完整调用是否可行，应在该次结果之后另做阶段决策。
