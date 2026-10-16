# Step 2c — Additional de novo motif sources (fetch design)

Status: draft, 2026-10-16. Fetch only; import into a raw layer is a
separate, later decision. Requested by the user from the KB note
`2026-GPT-Project-PMA#PMA纳入最全denovo motif DB`: download every de novo
motif source listed there that is not yet in raw, with annotations, and
for ChIP-derived motifs the ChIP target protein.

## 1. Sources (checked 2026-10-16)

| Source | Already in raw? | What is fetched | Protein for ChIP motifs |
|---|---|---|---|
| Factorbook ChIP-seq MEME (6,921 in paper; 10,477 in catalog) | yes (Step 2) | — | ENCODE target (done) |
| Factorbook HT-SELEX | yes (Step 2) | — | ENA run → TF (done) |
| ENCODE GRAMMAR / MotifCompendium (ENCSR091GRD; Zenodo 17179111) | no | Zenodo supplementary zip (50 MB): TF-MotifCompendium 19,739 raw TF-MoDISco CWMs from 2,345 BPNet TF ChIP-seq models + 6,111 cluster / 1,920 metacluster CWMs; Chromatin-MotifCompendium 75,813 CWMs from ATAC/DNase ChromBPNet + clusters; unified 3,473-motif catalog; metadata | `target` per motif (ENCODE ChIP target), experiment, biosample, TFClass family, DBD, direct/indirect cluster name |
| ENCODE BPNet per-model motifs | no | for each of the 2,345 BPNet annotations the "sequence motifs" tar is streamed from ENCODE S3 (md5 checked) and only `*.PFM.meme` (counts and profile heads) and `README.txt` are kept: the probability matrices behind the CWMs | annotation target + experiment |
| ENCODE ChromBPNet per-model motifs | no | same for the 1,531 ChromBPNet annotations with a motifs tar (477 GB streamed; lower priority) | none (accessibility; cell type / organ only) |
| HDMA, Nature 2026 (Zenodo 17427146, 16747618) | no | 508-motif compendium (PPM, trimmed PPM, modisco h5, CWM images), `merged_modisco_patterns_map.tsv` (6,362 per-cluster patterns). The 13.6 GB `all_modisco_outputs.tar.gz` with per-cluster PPMs is streamed and only PPM/meme files kept | none (ATAC) |
| ENCODE-motifs (Kheradpour & Kellis 2014) | no | `motifs.txt` (discovered motifs per ENCODE TF dataset, 1.1 MB) + method page | dataset TF name in motif ID |
| Cistrome DB | no | **pending decision** (§3) | factor per sample (DB 2 API) |
| UniBind | — | not fetched: it predicts binding sites with JASPAR PWMs, no new motifs | — |
| GimmeMotifs library | — | not fetched: a clustered compilation of existing databases, not de novo | — |

## 2. Rules

- Raw is append-only: each source goes to
  `$BIO_DATA/2.PROJECTS/PMA/motif_reference/raw/<source>/2026-10-16/`
  with `source_manifest.tsv` (URL, size, md5, date), `checksums.md5`
  and `README.source.md`.
- Large streams run on Argos (rcapps3), never on the Mac mini; only the
  extracted motif files (MB scale) are copied back.
- Nothing already in raw is re-downloaded (Factorbook ChIP + SELEX,
  JASPAR, HOCOMOCO, CisBP, Codebook).
- CWMs are kept as published; PFMs come from the per-model tars. Any
  CWM → PFM conversion is out of scope.

## 3. Cistrome DB (decision needed)

De novo PWMs exist per sample (`denovoN` entries of MDSeqPos, next to
known-motif matches) but only through per-sample API calls
(`db3.cistrome.org/cistrome/samples/<id>/motif`); the ChIP factor comes
from `dc2.cistrome.org/api/inspector?id=<DCid>` or the batch metadata
file (behind a web form). Options: (a) the user downloads the batch
metadata file, then a rate-limited harvest of the motif API on Argos;
(b) rate-limited harvest of both APIs (~45k samples × 2 calls, ~1 call/s,
about a day); (c) defer Cistrome.
