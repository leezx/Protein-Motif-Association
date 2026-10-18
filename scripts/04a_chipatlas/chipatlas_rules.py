"""Step 4a: deterministic normalisation rules for ChIP-Atlas metadata (rules_version 4a.v1).

Design: docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md §5. Pure functions, no I/O except the loaders.
Every normalised value keeps its raw source next to it in the experiment table; nothing is forced.
"""
import csv
import re

RULES_VERSION = "4a.v1"
MISSING = "."

# ---------------------------------------------------------------- antigen -> HGNC (§5.1)

NON_GENE = re.compile(r"^(G-quadruplex|DNA-RNA hybrid|RNA-DNA hybrids?|BrdU|5-mC|5-hmC|O-GlcNAc|Crotonyllysine|"
                      r"Pan-acetyllysine|MethylCap|8-Hydroxydeoxyguanosine|Cyclobutane pyrimidine dimers|Biotin)$", re.I)
TAG_ONLY = re.compile(r"^(Epitope tags|GFP|FLAG|HA|V5|Myc-tag)$", re.I)


def load_hgnc(path):
    """approved symbol -> id; previous / alias symbol (upper) -> set of approved symbols; symbol -> gene groups."""
    appr, prev, alias, groups = {}, {}, {}, {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r.get("status", "Approved") != "Approved":
                continue
            s = r["symbol"]
            appr[s] = r["hgnc_id"]
            groups[s] = r.get("gene_group", "")
            for col, d in (("prev_symbol", prev), ("alias_symbol", alias)):
                for p in filter(None, (r.get(col) or "").strip('"').split("|")):
                    d.setdefault(p.upper(), set()).add(s)
    return appr, prev, alias, groups


def load_exceptions(path):
    """antigen_raw -> (status, symbol_or_dot, candidates, modification, note)."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader((line for line in f if not line.startswith("#")), delimiter="\t"):
            out[r["antigen_raw"]] = (r["status"], r["hgnc_symbol"], r["candidates"], r["modification"], r["note"])
    return out


def map_antigen(raw, hgnc, exceptions):
    """-> dict(symbol, hgnc_id, method, status, candidates, modification). Priority: exact approved >
    manual exception (overrides known symbol collisions, e.g. TAZ) > unique previous > unique alias."""
    appr, prev, alias, _ = hgnc
    a = raw.strip()
    res = dict(symbol=MISSING, hgnc_id=MISSING, method=MISSING, status="unmapped", candidates=MISSING,
               modification=MISSING)
    if a in appr:
        return {**res, "symbol": a, "hgnc_id": appr[a], "method": "hgnc_approved", "status": "approved_exact"}
    if a in exceptions:
        st, sym, cand, mod, _ = exceptions[a]
        r = {**res, "method": "manual_exception", "status": st, "candidates": cand or MISSING,
             "modification": mod or MISSING}
        if sym and sym != MISSING and sym in appr:
            r.update(symbol=sym, hgnc_id=appr[sym])
        return r
    if NON_GENE.match(a):
        return {**res, "method": "rule_non_gene", "status": "non_gene_target"}
    if TAG_ONLY.match(a):
        return {**res, "method": "rule_tag", "status": "tag_only"}
    for d, st in ((prev, "previous_symbol"), (alias, "unique_alias")):
        hits = d.get(a.upper(), set())
        if len(hits) == 1:
            s = next(iter(hits))
            return {**res, "symbol": s, "hgnc_id": appr[s], "method": f"hgnc_{st}", "status": st}
        if len(hits) > 1:
            return {**res, "method": f"hgnc_{st}", "status": "ambiguous", "candidates": ";".join(sorted(hits))}
    return res


CHROMATIN_GROUP = re.compile(r"chromatin|histone|bromodomain|SWI/SNF|polycomb|lysine methyltransferase|"
                             r"lysine demethylase|acetyltransferase|deacetylase|mediator complex|cohesin|"
                             r"condensin|nucleosome|PHD finger|chromodomain|NuRD|SAGA|INO80|ISWI|"
                             r"BAF complex|COMPASS|methyl-CpG", re.I)


def target_category(antigen_class, m, tf_set, groups):
    if antigen_class == "RNA polymerase" or (m["symbol"] != MISSING and m["symbol"].startswith("POLR")):
        return "polymerase"
    if m["symbol"] == MISSING:
        return "ambiguous_or_unmapped"
    if m["symbol"] in tf_set:
        return "sequence_specific_tf"
    if CHROMATIN_GROUP.search(groups.get(m["symbol"], "")):
        return "chromatin_regulator_or_cofactor"
    return "other_protein"


# ---------------------------------------------------------------- antibody (§5.2)

VENDORS = [  # (normalised name, pattern on the text)
    ("Abcam", r"\babcam\b|\bab\d{2,6}\b"),
    ("Santa Cruz", r"santa[\s\-]*cruz|\bsc[\s\-]?\d{2,6}"),
    ("Cell Signaling Technology", r"cell\s*signal|\bCST\b"),
    ("Active Motif", r"active\s*motif"),
    ("Millipore", r"millipore|upstate|\bmerck\b|\bEMD\b"),
    ("Diagenode", r"diagenode"),
    ("Bethyl", r"bethyl|\bA30\d-\d{3}A\b"),
    ("Sigma-Aldrich", r"sigma|aldrich"),
    ("Thermo Fisher", r"thermo|invitrogen|pierce|life\s*tech"),
    ("Proteintech", r"proteintech|\b\d{4,6}-\d-AP\b"),
    ("R&D Systems", r"R\s*&\s*D|R and D systems"),
    ("Novus", r"\bnovus\b"),
    ("GeneTex", r"genetex|\bGTX\d+"),
    ("BD Biosciences", r"\bBD\b|becton"),
    ("BioLegend", r"biolegend"),
    ("Atlas Antibodies", r"atlas antibod|\bHPA\d{6}\b"),
    ("Wako", r"\bwako\b|fujifilm"),
    ("Roche", r"\broche\b"),
    ("EpiCypher", r"epicypher"),
    ("PTM Biolabs", r"PTM[\s\-]*bio"),
    ("ENCODE", r"\bENCAB\d{3}[A-Z]{3}\b"),
    ("Covance", r"covance|\bMMS-\d{3}[A-Z]?\b|\bPRB-\d{3}[A-Z]?\b"),
]
VENDOR_RE = [(n, re.compile(p, re.I)) for n, p in VENDORS]
CATALOG = [  # vendor -> catalog regex (vendor-implying patterns listed first)
    ("RRID", re.compile(r"\bRRID\s*:?\s*(AB_\d{5,8})\b", re.I)),
    ("ENCODE", re.compile(r"\b(ENCAB\d{3}[A-Z]{3})\b")),
    ("Covance", re.compile(r"\b(MMS-\d{3}[A-Z]?|PRB-\d{3}[A-Z]?)\b")),
    ("Abcam", re.compile(r"\b(ab\d{2,6})\b", re.I)),
    ("Santa Cruz", re.compile(r"\b(?:sc|scbt)[\s\-]?(\d{2,6}(?:-?X)?)\b", re.I)),
    ("Santa Cruz", re.compile(r"\b([A-Z]{1,2}-\d{2,3})\b")),  # legacy product names (N-20, C-20, HC-20, H-300)
    ("Bethyl", re.compile(r"\b(A30\d-\d{3}A)\b")),
    ("Proteintech", re.compile(r"\b(\d{4,6}-\d-AP)\b")),
    ("Atlas Antibodies", re.compile(r"\b(HPA\d{6})\b")),
    ("GeneTex", re.compile(r"\b(GTX\d+)\b")),
    ("Millipore", re.compile(r"\b(\d{2}-\d{3,4}|MABE?\d{3,5}|ABE\d{3,5}|CS\d{6})\b")),
    ("Diagenode", re.compile(r"\b(C\d{8}(?:-\d+)?|pAb-\d{3}-\d{3}|CS-\d{3}-\d{3})\b")),
    ("Sigma-Aldrich", re.compile(r"\b(F\d{4}|A\d{4}|SAB\d{7}|HPA\d{6}|M\d{4})\b")),
    ("Active Motif", re.compile(r"(?:#|cat\.?\s*(?:no\.?|#)?\s*|\b)(39\d{3}|61\d{3}|91\d{3}|10\d{4})\b")),
    ("Cell Signaling Technology", re.compile(r"(?:#|cat\.?\s*(?:no\.?|#)?\s*|\b)(\d{4,5}S?)\b")),
    ("Thermo Fisher", re.compile(r"\b(PA\d-\d{3,6}|MA\d-\d{3,6})\b")),
    ("Novus", re.compile(r"\b(NB\d{2,3}-\d{3,6})\b")),
    ("Roche", re.compile(r"\b(\d{11})\b")),
]
IMPLIES_VENDOR = {"RRID", "ENCODE", "Abcam", "Bethyl", "Proteintech", "Atlas Antibodies", "GeneTex", "Covance"}
CST_CLONE = re.compile(r"\b([A-Z]\d{1,2}[A-Z]\d{1,2})\b")  # CST rabbit mAb clone IDs, e.g. D22F2, C29F4
NA_TXT = re.compile(r"^\s*(n/?a|none|-|not applicable|unknown|not available|\.)\s*$", re.I)
CLONES = re.compile(r"\b(8WG16|4H8|3E10|3E8|H5|H14|DO-1|DO-7|9E10|12CA5|3F10|16B12|M2)\b")
CLONE_EXPL = re.compile(r"\bclone[\s:#]*([A-Za-z0-9][A-Za-z0-9\-\.]{1,15})", re.I)
HOST = re.compile(r"\b(mouse|rabbit|goat|rat|sheep|chicken|guinea[\s\-]?pig|donkey|llama|hamster)\b", re.I)
TAGS = [("FLAG", re.compile(r"\bflag\b|\bF1804\b|\bF3165\b|\bM2\b", re.I)),
        ("HA", re.compile(r"\bHA\b|12CA5|3F10|hemagglutinin", re.I)),
        ("V5", re.compile(r"\bV5\b", re.I)),
        ("GFP", re.compile(r"\b(e?GFP|YFP|venus|mNeonGreen)\b", re.I)),
        ("Myc-tag", re.compile(r"\bmyc[\s\-]*tag|\bc-?myc\s*epitope|\bmyc\b.*\b9E10\b", re.I)),
        ("other", re.compile(r"\b(T7[\s\-]*tag|His[\s\-]*tag|6xHis|Strep[\s\-]*tag|TY1|HALO[\s\-]*tag|biotin|Avi[\s\-]*tag|"
                             r"BioTag|BirA)\b", re.I))]
CONTROL_TXT = re.compile(r"^\s*((normal\s+)?(rabbit|mouse|goat|rat)?\s*IgG|IgG|no antibody|mock|input)\s*$", re.I)


def parse_antibody(attrs, antigen_raw):
    """attrs: list of (key, value). Uses keys containing 'antibod' except 'control antibody'."""
    ab = [(k, v) for k, v in attrs if "antibod" in k.lower() and "control" not in k.lower()
          and "secondary" not in k.lower() and v.strip() and not NA_TXT.match(v)]
    out = dict(antibody_raw=MISSING, antibody_source_field=MISSING, antibody_target_raw=MISSING,
               antibody_vendor=MISSING, antibody_catalog=MISSING, antibody_clone=MISSING, antibody_host=MISSING,
               antibody_type="unknown", antibody_id=MISSING, antibody_label=MISSING, epitope_tag="unknown",
               antibody_status="not_reported")
    if not ab:
        return out
    desc = [v for k, v in ab if "targetdescription" not in k.replace(" ", "").lower()
            and "target description" not in k.lower()]
    tgt = [v for k, v in ab if "target" in k.lower()]
    text = " | ".join(desc) if desc else ""
    out["antibody_raw"] = clean(" | ".join(f"{k}={v}" for k, v in ab))[:1000]
    out["antibody_source_field"] = ";".join(sorted({k for k, _ in ab}))
    if tgt:
        out["antibody_target_raw"] = clean(tgt[0])[:200]
    if not text.strip():
        out["antibody_status"] = "description_only" if tgt else "not_reported"
        return out
    vend = [n for n, rx in VENDOR_RE if rx.search(text)]
    cats = []
    for n, rx in CATALOG:
        if n in IMPLIES_VENDOR or n in vend or (n == "Santa Cruz" and re.search(r"\b(sc|scbt)[\s\-]?\d", text, re.I)):
            for c in rx.findall(text):
                c = re.sub(r"\s+", "", c)
                if n == "Santa Cruz" and c[0].isdigit():
                    c = "sc-" + c
                cats.append((n, c))
    cats = list(dict.fromkeys(cats))
    clone = CLONE_EXPL.search(text) or CLONES.search(text) or \
        (CST_CLONE.search(text) if "Cell Signaling Technology" in vend else None)
    host = HOST.search(text)
    out["antibody_host"] = host.group(1).lower() if host else MISSING
    low = text.lower()
    out["antibody_type"] = ("monoclonal" if re.search(r"monoclonal|\bmab\b|\bclone\b", low) or clone else
                            "polyclonal" if re.search(r"polyclonal|\bpab\b", low) else "unknown")
    tag = next((t for t, rx in TAGS if rx.search(text)), None)
    out["epitope_tag"] = tag or ("unknown" if antigen_raw in ("Epitope tags", "GFP") else "none")
    if clone:
        out["antibody_clone"] = clone.group(1)
    if vend:
        out["antibody_vendor"] = vend[0]
    if len({c for _, c in cats}) > 1 and len({n for n, _ in cats}) > 1:
        out["antibody_status"] = "ambiguous"
        out["antibody_catalog"] = ";".join(c for _, c in cats)[:200]
    elif cats:
        n, c = next((x for x in cats if x[0] != "RRID"), cats[0]) if len({c for _, c in cats}) == 1 else cats[0]
        rrid = next((c2 for n2, c2 in cats if n2 == "RRID"), None)
        out.update(antibody_vendor=n if n != "RRID" else out["antibody_vendor"], antibody_catalog=c,
                   antibody_id=f"RRID:{rrid}" if rrid else (c if n == "ENCODE" else f"{n}:{c}"),
                   antibody_status="catalog_resolved")
    elif clone:
        out["antibody_status"] = "clone_resolved"
    else:
        out["antibody_status"] = "description_only"
    out["antibody_label"] = (f"{out['antibody_vendor']} {out['antibody_catalog']}" if out["antibody_status"] ==
                             "catalog_resolved" else clean(text)[:60])
    out["_control_like"] = bool(CONTROL_TXT.match(text))
    return out


# ---------------------------------------------------------------- context (§5.3)

UNTREATED = re.compile(r"^\s*(none|no|untreated|no treatment|non[\s\-]?treated|control|ctrl|mock|vehicle|dmso|"
                       r"etoh|ethanol|pbs|unstimulated|n/?a|-|0|nothing|normal|wt|wild[\s\-]?type)\s*$|"
                       r"\b(vehicle|dmso|non[\s\-]?targeting|scrambl\w*|mock|untreated|unstimulated|no treatment)\b|"
                       r"^\s*(ntc|control)\b", re.I)
TREAT_KEYS = ("treatment", "agent", "drug", "stimulation", "treatment description", "compound", "treated with")
PERTURB = [("knockdown", r"knock[\s\-]*down|\bsi[\s\-]?rna|\bsh[\s\-]?rna|\bkd\b"),
           ("knockout", r"knock[\s\-]*out|\bko\b|crispr|-/-|null"),
           ("overexpression", r"over[\s\-]*express|\boe\b|transfect|transduc|induc(ed|ible) expression"),
           ("degron", r"degron|dTAG|\bAID\b|auxin"),
           ("stimulation", r"stimulat|\bLPS\b|\bTNF|\bIFN|estradiol|\bE2\b|dexamethasone|\bDex\b|androgen|DHT|R1881|"
                           r"insulin|forskolin|PMA|ionomycin|heat shock|hypoxia|estrogen|hormone|agonist|ligand"),
           ("drug", r"inhibitor|\bnM\b|\buM\b|\bµM\b|mg/ml|treated with|\bJQ1\b|tamoxifen|doxycycline|\bdox\b")]
PERTURB_RE = [(n, re.compile(p, re.I)) for n, p in PERTURB]
PRIMARY_CELL = re.compile(r"\b(T[\s\-]?cells?|B[\s\-]?cells?|monocytes?|macrophages?|neutrophils?|PBMC|"
                          r"peripheral blood|CD\d+\+?|NK cells?|dendritic|erythroblasts?|HSPC|CD34|primary)\b", re.I)


def parse_context(desc, attrs, cell_type_class, cell_type):
    d = dict(x.split("=", 1) for x in desc.split("|") if "=" in x) if "=" in desc and not desc.startswith("MeSH") else {}
    a = {}
    for k, v in attrs:
        a.setdefault(k.lower().strip(), v.strip())
    blob = " ".join([cell_type, desc] + [f"{k} {v}" for k, v in attrs]).lower()
    tissue = d.get("Primary Tissue") or a.get("tissue") or MISSING
    disease = d.get("Tissue Diagnosis") or a.get("disease") or a.get("disease state") or a.get("health state") or \
        a.get("tumor type") or MISSING
    if "organoid" in blob:
        bt = "organoid"
    elif "Primary Tissue" in d or (a.get("cell line", "").strip() and not UNTREATED.match(a["cell line"])):
        bt = "cell_line"
    elif re.search(r"(h?ipscs?|h?escs?|ips|es[\s\-]?cells?|stem[\s\-]?cells?)[\s\-]*derived|differentiat", blob):
        bt = "stem_cell_derived"
    elif a.get("tissue") and not a.get("cell line"):
        bt = "primary_tissue"
    elif PRIMARY_CELL.search(cell_type) or PRIMARY_CELL.search(a.get("cell type", "")):
        bt = "primary_cells"
    else:
        bt = "unknown"
    tv = [v for k, v in attrs if k.lower().strip() in TREAT_KEYS and v.strip()]
    if not tv:
        ts = "not_reported"
    elif all(UNTREATED.match(v) for v in tv):
        ts = "untreated"
    elif any(UNTREATED.match(v) for v in tv):
        ts = "ambiguous"
    else:
        ts = "treated"
    ptxt = " ".join(tv + [v for k, v in attrs if k.lower().strip() in ("genotype", "genotype/variation", "sirna",
                                                                       "shrna", "condition", "perturbation")])
    pert = [n for n, rx in PERTURB_RE if rx.search(ptxt)] if ptxt and not UNTREATED.match(ptxt) else []
    geno = a.get("genotype") or a.get("genotype/variation") or MISSING
    return dict(tissue=clean(tissue)[:100], biosample_type=bt, disease=clean(disease)[:100], treatment_status=ts,
                perturbation=";".join(pert) or MISSING, genotype=clean(geno)[:100])


def clean(s):
    return re.sub(r"[\t\r\n]+", " ", str(s)).strip() or MISSING
