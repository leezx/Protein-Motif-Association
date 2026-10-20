#!/usr/bin/env python3
"""Check that smoke and caller preflight honor one monotonic end-to-end budget."""
import importlib.util
import os
import subprocess
import sys
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
    print("PRINT smoke end-to-end deadline checks passed")


if __name__ == "__main__":
    main()
