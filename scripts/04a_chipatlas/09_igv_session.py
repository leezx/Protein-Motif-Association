"""Step 4a §11: IGV session for the occupancy evidence tracks (paths relative to the session file).

usage: 09_igv_session.py <out_session.xml> [locus] [variant]
variant: '' (raw tracks), '_noBlacklist' or '_blacklistOnly' (ENCODE v2 split; directories tracks<variant>/ and
tracks_histone<variant>/).
Order: chromatin accessibility (ATAC, DNase), protein evidence (TF, CAP, all proteins, experiments, Pol II, Pol III),
histone evidence (modification diversity,
experiments, then the six core marks by functional group). Each track autoscales on its own y-axis; heights
across tracks are not comparable.
"""
import sys
from xml.sax.saxutils import quoteattr

TRACKS = [
    ("tracks_atac/atac_celltypes.bw", "ATAC cell-type diversity", "0,150,200"),
    ("tracks_atac/atac_experiments.bw", "ATAC experiments", "100,180,210"),
    ("tracks_dnase/dnase_celltypes.bw", "DNase cell-type diversity", "0,110,160"),
    ("tracks_dnase/dnase_experiments.bw", "DNase experiments", "80,140,180"),
    ("tracks/tf.bw", "PMA TF diversity", "31,78,155"),
    ("tracks/cap.bw", "PMA CAP diversity", "117,62,145"),
    ("tracks/proteins.bw", "PMA all-protein diversity", "0,121,121"),
    ("tracks/experiments.bw", "PMA protein ChIP experiments", "110,110,110"),
    ("tracks_rnapol/rnapol2_experiments.bw", "RNA Pol II experiments", "160,40,120"),
    ("tracks_rnapol/rnapol3_experiments.bw", "RNA Pol III experiments", "200,100,160"),
    ("tracks_histone/histone_modifications.bw", "Histone modification diversity", "90,90,90"),
    ("tracks_histone/histone_experiments.bw", "Histone modification experiments", "150,150,150"),
    ("tracks_histone/histone_H3K27ac.bw", "H3K27ac (active regulatory)", "230,120,20"),
    ("tracks_histone/histone_H3K4me3.bw", "H3K4me3 (active regulatory)", "200,30,30"),
    ("tracks_histone/histone_H3K4me1.bw", "H3K4me1 (enhancer-associated)", "220,180,0"),
    ("tracks_histone/histone_H3K27me3.bw", "H3K27me3 (repressive)", "40,90,200"),
    ("tracks_histone/histone_H3K9me3.bw", "H3K9me3 (repressive)", "40,40,90"),
    ("tracks_histone/histone_H3K36me3.bw", "H3K36me3 (transcription elongation)", "30,140,60"),
]


def main(out, locus="chr4:15966228-16085729", variant=""):
    tracks = [(p.replace("/", f"{variant}/", 1),
               n + (f" [{variant.strip('_')}]" if variant else ""), c) for p, n, c in TRACKS]
    res = "\n".join(f"        <Resource path={quoteattr(p)}/>" for p, _, _ in tracks)
    trk = "\n".join(
        f"        <Track attributeKey={quoteattr(p.split('/')[-1])} autoScale=\"true\" clazz=\"org.broad.igv.track.DataSourceTrack\" "
        f"color=\"{c}\" fontSize=\"10\" height=\"50\" id={quoteattr(p)} name={quoteattr(n)} renderer=\"BAR_CHART\" "
        f"visible=\"true\" windowFunction=\"max\"/>" for p, n, c in tracks)
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Session genome="hg38" hasGeneTrack="true" hasSequenceTrack="true" locus="{locus}" relativePaths="true" version="8">
    <Resources>
{res}
    </Resources>
    <Panel height="900" name="DataPanel" width="1600">
{trk}
    </Panel>
</Session>
"""
    open(out, "w").write(xml)


if __name__ == "__main__":
    main(*sys.argv[1:4])
