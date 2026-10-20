#!/usr/bin/python3
"""One-shot 8-peak PRINT integration check; execution remains separately gated."""
from __future__ import print_function

import hashlib
import importlib.util
import json
import os
import resource
import socket
import subprocess
import sys
import time


RUN_ID = "BG_K562_PRINT_INTEGRATION_SMOKE_20261020_V1"
SCRIPT_DIR = "/home/zz950/PMA_fetch/pma_print_integration_smoke_code_20261020_v1"
ROOT = "/home/zz950/PMA_fetch/pma_print_integration_smoke_rcapps3_20261020_v1"
OUTPUT_DIR = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_integration_smoke_rcapps3_20261020_v1"
FROZEN_BED = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-19/encode_k562/ENCSR868FGK/ENCFF993BAP.bed.gz"
SELECTOR_NAME = "select_print_integration_smoke.py"
RUNNER_NAME = "run_print.R"
HELPER_NAME = "print_variable_width.R"
BASE_SUPERVISOR_NAME = "run_print_fullpeak_supervised.py"
GATE_PATH = "/home/zz950/PMA_fetch/pma_bg_gate_v2.sh"
GATE_SHA256 = "3776778b950be90cad124c04937eee422c81466154eccdadfe9e57d58224253c"
MAX_TOTAL_WALL_SECONDS = 30 * 60
RSS_SOFT_STOP_KB = 40 * 1024 * 1024
SELECTOR_SHA256 = "7e2a67554e4d5c601cdb6c18a3758bb420520fa21d6324eff6f02d15c1dd5856"
BASE_SUPERVISOR_SHA256 = "34330aa103d9f15168fbacb4fbab5d278a6336a79ce0476a0c3ed2aa27606b33"
RUNNER_SHA256 = "44853e1a865bcdf86c87ca6fbabd0279d86d144b14953b1b0533c679eb5098f2"
HELPER_SHA256 = "fa2aaba9248a9a67621fe269210b7afd81920aaa3bf85cac443f0a2371865174"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def remaining_seconds(deadline_monotonic):
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("end-to-end PRINT smoke wall budget expired")
    return remaining


def load_supervisor(path):
    spec = importlib.util.spec_from_file_location("print_fullpeak_supervisor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    started = time.monotonic()
    deadline = started + MAX_TOTAL_WALL_SECONDS
    if socket.gethostname().split(".")[0] not in ("rcGPUs", "rcapps3"):
        raise RuntimeError("must run only on the rcapps3/rcGPUs x86_64 host")
    if os.uname()[4] != "x86_64":
        raise RuntimeError("the staged PRINT R runtime requires x86_64")
    as_soft, as_hard = resource.getrlimit(resource.RLIMIT_AS)
    max_as = 44 * 1024 * 1024 * 1024
    if as_soft in (-1, resource.RLIM_INFINITY) or as_hard in (-1, resource.RLIM_INFINITY) or \
            as_soft > max_as or as_hard > max_as:
        raise RuntimeError("immutable gate per-process RLIMIT_AS <=44 GiB is not active")
    expected_self_sha = os.environ.get("PRINT_SMOKE_EXPECTED_SHA256", "")
    if len(expected_self_sha) != 64 or sha256(os.path.abspath(__file__)) != expected_self_sha:
        raise RuntimeError("reviewed smoke-supervisor SHA-256 was not supplied or did not match")
    if os.path.exists(ROOT) or os.path.exists(OUTPUT_DIR):
        raise RuntimeError("smoke output/evidence path already exists; refusing reuse")
    remaining_seconds(deadline)
    os.makedirs(ROOT, mode=0o700, exist_ok=False)
    selector = os.path.join(SCRIPT_DIR, SELECTOR_NAME)
    runner = os.path.join(SCRIPT_DIR, RUNNER_NAME)
    helper = os.path.join(SCRIPT_DIR, HELPER_NAME)
    base_supervisor = os.path.join(SCRIPT_DIR, BASE_SUPERVISOR_NAME)
    for path, expected, label in ((selector, SELECTOR_SHA256, "selector"),
                                  (runner, RUNNER_SHA256, "runner"),
                                  (helper, HELPER_SHA256, "helper"),
                                  (base_supervisor, BASE_SUPERVISOR_SHA256, "base supervisor")):
        if not os.path.isfile(path) or sha256(path) != expected:
            raise RuntimeError("staged %s SHA-256 mismatch" % label)
    if not os.path.isfile(GATE_PATH) or sha256(GATE_PATH) != GATE_SHA256:
        raise RuntimeError("immutable Argos gate SHA-256 mismatch")
    smoke_bed = os.path.join(ROOT, "eight_frozen_peaks.bed")
    smoke_map = os.path.join(ROOT, "eight_frozen_peaks.map.tsv")
    selector_command = [sys.executable, selector, FROZEN_BED, smoke_bed, smoke_map]
    selection = subprocess.check_output(selector_command,
                                        stderr=subprocess.STDOUT,
                                        universal_newlines=True,
                                        timeout=remaining_seconds(deadline))
    selection_seconds = time.monotonic() - started
    selection_facts = json.loads(selection.strip().splitlines()[-1])
    if selection_facts.get("selected_rows") != 8 or selection_facts.get("source_bed_sha256") is None:
        raise RuntimeError("smoke selector did not produce the reviewed 8-row set")
    with open(os.path.join(ROOT, "selection_summary.json"), "x") as handle:
        json.dump({"selection_seconds": selection_seconds,
                   "selector_sha256": sha256(selector), **selection_facts},
                  handle, indent=2, sort_keys=True)
        handle.write("\n")
    remaining_seconds(deadline)

    module = load_supervisor(base_supervisor)
    module.RUN_ID = RUN_ID
    module.ROOT = ROOT
    module.OUTPUT_DIR = OUTPUT_DIR
    module.BED = smoke_bed
    module.BED_SHA256 = sha256(smoke_bed)
    module.RUNNER = runner
    module.RUNNER_HELPER = helper
    module.RUNNER_SHA256 = RUNNER_SHA256
    module.RUNNER_HELPER_SHA256 = HELPER_SHA256
    module.CPUS = sorted(os.sched_getaffinity(0))[:2]
    if len(module.CPUS) != 2:
        raise RuntimeError("two CPU workers are not available")
    module.RSS_SOFT_STOP_KB = RSS_SOFT_STOP_KB
    preparation_seconds = time.monotonic() - started
    module.RUN_DEADLINE_MONOTONIC = deadline
    module.MAX_WALL_SECONDS = MAX_TOTAL_WALL_SECONDS
    original_preflight = module.preflight

    def smoke_preflight():
        cpus, hashes, facts = original_preflight()
        facts.update({"smoke_supervisor_sha256": sha256(os.path.abspath(__file__)),
                      "selector_sha256": sha256(selector),
                      "source_full_peak_bed_sha256": selection_facts["source_bed_sha256"],
                      "selected_smoke_bed_sha256": sha256(smoke_bed),
                      "rlimit_as_soft_bytes": as_soft,
                      "rlimit_as_hard_bytes": as_hard,
                      "selection_seconds": selection_seconds,
                      "setup_seconds_before_analysis": preparation_seconds,
                      "overall_deadline_monotonic_seconds_remaining": remaining_seconds(deadline),
                      "smoke_mode": "direct-per-region comparison; 8 frozen peak rows"})
        return cpus, hashes, facts

    module.preflight = smoke_preflight
    os.environ["PRINT_DIRECT_COMPARE"] = "1"
    sys.argv = [os.path.abspath(__file__)]
    remaining_seconds(deadline)
    status = module.main()
    remaining_seconds(deadline)
    prefix = os.path.join(OUTPUT_DIR, "print")
    report = prefix + ".direct-comparison.tsv"
    if status == 0:
        if not os.path.isfile(report):
            sys.stderr.write("FAIL_CLOSED: direct comparison report missing\n")
            return 3
        with open(report, "r") as handle:
            rows = [line for line in handle if line.strip()]
        if len(rows) != 17:
            sys.stderr.write("FAIL_CLOSED: expected header plus 16 direct comparisons\n")
            return 3
        with open(os.path.join(ROOT, "smoke_completion.json"), "x") as handle:
            total_wall = time.monotonic() - started
            remaining_seconds(deadline)
            json.dump({"status": "PASS", "direct_comparisons": 16,
                       "radii": [10, 20], "regions": 8,
                       "workers": 2, "total_wall_cap_seconds": MAX_TOTAL_WALL_SECONDS,
                       "observed_total_wall_seconds": total_wall,
                       "rss_soft_stop_gib": 40,
                       "rss_soft_stop_is_hard_task_limit": False,
                       "selection_summary": os.path.join(ROOT, "selection_summary.json"),
                       "direct_comparison_report": report},
                      handle, indent=2, sort_keys=True)
            handle.write("\n")
    return status


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        sys.stderr.write("FAIL_CLOSED: %s\n" % error)
        sys.exit(2)
