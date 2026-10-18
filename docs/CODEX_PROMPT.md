# Prompt to start Codex on PMA

Paste the block below into Codex, with the working directory set to the repo root
(`/Volumes/Stelligen_SSD/Stelligen/PR/Protein–Motif-Association`).

---

You are taking over the PMA (Protein–Motif-Association) project from another agent.

**Before doing anything:**
1. Read `docs/CODEX_HANDOFF.md` in full. It holds the project state, hard rules, Argos practicalities, what is running
   and the ordered next steps.
2. Then read `docs/PROJECT_CHARTER.md`, the workspace `/Volumes/Stelligen_SSD/Stelligen/AGENTS.md` and `HANDOFF.md`
   (PMA sections), and `docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md`.
3. Check out branch `step4b-atac-footprinting`. It contains all earlier steps. Run `git log --oneline -10` and confirm
   the head matches the handoff, or is newer.
4. Check the live state on Argos before acting:
   ```
   ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu 'cat /home/zz950/PMA_fetch/fp_4b1.log; ps -u $USER -o etime,args | grep -E "run_4b1|run_round1|Rscript|rgt-hint|TOBIAS" | grep -v grep'
   ```
   Kill/launch logic always goes in a script file that you scp over. Never put `pgrep -f`/`pkill -f` inside an ssh
   one-liner.

**Your task now: Step 4b-1, the round-1 benchmark of motif-free ATAC footprint callers on CPU.**
- If the driver `run_4b1.sh` is still waiting or running, monitor it.
- If the smoke test failed, find the real error in `processed/round1/runs_smoke/*/*.log`, fix the runner in
  `scripts/04b_footprint/`, commit, `git pull` in `/home/zz950/PMA_code_4b`, and re-run the driver.
- When the 12 round-1 jobs finish, write `scripts/04b_footprint/eval_round1.py`. Report per caller × dataset:
  - wall time;
  - peak RSS;
  - CPU cores;
  - number of events;
  - false-positive events per callable Mb on naked gDNA, at the default threshold and over a threshold sweep;
  - event counts in HCT116 control and auxin.
- Then follow handoff §7 in order:
  1. genome-wide speed-gate runs;
  2. TraceBIND full mode with mtDNA;
  3. B2 (in vitro + CTCF degron);
  4. B3 (K562 ChIP-exo / CUT&RUN);
  5. B4 (STREME);
  6. selection by the pre-registered rule;
  7. a C++ port only if the accuracy winner fails the 4 h / 32-CPU / 40 GiB gate.

**Non-negotiable rules:**
- Compute only on Argos, never on the Mac. Keep every task under about 50 GB RAM.
- No GPU tools.
- No data in the repo. Raw data is append-only.
- Do not touch `Zhixins-KB`.
- O2 rule: at most 2 DUO prompts per hour. Run `ssh -O check o2` first; if there is no master connection, stop and ask
  the user. O2 is not needed for this task.
- Design before compute. Do not change approved thresholds or selection rules after seeing results; report failures
  as failures.
- Use the same ChatGPT review conversation ("PMA项目", URL in the handoff) for plans and milestone reviews. Verify
  every reviewer finding yourself.
- Never merge a branch or PR without the user's explicit, separate confirmation.
- Keep `HANDOFF.md` (workspace) and the result docs current. Report progress as percentage plus delta (now 33 %).
- Talk to the user in Chinese.
- Write result write-ups in `Figures/FigureN/FigureN.<key>.result.md`, in the Chinese "result" style (why, what,
  results, evidence, conclusion, short discussion).
- After each milestone, give the user a short Chinese summary:
  - what ran;
  - the key numbers;
  - what failed and why;
  - the next step;
  - any decision the user must make.
