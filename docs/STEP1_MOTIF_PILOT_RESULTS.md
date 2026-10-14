# Step 1 — Motif reference pilot: results

Run 2026-10-14. Design: `docs/STEP1_MOTIF_PILOT_DESIGN.md`, including the
§3.3 amendment on q-values. Code: `scripts/01_motif_pilot/run_pilot.sh`.
Summaries are in `results/01_motif_pilot/`. Full tables are under
`$BIO_DATA/2.PROJECTS/PMA/motif_reference/result/step1_motif_pilot/`.

The primary criterion is per-query BH q < 0.01 over 1,685 Codebook
targets, with aligned overlap ≥ 60 % of the shorter motif. This
criterion is provisional (see §4).

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
| other_TF_only, paralog cluster | 51 | 6 % | matches only another TF, which shares a Codebook cluster with the query TF's PWM (e.g. CEBPA → CEBPG) |
| other_TF_only, unrelated | 64 | 7 % | pattern is present in Codebook but assigned to an unrelated TF |
| not_represented, near miss (best q < 0.05) | 72 | 8 % | mostly short motifs; see §4 |
| not_represented, no match at q < 0.05 | 105 | 12 % | genuinely absent from the Codebook representative set |

Sensitivity: at q < 0.001 the same_TF count falls to 457; at q < 0.05 it
rises to 641. The overlap cutoff (0.5–0.75) never changes the result,
because every significant Pearson-TOMTOM hit already overlaps ≥ 74 %
(median 100 %). See `sensitivity_grid.tsv`.

Coverage depends on motif length (`q1_coverage_by_length.tsv`): 27 % of
≤ 8 bp JASPAR motifs are not represented, against 12 % of > 15 bp motifs.

## Q2 — Which JASPAR patterns does the Codebook representative set not keep?

The 105 hard not-represented human motifs (`q2_human_not_represented_motifs.tsv`):
- **Assay:** ChIP-seq 56, HT-SELEX 27, GHT-SELEX 8, other 14.
- **Composite heterodimers (18):** CAP-SELEX/HT-SELEX ETS–FOX, ETS–HOX,
  ETS–FIGLA and TFAP4–ETS composites, GATA1::TAL1, RARA::RXRA.
- **ChIP-derived C2H2-ZF/ZBTB motifs (45):** ZBTB, ZNF and IKZF motifs.
  These may reflect the TF's in-vivo preference, a partner's motif, or
  artefacts. Step 1 cannot tell these apart.
- **TALE / homeobox alternative patterns:** MEIS2, MEIS3, PBX2, PBX3,
  PKNOX1, NKX2-2, NKX2-5.
- **ChIP-seq motifs of well-characterised TFs** (SOX2, SOX10, PAX5, EBF1,
  RUNX3, MYB): plausibly cofactor or composite patterns in the occupied
  regions.

**Alternative motifs per TF:** 35 human TFs have more than one JASPAR
non-redundant motif (76 motifs in total). For 15 of them, at least one
motif matches nothing in Codebook. For 21, the motifs best-match
different Codebook PWMs. Codebook therefore keeps some alternatives
(e.g. ASCL1, BACH2, NR2C2, SREBF1: every JASPAR motif matches a
distinct same-TF Codebook PWM) and drops others (e.g. TFAP2A/C, MEIS2, BCL11A).

Information content does not separate the classes. Median IC per
position is 1.33 for not represented and 1.35 for same_TF. The missing
motifs are not low-information noise.

## Q3 — Can Codebook's clustering be reused?

Codebook Supp. Table 10 clusters (MoSBAT, 613 clusters over 1,652
clustered PWMs) were compared with TOMTOM, Codebook × Codebook:
- **Size distribution:** median cluster size is 1. The tail is coarse.
  Cluster 2 holds 225 PWMs (AT-rich homeodomain, ARID and more), and
  cluster 13 groups AHR with CpG binders (CXXC, DNMT1, CAMTA).
- **Cohesion:** pooled over pairs, 26 % of within-cluster pairs match
  under TOMTOM q < 0.01. This is dominated by the giant clusters. Per
  cluster, the median within-cluster match fraction is 1.0 (180 clusters
  of size ≥ 2). It drops to 0.47 for clusters of 6–10 and 0.21 for
  clusters > 50.
- **Separation:** 0.1 % of between-cluster pairs match (1,322 pairs).
  Even so, 13 % of all TOMTOM-matched pairs cross Table-10 cluster
  boundaries.
- **Consistency:** of 640 JASPAR motifs that hit more than one Codebook
  PWM, 49 % hit PWMs in a single Table-10 cluster.
- Supp. Table 11 (HOCOMOCO v13 + Codebook, 653 clusters, average linkage
  with silhouette-chosen cut, HOCOMOCO "D" clusters discarded) is built
  on a different motif set. It was not tested quantitatively in Step 1.

**Conclusion:** the Codebook clusterings are useful as an external
reference, but should not be PMA's clustering. Small clusters agree with
TOMTOM. Large clusters lump distinct patterns, which is the over-merging
`motif_resources.md` §4 warns about, and 13 % of similarity edges cross
cluster boundaries.

## Decision (per design §5)

1. Use **Codebook 2026 as the TF-coverage backbone**. It names 759 of
   762 JASPAR human TFs, and it has 1,421 TFs against JASPAR's 762.
2. **Q2 is substantial** (105 hard-missing, plus 64 assigned to
   unrelated TFs). This confirms the multi-source raw-level design.
   Step 2 integrates HOCOMOCO, CisBP and Factorbook, and keeps JASPAR
   composites and ChIP-derived motifs.
3. **PMA clusters are built independently**, then compared with Codebook
   Table 10/11 as an external benchmark (ARI, cluster purity), not
   inherited.

## Caveats and open items (Step 2 design inputs)

4. **The match criterion is length-sensitive.** Short motifs (≤ 8–10 bp)
   cannot reach low TOMTOM p-values. 72 "not represented" motifs are near
   misses (q 0.01–0.05). For example, JASPAR CEBPA ChIP-seq
   `ATTGCACAAT` against Codebook CEBPG `ATTGCGCAAT` gives q = 0.013.
   Step 2 needs a length-aware or empirical criterion, for example
   calibrated on known same-TF pairs or on shuffled-column nulls,
   instead of a fixed q.
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
