#!/usr/bin/python3
"""One-shot 8-peak PRINT integration check; execution remains separately gated."""
from __future__ import print_function

import hashlib
import glob
import importlib.util
import json
import os
import resource
import signal
import socket
import subprocess
import sys
import tempfile
import time


RUN_ID = "BG_K562_PRINT_STREAM_VALIDATION_20261020_V4"
SCRIPT_DIR = "/home/zz950/PMA_fetch/pma_print_stream_validation_code_20261020_v4"
ROOT = "/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v4"
OUTPUT_DIR = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v4"
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
BASE_SUPERVISOR_SHA256 = "f5fcee3a1d768758042b5edae0e1265fb5be4a518cf622cf5b297415819ac710"
RUNNER_SHA256 = "e3be118cda14f028b458a111e38be0b260ef1f54b368e5d7890a11bb31ec3caa"
HELPER_SHA256 = "d2f6a30b9c712bc22d8fd70d945bd84c85eb5ed0643386050930f21af21fdaab"
OUTER_STOP_REQUESTED = []


def request_outer_stop(signum, frame):
    OUTER_STOP_REQUESTED.append(signum)


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


def active_groups(registry_path):
    active = {}
    try:
        with open(registry_path, "r") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                    pgid = int(event["pgid"])
                    if event["action"] == "register":
                        active[pgid] = event.get("role", "unknown")
                    elif event["action"] == "unregister":
                        active.pop(pgid, None)
                except (ValueError, TypeError, KeyError):
                    continue
    except FileNotFoundError:
        pass
    return active


def group_exists(pgid):
    if os.path.isdir("/proc"):
        found = False
        scan_error = False
        for stat_path in glob.glob("/proc/[0-9]*/stat"):
            pid = int(stat_path.split("/")[2])
            try:
                with open(stat_path, "r") as handle:
                    raw = handle.read()
                close = raw.rfind(")")
                fields = raw[close + 2:].split()
                if close < 0 or len(fields) < 4:
                    scan_error = True
                    continue
                if int(fields[2]) == pgid and fields[0] != "Z":
                    found = True
            except (IOError, OSError, ValueError, IndexError):
                if os.path.exists("/proc/%d" % pid):
                    scan_error = True
        return found or scan_error
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_registered_groups(groups, registry_path, worker_pgid, grace_seconds=60,
                           worker_process=None):
    """TERM known groups together, then KILL survivors within a fixed budget."""
    signaled = set()
    signal_errors = {}

    def refresh_and_term():
        candidates = dict(groups)
        candidates.update(active_groups(registry_path))
        candidates[worker_pgid] = "smoke_worker"
        for pgid in candidates:
            if pgid in signaled or not group_exists(pgid):
                continue
            try:
                os.killpg(pgid, signal.SIGTERM)
                signaled.add(pgid)
            except ProcessLookupError:
                pass
            except OSError as error:
                signal_errors[pgid] = "%s:%s" % (type(error).__name__, error.errno)
        return candidates

    deadline = time.monotonic() + grace_seconds
    candidates = refresh_and_term()
    while time.monotonic() < deadline:
        if worker_process is not None:
            worker_process.poll()
        candidates = refresh_and_term()
        alive = [pgid for pgid in candidates if group_exists(pgid)]
        if not alive:
            return []
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
    candidates = refresh_and_term()
    for pgid in candidates:
        if group_exists(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                signal_errors[pgid] = "%s:%s" % (type(error).__name__, error.errno)
    reap_deadline = time.monotonic() + 5
    while time.monotonic() < reap_deadline:
        if worker_process is not None:
            worker_process.poll()
        alive = [pgid for pgid in candidates if group_exists(pgid)]
        if not alive:
            return []
        time.sleep(0.1)
    return [{"pgid": pgid, "role": candidates.get(pgid, "unknown"),
             "still_present_after_sigkill": group_exists(pgid),
             "signal_error": signal_errors.get(pgid)}
            for pgid in candidates if group_exists(pgid) or pgid in signal_errors]


def run_outer_worker(command, deadline, registry_path, cleanup_grace_seconds=60):
    """Data-bearing work runs in a session; parent performs no input I/O."""
    with tempfile.TemporaryFile(mode="w+b", dir="/tmp") as stdout, \
            tempfile.TemporaryFile(mode="w+b", dir="/tmp") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        worker_pgid = process.pid
        while (process.poll() is None and time.monotonic() < deadline
               and not OUTER_STOP_REQUESTED):
            time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        timed_out = time.monotonic() >= deadline
        interrupted = bool(OUTER_STOP_REQUESTED)
        groups = active_groups(registry_path)
        live_groups = {pgid: role for pgid, role in groups.items() if group_exists(pgid)}
        worker_group_live = group_exists(worker_pgid)
        leaked_groups = bool(live_groups or worker_group_live)
        survivors = []
        if timed_out or interrupted or leaked_groups:
            survivors = stop_registered_groups(groups, registry_path, worker_pgid,
                                               grace_seconds=cleanup_grace_seconds,
                                               worker_process=process)
        try:
            return_code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            survivors.append({"pgid": worker_pgid, "role": "smoke_worker",
                              "still_present_after_sigkill": True,
                              "d_state_caveat": "SIGKILL may not immediately clear uninterruptible kernel tasks"})
            return_code = 124
        stdout.seek(0)
        stderr.seek(0)
        return (return_code, stdout.read().decode("utf-8", "replace"),
                stderr.read().decode("utf-8", "replace"), timed_out, survivors,
                leaked_groups, interrupted)


def worker_main(deadline, registry_path):
    started = time.monotonic()
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
    module.PROCESS_GROUP_REGISTRY = registry_path
    module.RUN_DEADLINE_MONOTONIC = deadline
    module.RUN_ID = RUN_ID
    module.ROOT = ROOT
    module.OUTPUT_DIR = OUTPUT_DIR
    module.BED = smoke_bed
    module.BED_SHA256 = sha256(smoke_bed)
    module.RUNNER = runner
    module.RUNNER_HELPER = helper
    module.RUNNER_SHA256 = RUNNER_SHA256
    module.RUNNER_HELPER_SHA256 = HELPER_SHA256
    module.CPUS = sorted(os.sched_getaffinity(0))[:16]
    if len(module.CPUS) != 16:
        raise RuntimeError("sixteen CPU workers are not available")
    module.RSS_SOFT_STOP_KB = RSS_SOFT_STOP_KB
    preparation_seconds = time.monotonic() - started
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
                      "workers": 16,
                      "smoke_mode": "direct-per-region comparison; 8 frozen peak rows; scoring chunks 3/3/2"})
        return cpus, hashes, facts

    module.preflight = smoke_preflight
    os.environ["PRINT_DIRECT_COMPARE"] = "1"
    for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                     "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[variable] = "1"
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
        completion_path = prefix + ".complete.tsv"
        if not os.path.isfile(completion_path):
            sys.stderr.write("FAIL_CLOSED: atomic completion manifest missing\n")
            return 3
        with open(completion_path, "r") as handle:
            completion_lines = [line.rstrip("\n").split("\t") for line in handle]
        if len(completion_lines) != 3 or completion_lines[0][0] != "radius" or \
                [row[0] for row in completion_lines[1:]] != ["10", "20"]:
            sys.stderr.write("FAIL_CLOSED: completion manifest does not cover r10/r20\n")
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
                       "workers": 16, "total_wall_cap_seconds": MAX_TOTAL_WALL_SECONDS,
                       "observed_total_wall_seconds": total_wall,
                       "rss_soft_stop_gib": 40,
                       "rss_soft_stop_is_hard_task_limit": False,
                       "selection_summary": os.path.join(ROOT, "selection_summary.json"),
                       "direct_comparison_report": report},
                      handle, indent=2, sort_keys=True)
            handle.write("\n")
    return status


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        return worker_main(float(sys.argv[2]), sys.argv[3])
    signal.signal(signal.SIGINT, request_outer_stop)
    signal.signal(signal.SIGTERM, request_outer_stop)
    started = time.monotonic()
    deadline = started + MAX_TOTAL_WALL_SECONDS
    registry_dir = tempfile.mkdtemp(prefix="pma_print_smoke_watchdog_", dir="/tmp")
    registry_path = os.path.join(registry_dir, "process_groups.jsonl")
    with open(registry_path, "x"):
        pass
    command = [sys.executable, os.path.abspath(__file__), "--worker",
               repr(deadline), registry_path]
    return_code, stdout, stderr, timed_out, survivors, leaked_groups, interrupted = run_outer_worker(
        command, deadline, registry_path)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    if timed_out:
        sys.stderr.write("FAIL_CLOSED: independent 30-minute supervisor deadline expired; "
                         "registered groups received TERM then bounded KILL; SIGKILL cannot instantly "
                         "clear uninterruptible kernel D-state tasks; survivors=%s\n" %
                         json.dumps(survivors, sort_keys=True))
        return 124
    if interrupted:
        sys.stderr.write("FAIL_CLOSED: external stop requested; registered process groups were cleaned "
                         "with bounded TERM/KILL; survivors=%s\n" %
                         json.dumps(survivors, sort_keys=True))
        return 124
    if leaked_groups:
        sys.stderr.write("FAIL_CLOSED: worker exited with registered process groups still active; "
                         "cleanup survivors=%s\n" % json.dumps(survivors, sort_keys=True))
        return 124
    return return_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        sys.stderr.write("FAIL_CLOSED: %s\n" % error)
        sys.exit(2)
