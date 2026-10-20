# PRINT 8 峰 smoke：登记竞态与预检退出码修复

时间：2026-10-20 10:26 EDT
范围：PMA footprint PR #8；ChIP BED6/PR #7 由 Claude 负责，不在本次范围。

## 审核结果

固定 PMA 对话对 PR #8 精确 HEAD `782a875900401fc201d29313643f4ee4b7203c4f` 复审为 `REQUEST_CHANGES`。它复现了两项 L1 缺陷：独立 session 子进程在登记 PGID 之前已经开始运行，登记文件写失败时会泄漏；`bounded_check_output()` 忽略子进程非零退出码，可能把失败预检当成成功。审核还指出其环境中的 deadline suite 在 `/proc` 清理断言处失败。真实 HDF5、PRINT S4、Argos Linux `/proc` 和并行端到端仍为 `BLOCKED / UNVERIFIED-critical`。该审核没有放行 smoke。

## 最小修复

- 增加 exec gate：新 session 的 launcher 先阻塞读取一字节，目标程序只有在注册表完成写入和 fsync 后才会 `execvp`。若外层 worker 在登记期间退出，管道 EOF 会阻止目标程序启动。
- 登记失败时关闭 gate，按现有有界 TERM→KILL 流程清理并回收进程，再将失败抛出。
- preflight、PRINT caller 与 RSS sampler 均通过该启动函数，统一消除 start→register 竞态。
- `bounded_check_output()` 检查返回码；非零状态抛出含原始 stdout/stderr 的 `CalledProcessError`。
- 更新 smoke supervisor 对 base supervisor 的固定 SHA。

## 本地验证

通过：

- `python3 tests/test_print_smoke_deadline.py`：覆盖注册写失败时目标不得执行、worker 在注册期间被杀时管道 EOF 阻止目标执行、退出码 7 必须报错并保留 stdout/stderr、正常 worker 完成、TERM-resistant 子进程的有界 KILL 清理。
- `python3 tests/test_select_print_integration_smoke.py`
- `Rscript tests/test_print_variable_width.R`
- R parse、Python `py_compile`
- `bash tests/test_step4b_runner_contract.sh`
- `git diff --check`

本机复跑 deadline suite 通过；测试按监督器合同检查进程组终止，不把 Linux zombie-only PID 误认作仍运行的任务。上述检查只证明本地合成流程与代码契约。它们不验证 Argos Linux `/proc`、真实 HDF5、PRINT S4、平行调用或生物学输出；没有执行 Argos 预检或计算，也没有产生 footprint track/event。

## 当前边界与下一步

候选 supervisor SHA-256：base `7d594c58de85c012cc3ff08d93c8c67252be65f9cd860497243bc9295ef0a234`；outer smoke supervisor `336c79277c1506447888dc6333db906b68d37cb5c893dbb1a559edb3fb785acc`。仍需更新 PR #8 同一 PR、推送后向固定 PMA 项目对话提交 exact-head 复审。未获明确 APPROVE 前不访问 Argos。通过后也仅可执行用户此前授权的单次 8 峰 smoke；失败即停止，不重试、不运行全峰 V7、不合并。
