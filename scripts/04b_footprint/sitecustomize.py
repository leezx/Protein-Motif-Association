"""Bootstrap setuptools local distutils before any child Python imports pip."""
import os
import pathlib
import sys


_root_value = os.environ.get("PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT")
if _root_value:
    try:
        from probe_hint_argos_toolchain import probe_startup

        expected_probe = pathlib.Path(__file__).with_name("probe_hint_argos_toolchain.py").resolve()
        actual_probe = pathlib.Path(probe_startup.__code__.co_filename).resolve()
        if actual_probe != expected_probe:
            raise RuntimeError(f"ARGOS_TOOLCHAIN_PROBE_SOURCE_MISMATCH:{actual_probe}")
        probe_startup(pathlib.Path(_root_value))
    except BaseException as _error:
        print(
            f"ARGOS_TOOLCHAIN_STARTUP_PROBE_FAIL:{type(_error).__name__}:{_error}",
            file=sys.stderr,
            flush=True,
        )
        # site.py may report and swallow ordinary sitecustomize exceptions.
        # Exit the interpreter so a child pip/build process cannot continue.
        os._exit(78)
