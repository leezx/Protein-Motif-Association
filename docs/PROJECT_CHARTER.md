# Project Charter — <PROJECT_NAME>

> **How to use this file**: copy it to `docs/PROJECT_CHARTER.md` inside
> the new project's own folder under `PR/<PROJECT_NAME>/`, fill in every
> `<...>` placeholder in Part 1, and leave Part 2 as-is unless the
> project has a genuine reason to deviate (state the reason inline if it
> does). **Any agent (Claude, Codex, or otherwise) must read this file
> in full before doing any work on the project** — it is the constitution
> the project operates under, not a suggestion. If an instruction here
> conflicts with a direct instruction from the user in chat, the user's
> chat instruction wins for that turn, but ask if the conflict looks
> like it wasn't intentional.

This template encodes the working pattern proven across
`PR/TWEAKR-OncoPlacental` (7+ steps, ~7 PRs, external data acquisition +
real cluster compute, closed to APPROVE on every PR before merge). It is
a specialization of the workspace-wide rules in `AGENTS.md` and
`DIRECTORY_CONVENTION.md` for **computational biology projects that pair
GitHub-PR-based iteration with a ChatGPT web-review loop and Argos
cluster compute**. Read those two files too — this charter does not
repeat what they already say, only what's specific to this pattern.

---

## Part 1 — Fill in for this project

- **Project name / repo**: `Protein-Motif-Association` (PMA; local folder
  `PR/Protein–Motif-Association`) — GitHub repo
  `github.com/leezx/Protein-Motif-Association`.
- **Founding question(s)**: Can we systematically map and quantify
  protein–motif genomic associations across the human
  chromatin-associated proteome using calibrated statistics and
  reproducible occupancy evidence? (frozen in
  `design/PMA_pseudo_figures_v0.2.md`)
- **Definition of 100%**: a released Human Protein–Motif Association
  Reference — an association matrix over ChIP-Atlas-derived occupancy
  and a curated, nonredundant, quality-graded motif repertoire — with
  (1) calibrated genomic association against matched background,
  (2) within-biosample protein-specificity statistic, (3) HOT-region and
  assay/biosample confounder control, (4) evidence grading
  (statistical support, independent replication, orthogonal evidence),
  and the two core figures (Fig. 1 resource construction, Fig. 2
  statistical calibration & reproducibility) built from real compute.
- **Explicit non-goals / deferred scope**: motif-dependent recruitment
  mechanism / recruitment grammar; perturbation experiments; ASB as a
  primary validation criterion (optional only); ChIP-exo/nexus
  (optional); RARB as a standalone main figure; binding to
  CancerRegAtlas; re-processing raw ChIP data as a novelty claim;
  application figures (Fig. 3+) until results justify them.
- **Immediate next step**: design `PMA Statistical Framework v0.1` —
  compare peak overlap, summit-centered enrichment, matched genomic
  background and within-biosample specificity; decide primary vs.
  auxiliary estimators and independent validation.
- **ChatGPT review conversation**: ChatGPT project **RA-Xiaolu** → conversation "PMA项目",
  https://chatgpt.com/g/g-p-6a70c0b8e77c81919ffc6390e12eacb0/c/6acfe12c-a128-83ea-8465-9bf5feca5a0b
  (set 2026-10-14; reuse for every PR).
- **Compute location**: `TBD`.

---

## Part 2 — Standing operating rules (keep as-is; note deviations inline)

### 2.1 Repo shape

```text
<PROJECT_NAME>/
├── README.md              — orientation; points to PROJECT_SUMMARY.md and Worklog.md
├── Worklog.md              — full chronological log, append-only in spirit
├── .gitignore              — blocks large data extensions (see 2.3)
├── docs/
│   ├── PROJECT_CHARTER.md  — this file, filled in
│   ├── PROJECT_SUMMARY.md  — staged deliverable report, updated at milestones
│   ├── STEP<N>_<NAME>_DESIGN.md    — one per step, written and reviewed BEFORE compute
│   └── STEP<N>_<NAME>_RESULTS.md   — one per step, written AFTER real compute
├── scripts/
│   └── <NN>_<step_name>/  — code for that step, numbered to match docs/results
├── results/
│   └── <NN>_<step_name>/  — every real compute output for that step
└── datasets/
    └── <dataset_id>/dataset.md  — manifest for each external dataset acquired
```

Step numbering in `docs/`, `scripts/`, and `results/` must stay aligned
— `scripts/07_x/` produces `results/07_x/` documented in
`docs/STEP7_X_RESULTS.md`. Never split one step across mismatched
numbers.

### 2.2 The step lifecycle (repeat for every step)

1. **Design first.** Before any compute or data acquisition, write
   `docs/STEP<N>_<NAME>_DESIGN.md` locking scope, method, exact
   contracts (data schemas, population definitions, statistical
   parameters) — everything a later reviewer or a future agent would
   otherwise have to guess. Ambiguity resolved later is ambiguity that
   should have been locked here.
2. **Branch.** One branch per PR, named for the step
   (`step<N>-<short-name>`), off latest `main`.
3. **Implement, commit.** Small, real, verifiable commits. Never fake
   or simulate compute output — if compute hasn't run yet, the PR says
   so; it does not contain placeholder numbers.
4. **Open the PR.** Push the branch, open a PR against `main` with `gh`
   or the GitHub UI.
5. **Submit to the ChatGPT reviewer** — the **same persistent
   conversation/tab** for every PR in this project (Part 1). Do not open
   a new conversation per PR; append. When Chrome's page-text tool
   truncates mid-word, `navigate` to the same URL, wait ~3-4s, and
   re-read rather than assuming truncation means the content doesn't
   exist.
6. **Independently verify every reviewer finding against real committed
   data or a live source before fixing it.** Never take a reviewer claim
   at face value, and never take your own prior round's conclusion at
   face value either — a later round finding your own earlier "could not
   verify" was itself incomplete is a sign the process is working, not a
   failure.
7. **Iterate to APPROVE.** Fix real findings; push back (with evidence)
   on findings that don't hold up rather than making cosmetic changes to
   satisfy a reviewer comment that's wrong.
8. **Report APPROVE to the user and stop.** Summarize what the PR does
   and what the review found. **Do not merge without an explicit,
   separate confirmation from the user for that specific PR** — a prior
   merge confirmation does not carry over to the next PR.
9. **After merge**, append a Worklog entry (2.4) and, if this step
   closes a meaningful chunk of the project, update
   `docs/PROJECT_SUMMARY.md` (2.5).

### 2.3 Data separation — never in git

#### Eight hard data-placement rules

These are hard constraints for every project created from this template:

1. **No data in `PR/` repositories.** Raw, processed, derived, cached,
   temporary, and downloaded data must never be stored under the project
   repository, even if `.gitignore` would hide it.
2. **All data belongs under the workspace `DATA/` tree.** Use
   `/Volumes/Stelligen_SSD/Stelligen/DATA/<data_type>/<dataset_id>/` as the
   only canonical storage root for acquired or generated data.
3. **Separate lifecycle states.** Within a dataset directory, use `raw/`
   for immutable source files, `processed/` for versioned transformations,
   and `result/` for machine-generated evidence and outputs.
4. **Repositories hold metadata, not payloads.** A repo may contain small
   manifests, schemas, checksums, source URLs, scripts, documentation, and
   small summary tables; it may not contain count matrices, H5AD/RDS/LOOM
   objects, FASTQ/BAM/CRAM files, archives, or other data payloads.
5. **Every dataset gets a repo-side manifest.** The manifest records the
   canonical DATA path, source URL/accession, license/access terms, file
   list, expected size, checksum, acquisition date, and current status.
6. **Downloads go directly to DATA.** Never download first into `PR/`, a
   repo working tree, or an undocumented temporary project directory. If a
   transfer must be resumed, resume it in its final DATA location.
7. **Transfers are not complete until verified.** Require exact byte-size
   and format/archive-integrity checks, then record SHA256 or MD5 checksums;
   cross-machine transfers require matching checksums at both ends.
8. **The repository safety net is mandatory but insufficient.** Keep the
   standard large-file patterns in `.gitignore`, and run a repository/data
   placement check before commit; `.gitignore` must never be treated as
   permission to place data in the repository.

- **No data files live in the repo.** All raw, processed, and result
  data lives under `DATA/<data_type>/<dataset_id>/` at the workspace
  root, following `DATA/README.md` and `DIRECTORY_CONVENTION.md`
  exactly (`raw/` append-only, `processed/` versioned, `result/` for
  machine-generated evidence). The project repo only holds:
  code (`scripts/`), small metadata (`datasets/<id>/dataset.md`,
  small `.tsv`/`.json` summary tables under `results/` — a coverage
  table or a scores summary is fine to commit; a raw count matrix is
  not), and docs.
- The `.gitignore` in every new project repo should block the same
  large-data extensions blocked in `TWEAKR-OncoPlacental/.gitignore`
  (`*.h5ad *.h5 *.loom *.rds *.mtx *.mtx.gz *.fastq* *.bam *.cram
  *.tar.gz` etc. — see `_TEMPLATE/gitignore_template`). This is a safety
  net, not the primary control — the primary control is: think about
  where a file belongs before writing it, not after `git status`
  surprises you.
- Every dataset acquired gets a `datasets/<dataset_id>/dataset.md`
  manifest in the project repo (source URL, license/access terms,
  what was downloaded and why, what wasn't) — this is metadata, not
  data, so it does commit.
- Never create accounts or handle credentials to get past a login wall
  to reach data. If a dataset is genuinely access-gated (e.g. a Zenodo
  record behind login), surface that as a blocker to the user and ask
  how to proceed — do not work around it, and do not silently drop the
  dataset without saying so.

### 2.4 Compute — heavy compute runs on the cluster, not locally

- Real compute (anything beyond trivial local scripting) runs on the
  project's designated cluster (Part 1) via `qsub`/SGE, in the
  project's conda env — never locally, and never left running
  un-submitted on the cluster's login node.
- Lightweight I/O (downloads, unpacking, quick shape/sanity checks) can
  run directly on the login node without a qsub wrapper — same
  precedent as this project's data-acquisition phase. If unsure whether
  something counts as "lightweight," default to qsub.
- File transfer between local and cluster (when `scp`/`rsync` are
  unavailable): `ssh <cluster> "cat <remote>" > <local>` to pull,
  `cat <local> | ssh <cluster> "cat > <remote>"` to push — **always**
  followed by md5 verification on both ends. Never treat a transfer as
  done until the checksums match.
- Before submitting a long/expensive qsub run, do a real smoke test
  first: syntax-check the script, run its loader/setup logic against
  real (not synthetic) data at small scale, confirm shapes and a couple
  of sanity numbers, *then* submit the full run. This catches
  integration bugs before they cost hours of cluster time.
- Never pipe a download through `tail`/`head` — it swallows the exit
  code and hides real failures. Verify downloads against an exact byte
  count or archive-integrity check, never a rounded size shown by a web
  UI.

### 2.5 Documentation discipline — after every step, not just at the end

- **After every merged PR**, append a `Worklog.md` entry: what was done,
  how, why, what was found (including real bugs caught and negative/
  unresolved findings — do not only record clean successes). Use
  `_TEMPLATE/WORKLOG_TEMPLATE.md` for the entry shape.
- **Design docs and results docs are separate files** — a design doc is
  written and reviewed before compute exists; a results doc reports
  what the compute actually produced, including anything that didn't
  match the design's pre-compute estimate. Do not retroactively edit a
  design doc to match results after the fact; write a results doc.
- **When the project reaches its defined 100% (Part 1), or at any other
  major milestone worth a checkpoint**, write or update
  `docs/PROJECT_SUMMARY.md` — a structured, staged deliverable report:
  what was done, how, why, what's been answered, what's still open. Use
  `_TEMPLATE/PROJECT_SUMMARY_TEMPLATE.md`. This is the file a new reader
  (human or agent) should be pointed to first; `README.md` says so.
- Quantitative progress reporting (per `AGENTS.md` rule 10): define the
  100% endpoint before assigning any percentage (Part 1 does this once,
  up front); report current % and delta since last checkpoint together,
  e.g. `72% → 81% (+9%)`; distinguish engineering/infrastructure
  completion from scientific/interpretive completion — finishing a
  loader is not the same as answering the founding question.

### 2.6 Reporting and honesty norms

- Report outcomes faithfully. If a coverage check flags a real gap, say
  so and investigate it empirically rather than assuming a plausible-
  sounding mechanism and moving on — an assumed mechanism that turns out
  to be checked against the wrong object is worse than an honestly
  unresolved gap. Reporting a real, hedged, partial finding grounded in
  data is honestly better than a confident but unverified explanation.
- A "could not verify" conclusion is not the end of the investigation —
  it's a flag that the next round should try harder or from a different
  angle, not a permanent shrug.
- Never fabricate or extrapolate compute results. If a run hasn't
  happened yet, the doc says "not yet run," not a plausible-looking
  placeholder number.

---

## Related workspace-level references (do not duplicate here)

- `AGENTS.md` — workspace-wide agent operating rules (data placement,
  progress reporting, single-ChatGPT-conversation-per-project rule).
- `DIRECTORY_CONVENTION.md` — result-tree structure and naming rules.
- `DATA/README.md` — the `DATA/<type>/<dataset_id>/{raw,processed,
  result}` convention this charter's §2.3 points to.
- `SOFTWARES/tools/GPT_Codex_PR/` — a related, more generic
  ChatGPT-plans/Codex-implements/GitHub-PR protocol for software
  engineering tasks (task-packet + handoff-note shaped). This charter's
  step-lifecycle (§2.2) is the computational-biology-project
  specialization of the same underlying idea: GitHub PRs plus a
  standing review loop as the shared workbench, not chat memory as the
  source of truth.
