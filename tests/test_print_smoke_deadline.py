#!/usr/bin/env python3
"""Check that smoke and caller preflight honor one monotonic end-to-end budget."""
import importlib.util
import os
import json
import signal
import subprocess
import sys
import tempfile
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = os.path.join(os.path.dirname(__file__), "..", "scripts", "04b_footprint")
SMOKE = load("print_smoke", os.path.join(ROOT, "run_print_integration_smoke_supervised.py"))
BASE = load("print_base_supervisor", os.path.join(ROOT, "run_print_fullpeak_supervised.py"))


def main():
    assert SMOKE.sha256(os.path.join(ROOT, "select_print_integration_smoke.py")) == \
        SMOKE.SELECTOR_SHA256
    assert SMOKE.sha256(os.path.join(ROOT, "run_print.R")) == SMOKE.RUNNER_SHA256
    assert SMOKE.sha256(os.path.join(ROOT, "print_variable_width.R")) == SMOKE.HELPER_SHA256
    assert SMOKE.sha256(os.path.join(ROOT, "run_print_fullpeak_supervised.py")) == \
        SMOKE.BASE_SUPERVISOR_SHA256
    deadline = time.monotonic() + 10
    assert 0 < SMOKE.remaining_seconds(deadline) <= 10
    try:
        SMOKE.remaining_seconds(time.monotonic() - 1)
    except TimeoutError:
        pass
    else:
        raise AssertionError("smoke accepted an expired end-to-end deadline")

    previous = BASE.RUN_DEADLINE_MONOTONIC
    try:
        BASE.RUN_DEADLINE_MONOTONIC = time.monotonic() - 1
        try:
            BASE.check_wall_deadline()
        except TimeoutError:
            pass
        else:
            raise AssertionError("caller preflight accepted an expired deadline")
        BASE.RUN_DEADLINE_MONOTONIC = time.monotonic() + 0.1
        try:
            BASE.bounded_check_output(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                universal_newlines=True)
        except subprocess.TimeoutExpired:
            pass
        else:
            raise AssertionError("preflight subprocess exceeded the shared deadline")
    finally:
        BASE.RUN_DEADLINE_MONOTONIC = previous

    with tempfile.TemporaryDirectory(prefix="print-smoke-watchdog-normal-") as tmp:
        registry = os.path.join(tmp, "groups.jsonl")
        with open(registry, "w"):
            pass
        result = SMOKE.run_outer_worker(
            [sys.executable, "-c", "print('worker_done')"],
            time.monotonic() + 5, registry)
        return_code, stdout, _, timed_out, survivors, leaked, interrupted = result
        assert return_code == 0 and "worker_done" in stdout
        assert not timed_out and not survivors and not leaked and not interrupted

    with tempfile.TemporaryDirectory(prefix="print-smoke-watchdog-") as tmp:
        registry = os.path.join(tmp, "groups.jsonl")
        pid_path = os.path.join(tmp, "child.pid")
        with open(registry, "w"):
            pass
        child_code = (
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "time.sleep(30)"
        )
        worker_code = r'''
import json, os, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", sys.argv[2]], start_new_session=True)
with open(sys.argv[3], "w") as handle:
    handle.write(str(child.pid))
with open(sys.argv[1], "a") as handle:
    handle.write(json.dumps({"action":"register","pgid":child.pid,"role":"test_child"})+"\n")
    handle.flush()
    os.fsync(handle.fileno())
time.sleep(30)
'''
        command = [sys.executable, "-c", worker_code, registry, child_code, pid_path]
        result = SMOKE.run_outer_worker(command, time.monotonic() + 0.5,
                                        registry, cleanup_grace_seconds=0.5)
        return_code, _, _, timed_out, survivors, leaked, interrupted = result
        assert timed_out and leaked and return_code != 0 and not interrupted
        assert not survivors, "registered child process group survived bounded KILL"
        with open(pid_path) as handle:
            child_pid = int(handle.read())
        for _ in range(20):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("timeout cleanup left the detached child process alive")
    print("PRINT smoke end-to-end deadline checks passed")


if __name__ == "__main__":
    main()
