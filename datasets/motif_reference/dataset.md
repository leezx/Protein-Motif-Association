# Dataset manifest — PMA motif reference

Canonical path: `$BIO_DATA/2.PROJECTS/PMA/motif_reference/` (all payloads live there; nothing here).

| Source | Fetched | Files (raw) | License | Status |
|---|---|---|---|---|
| Codebook 2026 — Nature ESM: Supp. Tables 1–16 (MOESM3), Supp. Data 1 representative PWMs (MOESM4) | 2026-10-14 | 2 zips, unpacked (1,685 PWMs) | open access | verified (Zenodo md5 match) |
| Codebook Zenodo 17307845 (HOCOMOCO v13 + Codebook MARA representatives, 653) | 2026-10-14 | representative_motifs.zip, groups.json, README | CC-BY | verified md5 |
| Codebook Zenodo 15667805 (MEX) — README, MEX_top1.zip, metadata_complete_dataset.tsv | 2026-10-14 | 3 files (large tar sets not fetched) | CC-BY | verified md5 |
| JASPAR 2026 CORE vertebrates NR/redundant (MEME, JASPAR), UNVALIDATED NR (MEME), JASPAR2026.sqlite | 2026-10-14 | 7 files | CC-BY 4.0 | sizes recorded; no upstream checksum published |

| HOCOMOCO v14 (H14CORE meme/pcms, annotations, clusters, tf_masterlist) | 2026-10-14 | 8 files | WTFPL | sizes + md5 recorded; no upstream checksum |
| CisBP 3.10 human species archive (TF info) + EntireDataset PWMs.zip | 2026-10-14 | 2 zips | CisBP terms | species-archive PWM file corrupt (interleaved log); see README.source.md |
| Factorbook ChIP-seq MEME catalog + metadata TSV | 2026-10-14 | 2 files | Factorbook/ENCODE | sizes + md5 recorded |
| Factorbook HT-SELEX catalog | — | — | — | deferred: HTTP 429 to scripts; manual browser download needed |

Per-file URLs, byte sizes and md5: `raw/<source>/<date>/source_manifest.tsv` and `checksums.md5`.
Fetch script: `scripts/01_motif_pilot/00_fetch_sources.sh`.

Not fetched: MEX large tars (MEX.PBM/SMS/CHS, ~15 GB, raw experimental data; not needed for a motif reference).
