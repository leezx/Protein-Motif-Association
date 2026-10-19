# ChIP-Atlas unique BED6 builder implementation handoff

Updated: 2026-10-18 22:38 EDT
Branch: `task_20261019_chipatlas_bed6_builder`  
Parent design PR: [#6](https://github.com/leezx/Protein-Motif-Association/pull/6), exact GPT-approved design HEAD `3c0e48e699073726b9ef7453644cabbe8b277ca4`, OPEN/unmerged.  
Implementation PR: [#7](https://github.com/leezx/Protein-Motif-Association/pull/7), OPEN/unmerged, stacked on PR #6. Verify the complete live HEAD on GitHub before review or execution; this handoff is a timestamped snapshot.

## Direction and current progress

GPT reviewed PR #7 full HEAD `e54f7ab79def02a01673b52e4f8a1adabe7c81d6` (base `3c0e48e699073726b9ef7453644cabbe8b277ca4`) and returned `REQUEST_CHANGES`. F1, F2, N1 and N2 passed; two blockers remained: metadata release was inferred from a local directory instead of explicitly identified, and `zip(bed, summary)` could consume an extra BED row while the output audit lacked an independent BED ID/bounds check. GPT also recommended that the collision checker require the BED SHA-256 declaration. Focused repairs were committed/pushed on the same branch as `7e16526111f9491fe56a4e3152e3f21a6b769e2c`: required `--metadata-release`, `zip_longest` row-count reconciliation, per-row BED ID/bounds validation, and strict manifest BED hash requirement. Static checks passed. The new full HEAD still awaits GPT review; no external input was read and no Argos operation occurred.

The user's two endpoints remain: (1) produce a coordinate-unique, experiment-traceable human hg38 ChIP-Atlas BED6 reference with QC; (2) compare PRINT, TraceBIND, HINT, and TOBIAS on matched motif-free footprint accuracy and genome-wide speed on Argos, then complete B1–B4 and motif integration. Neither endpoint is complete.

PR #6's current design-only approval does not include implementation or Argos operations. This branch contains a proposed streaming builder for endpoint 1 and an implementation-stage clarification to the approved design. It has not read external datasets, run a builder, or measured memory/disk/runtime. The latest static checks are Python compilation via `python3 -m py_compile`, shell parse (`bash -n`), and `git diff --check`; no functional tests were run.

## Builder contract in this branch

- CLI consumes the pinned hg38 peaks archive, experiment metadata snapshot, and chromosome sizes, and writes to a new external output directory. It rejects output/work paths inside a Git checkout.
- It assigns every source row one primary status, streams eligible rows to an external-sort spool, de-duplicates exact coordinates only, and retains every included source row in provenance.
- Core build uses two GNU external sorts. The builder records collision QC as `NOT_RUN`; separate `verify_unique_bed6_region_ids.py` performs a third compact sort by full region ID once per formal release. Zero duplicate IDs and zero coordinate/hash mismatches are required for `PASS`.
- The builder produces BED6, region–experiment links, source-row provenance, region summary, experiment metadata (including zero-peak eligible experiments), reconciliation counts, deterministic tabix query QC, collision-QC `NOT_RUN`, and a SHA-256 manifest. The separate collision checker validates chromosome order/bounds, coordinates, full ID hashes, and exact ID uniqueness, then updates the release QC/manifest.
- The builder and release-QC launchers fail closed unless `systemd-run --user` can place Python and child processes in a cgroup capped at 44 GiB with swap disabled. GNU sort defaults to 4 GiB and two workers. Disk peak remains unknown and must be assessed by an approved read-only Argos preflight before any build.
- Both Python entrypoints independently verify the live cgroup-v2 `memory.max` (finite, <=44 GiB), `memory.swap.max=0`, and readable memory peak; direct invocation outside this enforced limit fails before data reading. GNU sort uses `LC_ALL=C`.
- The builder requires explicit `--metadata-release` (the pinned source is 2026-10-14; never infer this from `raw/2026-10-17/`). After writing, it fully rereads BED6, region summaries, region-experiment links, and peak provenance, verifies cross-file cardinalities/order/IDs/source hashes and chromosome bounds, and consumes gzip streams to validate CRCs before marking output integrity `PASS`.
- Tabix QC uses byte-for-byte comparisons for 48 seeded random windows and includes a guaranteed positive control derived from an emitted region.

## Review and execution gates

The complete implementation PR and current resulting HEAD require GPT review before Argos access. The second focused repair is pushed on PR #7. Synchronize the PR body to the final complete review HEAD and request GPT review of that exact HEAD. The review request must include the precise read-only preflight and builder commands for consideration; no command has been run. If the PR HEAD is approved only for code review, obtain explicit GPT review of the proposed Argos scope before executing it. Do not merge PR #6 or the implementation PR without the user's separate approval.

## Next acceptance

Finish static review, update the PR body and this handoff with the final exact HEAD, request exact-head GPT review, and fix only review findings in the same PR. After approval, confirm available disk and the memory cgroup on Argos before the full build; never use Mac mini compute. Then verify full row reconciliation, coordinate and region-ID uniqueness, provenance/linkage cardinality, class-mask counts, tabix queries, and reproducible hashes. Keep all data and results outside the repository.
