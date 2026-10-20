#!/usr/bin/env python3
"""Regression coverage for the bounded 64-peak wrapper's independent parent."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import time


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts", "04b_footprint")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SPEED = load("print_speed64", os.path.join(SCRIPTS, "run_print_speed64_supervised.py"))
OUTER = load("print_outer_watchdog",
             os.path.join(SCRIPTS, "run_print_integration_smoke_supervised.py"))


def test_parent_delegates_all_work_to_supervised_worker():
    with tempfile.TemporaryDirectory(prefix="print-speed64-parent-") as tmp:
        root = os.path.join(tmp, "unique-run-root")
        previous = (SPEED.ROOT, SPEED.OUTPUT_DIR, SPEED.CODE_DIR,
                    SPEED.MAX_WALL_SECONDS, SPEED.sys.argv[:], SPEED.signal.signal,
                    SPEED.load_module)
        calls = []

        class FakeOuter:
            request_outer_stop = staticmethod(lambda signum, frame: None)

            @staticmethod
            def run_outer_worker(command, deadline, registry_path,
                                 cleanup_grace_seconds=60):
                calls.append((command, deadline, registry_path, cleanup_grace_seconds))
                return 0, "worker output", "", False, [], False, False

        try:
            SPEED.ROOT = root
            SPEED.OUTPUT_DIR = os.path.join(tmp, "unused-output")
            SPEED.CODE_DIR = SCRIPTS
            SPEED.MAX_WALL_SECONDS = 30
            SPEED.sys.argv = [SPEED.__file__, "ctrl", "print"]
            SPEED.signal.signal = lambda *_args: None
            SPEED.load_module = lambda _path: FakeOuter
            assert SPEED.main() == 0
        finally:
            (SPEED.ROOT, SPEED.OUTPUT_DIR, SPEED.CODE_DIR,
             SPEED.MAX_WALL_SECONDS, SPEED.sys.argv, SPEED.signal.signal,
             SPEED.load_module) = previous

        assert len(calls) == 1
        command, deadline, registry, grace = calls[0]
        assert command[1] == os.path.abspath(SPEED.__file__)
        assert command[2] == "--worker"
        assert command[4] == os.path.join(root, "process_groups.jsonl")
        assert registry == command[4]
        assert grace == 60
        assert deadline > time.monotonic()
        assert not os.path.exists(root), "parent must not perform worker data setup"


def test_blocked_worker_cleans_detached_registered_group():
    with tempfile.TemporaryDirectory(prefix="print-speed64-timeout-") as tmp:
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
    handle.write(json.dumps({"action":"register","pgid":child.pid,"role":"independent_child"})+"\n")
    handle.flush()
    os.fsync(handle.fileno())
time.sleep(30)
'''
        command = [sys.executable, "-c", worker_code, registry, child_code, pid_path]
        result = OUTER.run_outer_worker(command, time.monotonic() + 0.5,
                                        registry, cleanup_grace_seconds=0.5)
        return_code, _, _, timed_out, survivors, leaked, interrupted = result
        assert timed_out and leaked and not interrupted and return_code != 0
        assert not survivors, "registered detached process group survived bounded cleanup"
        with open(pid_path) as handle:
            child_pid = int(handle.read())
        for _ in range(40):
            if not OUTER.group_exists(child_pid):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("timeout left the independent process group alive")


if __name__ == "__main__":
    test_parent_delegates_all_work_to_supervised_worker()
    test_blocked_worker_cleans_detached_registered_group()
    print("PRINT 64-peak parent/timeout cleanup checks passed")
