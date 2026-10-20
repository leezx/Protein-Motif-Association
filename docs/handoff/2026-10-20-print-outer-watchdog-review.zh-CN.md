# PRINT 8-peak smoke 外层监督器复审修复

时间：2026-10-20 10:19 EDT
范围：仅 PMA footprint PR #8；ChIP BED6 / PR #7 属于 Claude，不在本任务内。

## 当前状态

固定 PMA 项目对话审查了 PR #8 精确 HEAD `6ff52e0d78dec129f5b73e1fc73e0d2da80f7416`。独立 bias 对照问题已关闭；整体 deadline 问题仍为 `REQUEST_CHANGES`：原实现在执行线程内检查时间，不能打断阻塞文件读取；单独给子进程传 `timeout` 不能证明进程组完整清理；原测试只有普通 sleep，没有覆盖隔离子进程清理。此次仅在本地同一 PR 修复这些点，还没有新审核，也没有 Argos 预检或计算。

## 修复

- 外层父进程在启动 worker 前建立唯一 30 分钟单调时钟；父进程不读实验文件、不哈希、不做预检。全部原有数据访问和协作式 deadline 检查留在 worker。
- worker 将单独 session 的 preflight、PRINT caller、RSS sampler 通过本地 `/tmp` JSONL 注册到外层。内层仍保留原有 deadline 检查。
- 到期、SIGINT/SIGTERM 或 worker 退出后仍留有注册组时，外层对所有已知组和 worker 组并行发送 TERM，最多等 60 秒，再对残留组发 KILL，最多再观察 5 秒，并返回残留组 ID。Argos Linux 依据 /proc 组成员状态，将 zombie 视为已退出；本机 macOS fixture 使用 killpg 存在性检查。说明明确指出内核 D-state 进程可能不会被 SIGKILL 立即清除；不会宣称超时能绝对清除不可中断内核任务。
- 任务仍限定原始 8 个 peak、2 个 worker、radii 10/20、每进程 RLIMIT_AS ≤44 GiB、40 GiB 采样 RSS 软停止；没有扩大数据或分析范围。

## 本地验证

通过：`python3 tests/test_print_smoke_deadline.py`（正常完成路径；另含一个独立 session 中忽略 TERM 的子进程，验证外层 deadline 触发 KILL 并在有界时间内清理）、`python3 tests/test_select_print_integration_smoke.py`、`Rscript tests/test_print_variable_width.R`、R 源码 parse、Python `py_compile`、`bash tests/test_step4b_runner_contract.sh`、`git diff --check`。

该本机 macOS 测试验证进程组 API 和注册/超时流程；Argos Linux `/proc` 聚合 RSS、真实远端 launcher、HDF5 和 PRINT S4 并行调用仍未验证。没有新的 footprint track/event、运行耗时或实际内存数据。

## 候选文件 SHA-256

- selector：`7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856`
- runner：`44853e1a865bcdf86c87ca6fbabd0279d86d144b14953b1b0533c679eb5098f2`
- helper：`fa2aaba9248a9a67621fe269210b7afd81920aaa3bf85cac443f0a2371865174`
- base supervisor：`5631f74b7fcad6b50776a237325234063f54ceeac781dfd9e0fa68fc75f6968f`
- outer smoke supervisor：`d68e50789f1a70e021b8a7b330ba46d0a4ad414477b66998e6fa1ef0748a6324`

## 下一步

提交到 PR #8 同一分支，核实 GitHub exact HEAD 与本地一致，更新 PR 描述，然后在固定 `PMA｜固定阶段审核` 对话仅请求审查当前完整 HEAD。未获当前 exact-head APPROVE 前，不接触 Argos。获批也只允许之前范围内的一次 8-peak smoke；失败保留证据并停止，不自动重试、不开 full-scale V7、不合并。
