# ChIP-Atlas unique BED6 builder implementation handoff

Updated: 2026-10-18 22:18 EDT  
Branch: `task_20261019_chipatlas_bed6_builder`  
Parent design PR: [#6](https://github.com/leezx/Protein-Motif-Association/pull/6), exact GPT-approved design HEAD `3c0e48e699073726b9ef7453644cabbe8b277ca4`, OPEN/unmerged.  
Implementation PR: being prepared on top of the approved PR #6 branch; verify live GitHub HEAD before review or execution.

## Direction and current progress

The user's two endpoints remain: (1) produce a coordinate-unique, experiment-traceable human hg38 ChIP-Atlas BED6 reference with QC; (2) compare PRINT, TraceBIND, HINT, and TOBIAS on matched motif-free footprint accuracy and genome-wide speed on Argos, then complete B1–B4 and motif integration. Neither endpoint is complete.

PR #6's current design-only approval does not include implementation or Argos operations. This branch contains a proposed streaming builder for endpoint 1 and an implementation-stage clarification to the approved design. It has not read external datasets, run a builder, or measured memory/disk/runtime. Local checks are syntax compilation (`py_compile`), shell parse (`bash -n`), and `git diff --check`; no functional tests were run.

## Builder contract in this branch

- CLI consumes the pinned hg38 peaks archive, experiment metadata snapshot, and chromosome sizes, and writes to a new external output directory. It rejects output/work paths inside a Git checkout.
- It assigns every source row one primary status, streams eligible rows to an external-sort spool, de-duplicates exact coordinates only, and retains every included source row in provenance.
- Core build uses two GNU external sorts. A separate release QC uses a third compact sort by full region ID to enumerate exact duplicate IDs/collisions; zero duplicates is required for `PASS`.
- It produces BED6, region–experiment links, source-row provenance, region summary, experiment metadata (including zero-peak eligible experiments), reconciliation counts, deterministic tabix query QC, collision QC, and SHA-256 manifest.
- The launcher fails closed unless `systemd-run --user` can place Python and child processes in a cgroup capped at 44 GiB with swap disabled. GNU sort defaults to 4 GiB and two workers. Disk peak remains unknown and must be assessed by an approved read-only Argos preflight before any build.

## Review and execution gates

The complete implementation PR and current HEAD require GPT review before Argos access. The review request must include the precise read-only preflight and builder commands for consideration; no command has been run. If the current PR HEAD is approved only for code review, obtain explicit GPT review of the proposed Argos scope before executing it. Do not merge PR #6 or the implementation PR without the user's separate approval.

## Next acceptance

Finish static review, update the PR body and this handoff with the final exact HEAD, request exact-head GPT review, and fix only review findings in the same PR. After approval, confirm available disk and the memory cgroup on Argos before the full build; never use Mac mini compute. Then verify full row reconciliation, coordinate and region-ID uniqueness, provenance/linkage cardinality, class-mask counts, tabix queries, and reproducible hashes. Keep all data and results outside the repository.
