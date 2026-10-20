#!/usr/bin/env python3
"""One-shot 64-peak PRINT speed sample, supervised by the pinned full-run monitor."""
from __future__ import print_function

import hashlib
import importlib.util
import json
import os
import resource
import signal
import socket
import subprocess
import sys
import time


RUN_ID = "BG_K562_PRINT_PEAK_SPEED64_20261020_V2"
CODE_DIR = "/home/zz950/PMA_fetch/pma_print_peak_speed_code_20261020_v2"
ROOT = "/home/zz950/PMA_fetch/pma_print_peak_speed_rcapps3_20261020_v2"
OUTPUT_DIR = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_peak_speed_rcapps3_20261020_v2"
FROZEN_BED = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-19/encode_k562/ENCSR868FGK/ENCFF993BAP.bed.gz"
SELECTOR_NAME = "select_print_speed64.py"
RUNNER_NAME = "run_print.R"
HELPER_NAME = "print_variable_width.R"
BASE_NAME = "run_print_fullpeak_supervised.py"
OUTER_NAME = "run_print_integration_smoke_supervised.py"
SELECTOR_SHA256 = "105be1be89c94d466e46dccdee98402d74ec7dfba1781f1c7a91740342932b46"
RUNNER_SHA256 = "0c7c26f303f079a18d5f1f110faa2e516d631c8826dbd5e5517fc26d4aff22bb"
HELPER_SHA256 = "5f5da1b9cf3179f40850792d26ecce6862ed8c3a5dfd82ad39fa8ab07d51d4ca"
BASE_SHA256 = "7d594c58de85c012cc3ff08d93c8c67252be65f9cd860497243bc9295ef0a234"
OUTER_SHA256 = "1b4c574e71a8d63c34c92c26810c822e627c4cd25cd78eb7cbc85e8996ca68ad"
GATE_PATH = "/home/zz950/PMA_fetch/pma_bg_gate_v2.sh"
GATE_SHA256 = "3776778b950be90cad124c04937eee422c81466154eccdadfe9e57d58224253c"
MAX_WALL_SECONDS = 30 * 60
RSS_SOFT_STOP_KB = 40 * 1024 * 1024
WORKERS = 2


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(path):
    spec = importlib.util.spec_from_file_location("pma_print_fullpeak_supervisor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_hash(path, expected, label):
    if not os.path.isfile(path) or sha256(path) != expected:
        raise RuntimeError("%s missing or SHA-256 mismatch" % label)


def worker_main(deadline, registry_path):
    started = time.monotonic()
    if socket.gethostname().split(".")[0] not in ("rcGPUs", "rcapps3") or os.uname()[4] != "x86_64":
        raise RuntimeError("must run only on the rcapps3/rcGPUs x86_64 host")
    expected_self = os.environ.get("PMA_PRINT_SPEED64_EXPECTED_SHA256", "")
    if len(expected_self) != 64 or sha256(os.path.abspath(__file__)) != expected_self:
        raise RuntimeError("reviewed wrapper SHA-256 missing or mismatched")
    if os.path.exists(ROOT) or os.path.exists(OUTPUT_DIR):
        raise RuntimeError("refusing to reuse existing run/output paths")
    os.makedirs(ROOT, mode=0o700, exist_ok=False)
    if os.path.dirname(registry_path) != ROOT:
        raise RuntimeError("process-group registry must be under the unique run root")
    with open(registry_path, "x"):
        pass
    for name, expected, label in ((SELECTOR_NAME, SELECTOR_SHA256, "selector"),
                                  (RUNNER_NAME, RUNNER_SHA256, "PRINT runner"),
                                  (HELPER_NAME, HELPER_SHA256, "variable-width helper"),
                                  (BASE_NAME, BASE_SHA256, "base supervisor"),
                                  (OUTER_NAME, OUTER_SHA256, "outer watchdog")):
        require_hash(os.path.join(CODE_DIR, name), expected, label)
    require_hash(GATE_PATH, GATE_SHA256, "immutable Argos gate")
    selector = os.path.join(CODE_DIR, SELECTOR_NAME)
    bed = os.path.join(ROOT, "k562_midpoint_quantile_64peaks.bed")
    row_map = os.path.join(ROOT, "k562_midpoint_quantile_64peaks.map.tsv")
    selection_started = time.monotonic()
    result = subprocess.run([sys.executable, selector, FROZEN_BED, bed, row_map],
                            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True,
                            timeout=max(1, deadline - time.monotonic()))
    selection_seconds = time.monotonic() - selection_started
    selection = json.loads(result.stdout.strip().splitlines()[-1])
    if selection.get("selected_rows") != 64 or selection.get("source_rows") != 159628:
        raise RuntimeError("selector did not produce the frozen 64-of-159628 sample")
    with open(os.path.join(ROOT, "selection_summary.json"), "x") as handle:
        json.dump({**selection, "selection_seconds": selection_seconds,
                   "selector_sha256": sha256(selector)}, handle, indent=2, sort_keys=True)
        handle.write("\n")

    base = load_module(os.path.join(CODE_DIR, BASE_NAME))
    base.RUN_ID = RUN_ID
    base.ROOT = ROOT
    base.OUTPUT_DIR = OUTPUT_DIR
    base.BED = bed
    base.BED_SHA256 = selection["selected_bed_sha256"]
    base.RUNNER = os.path.join(CODE_DIR, RUNNER_NAME)
    base.RUNNER_HELPER = os.path.join(CODE_DIR, HELPER_NAME)
    base.RUNNER_SHA256 = RUNNER_SHA256
    base.RUNNER_HELPER_SHA256 = HELPER_SHA256
    base.PROCESS_GROUP_REGISTRY = registry_path
    base.CPUS = sorted(os.sched_getaffinity(0))[:WORKERS]
    if len(base.CPUS) != WORKERS:
        raise RuntimeError("two CPU workers are unavailable")
    base.RSS_SOFT_STOP_KB = RSS_SOFT_STOP_KB
    base.MAX_WALL_SECONDS = MAX_WALL_SECONDS
    base.RUN_DEADLINE_MONOTONIC = deadline
    original_preflight = base.preflight

    def preflight_with_sample_facts():
        cpus, hashes, facts = original_preflight()
        facts.update({"bounded_sample_wrapper_sha256": sha256(os.path.abspath(__file__)),
                      "selector_sha256": sha256(selector),
                      "selection_seconds": selection_seconds,
                      "selected_rows": 64, "source_rows": 159628,
                      "selection_method": "64 midpoint quantiles in frozen BED row order",
                      "bias_path": "production chromosome-wise bias strategy",
                      "workers": WORKERS, "radii_bp": [10, 20],
                      "caller_warning_mode": "options(warn=1); warning messages preserved on stderr"})
        return cpus, hashes, facts

    base.preflight = preflight_with_sample_facts
    os.environ["PRINT_DIRECT_COMPARE"] = "0"
    as_soft, as_hard = resource.getrlimit(resource.RLIMIT_AS)
    expected_limit = 44 * 1024 * 1024 * 1024
    if as_soft in (-1, resource.RLIM_INFINITY) or as_hard in (-1, resource.RLIM_INFINITY) or \
            as_soft > expected_limit or as_hard > expected_limit:
        raise RuntimeError("immutable gate per-process RLIMIT_AS <=44 GiB is not active")
    run_status = base.main()
    summary_path = os.path.join(ROOT, "summary.json")
    if os.path.isfile(summary_path):
        with open(summary_path, "r") as handle:
            summary = json.load(handle)
        summary["selection_seconds"] = selection_seconds
        summary["wrapper_wall_seconds"] = time.monotonic() - started
        summary["sample_summary_path"] = os.path.join(ROOT, "selection_summary.json")
        summary["caller_mode"] = "production chromosome-wise bias; PRINT_DIRECT_COMPARE=0"
        with open(summary_path, "w") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return run_status


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        return worker_main(float(sys.argv[2]), sys.argv[3])

    started = time.monotonic()
    deadline = started + MAX_WALL_SECONDS
    outer_path = os.path.join(CODE_DIR, OUTER_NAME)
    require_hash(outer_path, OUTER_SHA256, "outer watchdog")
    outer = load_module(outer_path)
    signal.signal(signal.SIGINT, outer.request_outer_stop)
    signal.signal(signal.SIGTERM, outer.request_outer_stop)
    registry_path = os.path.join(ROOT, "process_groups.jsonl")
    command = [sys.executable, os.path.abspath(__file__), "--worker",
               repr(deadline), registry_path]
    return_code, stdout, stderr, timed_out, survivors, leaked_groups, interrupted = \
        outer.run_outer_worker(command, deadline, registry_path, cleanup_grace_seconds=60)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    parent_wall_seconds = time.monotonic() - started
    if os.path.isdir(ROOT):
        summary = {"run_id": RUN_ID, "outer_supervisor_wall_seconds": parent_wall_seconds,
                   "worker_exit_code": return_code, "deadline_seconds": MAX_WALL_SECONDS,
                   "timed_out": timed_out, "interrupted": interrupted,
                   "worker_left_registered_groups": leaked_groups,
                   "cleanup_survivors": survivors,
                   "cleanup_wall_is_outside_execution_budget": True}
        with open(os.path.join(ROOT, "outer_supervisor_summary.json"), "x") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
    if timed_out or interrupted or leaked_groups:
        sys.stderr.write("FAIL_CLOSED: independent end-to-end supervisor stopped the worker; "
                         "registered process groups received bounded TERM/KILL cleanup; "
                         "SIGKILL cannot instantly clear uninterruptible kernel tasks; "
                         "survivors=%s\n" % json.dumps(survivors, sort_keys=True))
        return 124
    if parent_wall_seconds > MAX_WALL_SECONDS:
        sys.stderr.write("FAIL_CLOSED: observed end-to-end wall exceeded its budget\n")
        return 124
    return return_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        sys.stderr.write("FAIL_CLOSED: %s\n" % error)
        sys.exit(2)
