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
import textwrap


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = os.path.join(os.path.dirname(__file__), "..", "scripts", "04b_footprint")
SMOKE = load("print_smoke", os.path.join(ROOT, "run_print_integration_smoke_supervised.py"))
BASE = load("print_base_supervisor", os.path.join(ROOT, "run_print_fullpeak_supervised.py"))


def main():
    assert SMOKE.RUN_ID == "BG_K562_PRINT_STREAM_VALIDATION_20261020_V4"
    assert all("_20261020_v4" in path for path in
               (SMOKE.SCRIPT_DIR, SMOKE.ROOT, SMOKE.OUTPUT_DIR))
    assert all("_20261020_v3" not in path and "_20261020_v2" not in path for path in
               (SMOKE.SCRIPT_DIR, SMOKE.ROOT, SMOKE.OUTPUT_DIR))
    assert SMOKE.sha256(os.path.join(ROOT, "select_print_integration_smoke.py")) == \
        SMOKE.SELECTOR_SHA256
    assert SMOKE.RUNNER_SHA256 == SMOKE.sha256(os.path.join(ROOT, "run_print.R"))
    assert SMOKE.HELPER_SHA256 == SMOKE.sha256(os.path.join(ROOT, "print_variable_width.R"))
    assert SMOKE.BASE_SUPERVISOR_SHA256 == SMOKE.sha256(
        os.path.join(ROOT, "run_print_fullpeak_supervised.py"))
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
    previous_registry = BASE.PROCESS_GROUP_REGISTRY
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

        BASE.RUN_DEADLINE_MONOTONIC = time.monotonic() + 5
        try:
            BASE.bounded_check_output(
                [sys.executable, "-c",
                 "import sys; sys.stdout.write('out'); sys.stderr.write('err'); sys.exit(7)"],
                universal_newlines=True)
        except subprocess.CalledProcessError as error:
            assert error.returncode == 7
            assert error.output == "out" and error.stderr == "err"
        else:
            raise AssertionError("preflight exit 7 was accepted as successful output")
    finally:
        BASE.RUN_DEADLINE_MONOTONIC = previous
        BASE.PROCESS_GROUP_REGISTRY = previous_registry

    with tempfile.TemporaryDirectory(prefix="print-smoke-registry-failure-") as tmp:
        registry_directory = os.path.join(tmp, "not_a_file")
        os.mkdir(registry_directory)
        marker = os.path.join(tmp, "command_executed")
        BASE.PROCESS_GROUP_REGISTRY = registry_directory
        try:
            BASE.start_registered_process(
                [sys.executable, "-c",
                 "open(%r, 'w').write('ran')" % marker],
                "registry_failure_test", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
        except IsADirectoryError:
            pass
        else:
            raise AssertionError("registry failure did not stop gated child launch")
        finally:
            BASE.PROCESS_GROUP_REGISTRY = previous_registry
        assert not os.path.exists(marker), "child executed before durable registration"

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
        for _ in range(40):
            if not SMOKE.group_exists(child_pid):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("timeout cleanup left the detached child process alive")

    with tempfile.TemporaryDirectory(prefix="print-smoke-registration-window-") as tmp:
        registry = os.path.join(tmp, "groups.jsonl")
        pid_path = os.path.join(tmp, "gated-child.pid")
        marker = os.path.join(tmp, "target_executed")
        with open(registry, "w"):
            pass
        worker_code = textwrap.dedent(r'''
            import importlib.util, os, subprocess, sys, time
            module_path, registry, pid_path, marker = sys.argv[1:]
            spec = importlib.util.spec_from_file_location("base", module_path)
            base = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(base)
            base.PROCESS_GROUP_REGISTRY = registry
            original_registry = base.registry_event
            original_popen = subprocess.Popen
            def capture_popen(*args, **kwargs):
                child = original_popen(*args, **kwargs)
                with open(pid_path, "w") as handle:
                    handle.write(str(child.pid))
                return child
            subprocess.Popen = capture_popen
            def delayed_registry(*args, **kwargs):
                time.sleep(30)
                return original_registry(*args, **kwargs)
            base.registry_event = delayed_registry
            base.start_registered_process(
                [sys.executable, "-c", "open(%r, 'w').write('ran')" % marker],
                "registration_window_test", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ''')
        result = SMOKE.run_outer_worker(
            [sys.executable, "-c", worker_code, BASE.__file__, registry, pid_path, marker],
            time.monotonic() + 0.5, registry, cleanup_grace_seconds=0.5)
        return_code, _, _, timed_out, survivors, _, _ = result
        assert timed_out and return_code != 0 and not survivors
        with open(pid_path) as handle:
            gated_pid = int(handle.read())
        for _ in range(40):
            if not SMOKE.group_exists(gated_pid):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("gated child survived its worker during registration window")
        assert not os.path.exists(marker), "target executed before its registry entry"
    print("PRINT smoke end-to-end deadline checks passed")


if __name__ == "__main__":
    main()
