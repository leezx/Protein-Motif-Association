# Step 1 — Motif reference pilot: results

Run 2026-10-14. Design: `docs/STEP1_MOTIF_PILOT_DESIGN.md`, including the
§3.3 amendment on q-values. Code: `scripts/01_motif_pilot/run_pilot.sh`.
Summaries are in `results/01_motif_pilot/`. Full tables are under
`$BIO_DATA/2.PROJECTS/PMA/motif_reference/result/step1_motif_pilot/`.

The primary criterion is per-query BH q < 0.01 over 1,685 Codebook
targets, with aligned overlap ≥ 60 % of the shorter motif. This
criterion is provisional (see §4). The BH family is the 1,685 targets of
**one** query, so q < 0.01 is a per-query candidate-match criterion, not
a global FDR for the reference. Completeness is asserted in code: every
query has exactly one row per target (1,717,015 and 2,839,225 pairs).
For Codebook × Codebook, self-pairs are part of the BH family and are
dropped before any graph is built.

Every class label below is relative to this cutoff ("no match under the
primary criterion"). None of them is a biological claim of absence.

*Revised 2026-10-14 after ChatGPT review round 1 (REQUEST CHANGES):*
- labels were made objective;
- cutoff-dependent wording was made explicit;
- assertions and BH tests were added;
- Q3 was reframed as an agreement check between two similarity
  definitions.

## Inputs

| Set | Motifs | Notes |
|---|---|---|
| Codebook 2026 Supp. Data 1 | 1,685 PWMs, 1,421 TFs | 1,505 direct and 180 inferred evidence (ortholog/paralog), per Supp. Table 10. 4 PWMs have all-zero spacer rows, set to uniform. |
| JASPAR 2026 CORE vertebrates, non-redundant | 1,019 | 857 human (tax 9606), 162 non-human (156 mouse), 77 heterodimers |

## Q1 — Does Codebook cover JASPAR human TFs?

**TF level: almost completely.** 759 of the 762 human TFs named in JASPAR
2026 CORE have at least one Codebook representative PWM. 732 of these
have a *direct-evidence* Codebook PWM.

**Motif level: only partly.** The 857 JASPAR human motifs break down as:

| Class | n | % | Meaning |
|---|---|---|---|
| same_TF | 565 | 66 % | matches a Codebook PWM of its own TF |
| other_TF_only, same Codebook cluster | 51 | 6 % | matches only other TFs' PWMs, and one of them shares a Supp. Table 10 cluster with the query TF's PWM (e.g. CEBPA → CEBPG). This is not a paralogy claim. |
| other_TF_only, different Codebook cluster | 64 | 7 % | matches only other TFs' PWMs, none in a cluster with the query TF's PWM |
| no_match_primary, near miss (best q < 0.05) | 72 | 8 % | mostly short motifs; see §4 |
| no_match_primary, no match at q < 0.05 | 105 | 12 % | no full-length match even at the relaxed cutoff; see Q2 |

Sensitivity: at q < 0.001 the same_TF count falls to 457; at q < 0.05 it
rises to 641. The overlap cutoff (0.5–0.75) never changes the result,
because every significant Pearson-TOMTOM hit already overlaps ≥ 74 %
(median 100 %). See `sensitivity_grid.tsv`.

Matching depends on motif length (`q1_coverage_by_length.tsv`):
no_match_primary is 27 % for ≤ 8 bp, 19 % for 9–10 bp, 15 % for 11–12 bp,
21 % for 13–15 bp and 12 % for > 15 bp. The trend is broad but not
monotonic.

`jaspar_motif_coverage_classes.tsv` (DATA result dir) also gives, for
every query, the cutoff-free best match: target, TOMTOM p, BH q and
overlap fraction.

## Q2 — Which JASPAR patterns lack a full-length match in the Codebook representative set?

The 105 human motifs with no match even at q < 0.05
(`q2_human_no_match_at_q005_motifs.tsv`) fall into three descriptive
groups. No motif decomposition was attempted.

| Group | n | Reading |
|---|---|---|
| short, ≤ 10 bp | 69 | Dominated by the length/power limit (§4). Not evidence of a missing pattern. Many are ChIP-derived ZNF/ZBTB motifs. |
| composite heterodimer | 18 | CAP-SELEX/HT-SELEX ETS–FOX, ETS–HOX, ETS–FIGLA, TFAP4–ETS, GATA1::TAL1, RARA::RXRA. The components may exist in Codebook as monomers. Only the full composite is unmatched. |
| single protein, > 10 bp | 18 | The best candidates for alternative patterns not kept in the Codebook representative set. Unverified. |

By assay, the 105 are ChIP-seq 56, HT-SELEX 27, GHT-SELEX 8 and other 14.

**Alternative motifs per TF:** 35 human TFs have more than one JASPAR
non-redundant motif (76 motifs in total). For 15 of them, at least one
motif has no primary match. For 21, the motifs best-match different
Codebook PWMs. Codebook therefore keeps some alternatives
(e.g. ASCL1, BACH2, NR2C2, SREBF1: every JASPAR motif matches a
distinct same-TF Codebook PWM), while others lack a full-length match
(e.g. TFAP2A/C, MEIS2, BCL11A).

Median IC per position is similar across classes (1.33 vs 1.35). This
does not show that the unmatched motifs are free of noise.

**What Q2 supports:** the Codebook representative set alone does not
reproduce a non-trivial part of JASPAR's full-length patterns, mainly
composites and some longer alternative motifs. That is enough to keep
the multi-source raw-level design. It does not establish a count of
"novel" or "absent" patterns.

## Q3 — Can Codebook's clustering be reused?

This is an agreement check between two similarity definitions:
Codebook Supp. Table 10 (MoSBAT affinity correlation, average linkage,
613 clusters over 1,652 PWMs) and TOMTOM-Pearson (Codebook × Codebook).
It does not test whether either clustering is biologically correct.
Directed TOMTOM matches become undirected edges under two rules:
*either* direction (candidate edges) or *both* directions (high
confidence).

| Metric | either | both |
|---|---|---|
| TOMTOM edges | 10,191 | 8,015 |
| within-cluster pairs matched (pooled) | 26 % | 21 % |
| between-cluster pairs matched | 0.10 % (1,322) | 0.055 % (732) |
| share of edges crossing Table-10 clusters | 13 % | 9 % |

- The cluster-size distribution has median 1 and a long tail: cluster 2
  has 225 PWMs (AT-rich homeodomain, ARID and others), and cluster 13
  groups AHR with CpG binders (CXXC, DNMT1, CAMTA).
- The pooled within-cluster figure is dominated by the large clusters.
  Per cluster, the median within-cluster match fraction is 1.0 (180
  clusters of size ≥ 2). It is 0.47 for clusters of 6–10 and 0.21 for
  clusters > 50.
- Of 640 JASPAR motifs that hit more than one Codebook PWM, 49 % hit
  PWMs in a single Table-10 cluster.
- Supp. Table 11 (HOCOMOCO v13 + Codebook, 653 clusters) is built on a
  different motif set and was not tested.

**Conclusion:** the two similarity definitions agree well for small
clusters and diverge for the large ones. PMA should therefore build and
evaluate its own clusters on its own motif set, and report agreement
with Codebook Table 10/11 as an external benchmark. This is not a
finding that the Codebook clusters are wrong.

## Decision (per design §5)

1. Use **Codebook 2026 as the TF-coverage backbone**. It names 759 of
   762 JASPAR human TFs, and it has 1,421 TFs against JASPAR's 762.
2. **Q2 is large enough to keep the multi-source raw-level design.**
   It shows 105 no-match motifs at q < 0.05 (18 composites and 18 long
   single-protein motifs; the rest are short), plus 64 matching only
   PWMs from a different Codebook cluster. Step 2 integrates HOCOMOCO,
   CisBP and Factorbook, and keeps JASPAR composites and ChIP-derived
   motifs.
3. **PMA clusters are built independently**, then compared with Codebook
   Table 10/11 as an external benchmark (ARI, cluster purity), not
   inherited.

## Caveats and open items (Step 2 design inputs)

4. **The match criterion is length-sensitive.** Short motifs (≤ 8–10 bp)
   cannot reach low TOMTOM p-values. 72 no_match_primary motifs are near
   misses (q 0.01–0.05). For example, JASPAR CEBPA ChIP-seq
   `ATTGCACAAT` against Codebook CEBPG `ATTGCGCAAT` gives q = 0.013.
   Step 2 keeps this criterion as `statistical_match_v0.1`. It also
   freezes a benchmark of known positive pairs and hard negatives, then
   evaluates matching by length before choosing between a uniform
   effect-size cutoff, length strata or empirical calibration. No
   uncalibrated length-specific thresholds will be used.
5. TOMTOM's own q-values are not reproducible across query order: the
   π₀ bootstrap RNG differed by ≤ 0.5 % between serial and chunked runs.
   PMA uses deterministic per-query BH from TOMTOM p-values. The p-values
   matched the serial run exactly (61,373 / 61,373 pairs).
6. Non-human JASPAR motifs are mapped by uppercase symbol only.
   Unmapped examples include Zfp809, Dux and Rhox11. Step 2 needs real
   ortholog mapping (workspace `Ensembl_orthologues`).
7. 180 Codebook representative PWMs are *inferred*, not measured. They
   count toward TF coverage, but CORE assignment must keep the evidence
   flag.
8. HOCOMOCO is now at v13/v14, not v12. Codebook's MARA set uses v13.
   The version must be chosen in the Step 2 design.
9. TOMTOM runtime scales as queries × targets. This run took 14 min
   wall-clock on 6 cores for 2.7k × 1.7k motifs. Full multi-source
   all-vs-all (~20k motifs) will need Argos/O2 or a prefilter.
