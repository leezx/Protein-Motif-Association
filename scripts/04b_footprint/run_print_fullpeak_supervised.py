#!/usr/bin/python3
"""One-shot, fixed-input PRINT run with an aggregate-PSS process-group watchdog."""
from __future__ import print_function

import glob
import gzip
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time


RUN_ID = "BG_K562_PRINT_FULLPEAK_20261020_V1"
RUNNER_SHA256 = "cae788b22dfb8ffc6006bae168b356909b3082036faa4a73e853c496ce717abf"
BED_SHA256 = "c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945"
FRAGS_SHA256 = "238367780a1b7a2a24595a4259bdbe91cb8be439c2e5fda210831ad60d77544f"
BIAS_H5_SHA256 = "574140487a0a829c7a59735e0e7a64a3f3a227a7e5ceb8ea5f355f7cc3289402"
MODEL_SHA256 = {
    10: "c0cd01806684784abc0cb6894e6cfcd0234704f88baf3045121a2b6e07737414",
    20: "1413478ee5dfef1655a419adf67ef18b503d7bcd4c82273c4c5c0f485cf2d0b3",
}
ROOT = "/home/zz950/PMA_fetch/pma_print_fullpeak_rcapps3_20261020_v1"
OUTPUT_DIR = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_fullpeak_rcapps3_20261020_v1"
PRINT_REPO = "/home/zz950/softwares/src/PRINT"
PRINT_REPO_COMMIT = "8dad7317c3a640454a191dba2acd138e6edc54ac"
PRINT_MODULE_SHA256 = {
    "utils.R": "8c20776317dd5a9207aeebb9dd084f9e4f0d5d80c1056f599c411fe696ecc8b7",
    "getCounts.R": "2f54f1c2c6a8cd410ed102cc934679f14c977ef002b8c1abf50c12018212d495",
    "getBias.R": "455b6ac5a33807d558399679d9947d29561d00fc7a7a7ffa2b8cc948e8f04615",
    "getFootprints.R": "7944dfa194cdf1eeda3cdfa821dab7df45cf59d7aa36d74ae206f77fb7e0babd",
}
SHARED = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/print_shared"
BED = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-19/encode_k562/ENCSR868FGK/ENCFF993BAP.bed.gz"
FRAGS = "/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/frags/k562_speed.frags.tsv.gz"
RUNNER = os.path.join(ROOT, "run_print.R")
RSCRIPT = "/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript"
RLIBS = ":".join(("/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib",
                   "/home/zz950/softwares/R_lib_tracebind",
                   "/home/zz950/softwares/R_lib_4"))
CPUS = list(range(16))
PSS_LIMIT_KB = 100 * 1024 * 1024
MAX_WALL_SECONDS = 24 * 60 * 60
SAMPLE_SECONDS = 2


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def require_file(path):
    if not os.path.isfile(path) or not os.access(path, os.R_OK):
        raise RuntimeError("required readable file missing: " + path)


def line_count(path):
    opener = gzip.open if path.endswith(".gz") else open
    count = 0
    with opener(path, "rb") as handle:
        for _ in handle:
            count += 1
    return count


def group_members(pgid):
    result = []
    for stat_path in glob.glob("/proc/[0-9]*/stat"):
        try:
            with open(stat_path, "r") as handle:
                raw = handle.read()
            close = raw.rfind(")")
            fields = raw[close + 2:].split()
            # fields begin with state (proc stat field 3); pgrp is field 5.
            if int(fields[2]) == pgid:
                result.append((int(stat_path.split("/")[2]), fields[0]))
        except (IOError, OSError, ValueError, IndexError):
            continue
    return result


def group_pss(pgid):
    members = group_members(pgid)
    total = 0
    failures = []
    for pid, state in members:
        if state == "Z":
            continue
        try:
            with open("/proc/%d/smaps_rollup" % pid, "r") as handle:
                pss = None
                for line in handle:
                    if line.startswith("Pss:"):
                        pss = int(line.split()[1])
                        break
            if pss is None:
                failures.append(pid)
            else:
                total += pss
        except (IOError, OSError, ValueError):
            # A process that vanished between the /proc scans is a harmless race.
            if os.path.exists("/proc/%d" % pid):
                failures.append(pid)
    return members, total, failures


def terminate_group(pgid, log, reason):
    log.write(json.dumps({"event": "terminate", "reason": reason,
                          "time_epoch": time.time(), "pgid": pgid}) + "\n")
    log.flush()
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 60
    while time.time() < deadline:
        members = group_members(pgid)
        if not members or all(state == "Z" for _, state in members):
            return
        time.sleep(1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def preflight():
    if socket.gethostname().split(".")[0] not in ("rcGPUs", "rcapps3"):
        raise RuntimeError("must run only on the rcapps3/rcGPUs x86_64 host")
    if os.uname()[4] != "x86_64":
        raise RuntimeError("the prepared R runtime requires x86_64")
    allowed = sorted(os.sched_getaffinity(0))
    if len(allowed) < len(CPUS):
        raise RuntimeError("fewer than 16 CPUs are available to this process")
    with open("/proc/meminfo", "r") as handle:
        mem_available = [line for line in handle if line.startswith("MemAvailable:")]
    if not mem_available or int(mem_available[0].split()[1]) < 256 * 1024 * 1024:
        raise RuntimeError("less than 256 GiB MemAvailable; refusing to start")
    require_file(BED)
    require_file(FRAGS)
    require_file(RUNNER)
    require_file(RSCRIPT)
    require_file(os.path.join(SHARED, "precomputedTn5Bias", "hg38Tn5Bias.h5"))
    for radius in (10, 20):
        require_file(os.path.join(SHARED, "dispModel", "dispersionModel%dbp.rds" % radius))
    if os.path.exists(OUTPUT_DIR):
        raise RuntimeError("refusing to reuse output directory: " + OUTPUT_DIR)
    if sha256(BED) != BED_SHA256:
        raise RuntimeError("frozen peak BED SHA-256 mismatch")
    if sha256(RUNNER) != RUNNER_SHA256:
        raise RuntimeError("reviewed run_print.R SHA-256 mismatch")
    commit = subprocess.check_output(["git", "-C", PRINT_REPO, "rev-parse", "HEAD"],
                                     universal_newlines=True).strip()
    dirty = subprocess.check_output(["git", "-C", PRINT_REPO, "status", "--porcelain"],
                                    universal_newlines=True)
    if commit != PRINT_REPO_COMMIT or dirty.strip():
        raise RuntimeError("PRINT source checkout is not the reviewed clean commit")
    module_hashes = {}
    for filename, expected in PRINT_MODULE_SHA256.items():
        module_path = os.path.join(PRINT_REPO, "code", filename)
        require_file(module_path)
        module_hashes[filename] = sha256(module_path)
        if module_hashes[filename] != expected:
            raise RuntimeError("PRINT module SHA-256 mismatch: " + filename)
    fragment_hash = sha256(FRAGS)
    bias_path = os.path.join(SHARED, "precomputedTn5Bias", "hg38Tn5Bias.h5")
    bias_hash = sha256(bias_path)
    model_hashes = {str(r): sha256(os.path.join(SHARED, "dispModel", "dispersionModel%dbp.rds" % r)) for r in (10, 20)}
    if fragment_hash != FRAGS_SHA256:
        raise RuntimeError("frozen fragment file SHA-256 mismatch")
    if bias_hash != BIAS_H5_SHA256:
        raise RuntimeError("frozen hg38 bias model SHA-256 mismatch")
    for radius in (10, 20):
        if model_hashes[str(radius)] != MODEL_SHA256[radius]:
            raise RuntimeError("frozen dispersion model SHA-256 mismatch at radius %d" % radius)
    frozen_hashes = {"bed_sha256": BED_SHA256, "fragments_sha256": fragment_hash,
                     "runner_sha256": sha256(RUNNER),
                     "print_repo_commit": commit, "print_module_sha256": module_hashes,
                     "bias_h5_sha256": bias_hash,
                     "dispersion_model_sha256": model_hashes}
    env = os.environ.copy()
    env["R_LIBS"] = RLIBS
    probe = [RSCRIPT, "-e", "stopifnot(requireNamespace('cladoRcpp',quietly=TRUE),requireNamespace('GenomicRanges',quietly=TRUE),requireNamespace('data.table',quietly=TRUE),requireNamespace('rhdf5',quietly=TRUE))"]
    subprocess.check_call(probe, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    preflight_facts = {"mem_available_kb": int(mem_available[0].split()[1]),
                       "load_average": list(os.getloadavg()),
                       "allowed_cpu_ids": allowed}
    preflight_facts["r_version"] = subprocess.check_output(
        [RSCRIPT, "--version"], stderr=subprocess.STDOUT,
        universal_newlines=True).strip()
    preflight_facts["supervisor_sha256"] = sha256(os.path.abspath(__file__))
    return allowed[:len(CPUS)], frozen_hashes, preflight_facts


def main():
    os.makedirs(ROOT, mode=0o700, exist_ok=True)
    log_path = os.path.join(ROOT, "watchdog.jsonl")
    with open(log_path, "a") as log:
        started = time.time()
        try:
            cpus, frozen_hashes, preflight_facts = preflight()
            preflight_seconds = time.time() - started
            os.makedirs(OUTPUT_DIR, mode=0o700, exist_ok=False)
            prefix = os.path.join(OUTPUT_DIR, "print")
            environment = os.environ.copy()
            environment.update({"R_LIBS": RLIBS, "OMP_NUM_THREADS": "1",
                                "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                                "NUMEXPR_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": ""})
            command = ["/usr/bin/time", "-v", "/usr/bin/taskset", "-c",
                       ",".join(str(cpu) for cpu in cpus), RSCRIPT, RUNNER,
                       PRINT_REPO, SHARED, BED, FRAGS, prefix, "16", "10,20"]
            os.makedirs(os.path.join(ROOT, "runlogs"), mode=0o700, exist_ok=True)
            stdout_path = os.path.join(ROOT, "runlogs", "caller.stdout")
            time_path = os.path.join(ROOT, "runlogs", "gnu_time.stderr")
            with open(stdout_path, "wb") as stdout, open(time_path, "wb") as stderr:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                           env=environment, start_new_session=True)
                caller_started = time.time()
                pgid = process.pid
                peak_pss = 0
                failures_in_row = 0
                reason = "normal_exit"
                while True:
                    members, pss_kb, failures = group_pss(pgid)
                    if failures:
                        failures_in_row += 1
                    else:
                        failures_in_row = 0
                    peak_pss = max(peak_pss, pss_kb)
                    log.write(json.dumps({"event": "sample", "time_epoch": time.time(),
                                          "pgid": pgid, "pids": [p for p, _ in members],
                                          "pss_kb": pss_kb, "peak_pss_kb": peak_pss,
                                          "sample_failures": failures}) + "\n")
                    log.flush()
                    if pss_kb >= PSS_LIMIT_KB:
                        reason = "aggregate_pss_limit_100_gib"
                        terminate_group(pgid, log, reason)
                        break
                    if failures_in_row >= 3:
                        reason = "three_consecutive_pss_sampling_failures"
                        terminate_group(pgid, log, reason)
                        break
                    if time.time() - started >= MAX_WALL_SECONDS:
                        reason = "wall_timeout_24h"
                        terminate_group(pgid, log, reason)
                        break
                    if process.poll() is not None:
                        members = group_members(pgid)
                        if not members or all(state == "Z" for _, state in members):
                            break
                        reason = "orphaned_process_group_after_main_exit"
                        terminate_group(pgid, log, reason)
                        break
                    time.sleep(SAMPLE_SECONDS)
                return_code = process.wait()
                caller_elapsed = time.time() - caller_started
            summary = {"run_id": RUN_ID, "host": socket.gethostname(),
                       "architecture": os.uname()[4], "cpus": cpus, "workers": 16,
                       "radii_bp": [10, 20], "caller_exit": return_code,
                       "stop_reason": reason, "watchdog_peak_pss_kb": peak_pss,
                       "watchdog_limit_gib": 100, "wall_limit_hours": 24,
                       "preflight_seconds": preflight_seconds,
                       "caller_wall_seconds_including_time_wrapper": caller_elapsed,
                       "bed_path": BED, "fragments_path": FRAGS, "runner_path": RUNNER,
                       "output_prefix": prefix, "output_dir": OUTPUT_DIR,
                       "watchdog_path": log_path, "gnu_time_path": time_path,
                       "caller_stdout_path": stdout_path,
                       "preflight_facts": preflight_facts}
            summary.update(frozen_hashes)
            for radius in (10, 20):
                for suffix in (".r%d.track.tsv.gz" % radius, ".r%d.native_events.bed" % radius):
                    path = prefix + suffix
                    if os.path.isfile(path):
                        summary[path] = {"bytes": os.path.getsize(path), "sha256": sha256(path),
                                         "rows": line_count(path)}
            timing_path = prefix + ".timing.tsv"
            if os.path.isfile(timing_path):
                summary[timing_path] = {"bytes": os.path.getsize(timing_path), "sha256": sha256(timing_path),
                                        "rows": line_count(timing_path)}
            required_outputs = [prefix + ".r%d.track.tsv.gz" % radius for radius in (10, 20)]
            required_outputs.extend([prefix + ".r%d.native_events.bed" % radius for radius in (10, 20)])
            required_outputs.append(timing_path)
            missing_outputs = [path for path in required_outputs if not os.path.isfile(path)]
            empty_tracks = [prefix + ".r%d.track.tsv.gz" % radius for radius in (10, 20)
                            if os.path.isfile(prefix + ".r%d.track.tsv.gz" % radius)
                            and summary.get(prefix + ".r%d.track.tsv.gz" % radius, {}).get("rows", 0) == 0]
            timing_rows = summary.get(timing_path, {}).get("rows", 0)
            summary["output_complete"] = not missing_outputs and not empty_tracks and timing_rows >= 2
            summary["missing_outputs"] = missing_outputs
            summary["empty_score_tracks"] = empty_tracks
            with open(os.path.join(ROOT, "summary.json"), "w") as handle:
                json.dump(summary, handle, indent=2, sort_keys=True)
                handle.write("\n")
            print(json.dumps(summary, sort_keys=True))
            if reason != "normal_exit":
                return 124
            if return_code == 0 and not summary["output_complete"]:
                return 3
            return return_code
        except Exception as error:
            log.write(json.dumps({"event": "preflight_or_supervisor_error",
                                  "error": str(error), "time_epoch": time.time()}) + "\n")
            log.flush()
            print("FAIL_CLOSED: " + str(error), file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
