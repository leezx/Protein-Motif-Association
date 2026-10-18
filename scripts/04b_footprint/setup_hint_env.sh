#!/bin/bash
# Create an isolated HINT runtime by cloning pmafp, then keep only its HINT-compatible dependency set.
# usage: setup_hint_env.sh <conda_executable> <pmafp_prefix> <pma_hint_prefix>
set -euo pipefail
CONDA=$1; PMAFP=$2; HINT_ENV=$3

if [ -e "$HINT_ENV" ]; then
  if [ ! -x "$HINT_ENV/bin/python" ]; then
    echo "HINT_ENV_EXISTS_BUT_INVALID $HINT_ENV; preserve and inspect it before retrying" >&2
    exit 2
  fi
  echo "HINT_ENV_ALREADY_EXISTS $HINT_ENV; validate it with run_4b1.sh preflight" >&2
  exit 2
fi

"$CONDA" list --explicit --prefix "$PMAFP" > "${HINT_ENV}.pmafp-conda-before.txt"
"$PMAFP/bin/python" -m pip freeze --all > "${HINT_ENV}.pmafp-pip-before.txt"
"$CONDA" create --offline --use-local --yes --prefix "$HINT_ENV" --clone "$PMAFP"
if "$HINT_ENV/bin/python" -m pip show TOBIAS >/dev/null 2>&1; then
  "$HINT_ENV/bin/python" -m pip uninstall --yes TOBIAS
fi
"$CONDA" install --offline --use-local --yes --prefix "$HINT_ENV" numpy=1.26.4 setuptools=80.9.0

"$HINT_ENV/bin/python" -m pip check
"$CONDA" list --explicit --prefix "$PMAFP" > "${HINT_ENV}.pmafp-conda-after.txt"
"$PMAFP/bin/python" -m pip freeze --all > "${HINT_ENV}.pmafp-pip-after.txt"
cmp "${HINT_ENV}.pmafp-conda-before.txt" "${HINT_ENV}.pmafp-conda-after.txt"
cmp "${HINT_ENV}.pmafp-pip-before.txt" "${HINT_ENV}.pmafp-pip-after.txt"
"$CONDA" list --explicit --prefix "$HINT_ENV" > "${HINT_ENV}.conda-explicit.txt"
"$HINT_ENV/bin/python" -m pip freeze --all > "${HINT_ENV}.pip-freeze.txt"
"$HINT_ENV/bin/python" - <<'PY'
from importlib.metadata import version
import numpy
import pkg_resources
import rgt
from numpy import mat

assert version("RGT") == "1.0.2"
assert version("setuptools") == "80.9.0"
assert numpy.__version__ == "1.26.4"
try:
    version("TOBIAS")
except Exception:
    pass
else:
    raise SystemExit("TOBIAS must not be installed in the isolated HINT environment")
print("HINT_IMPORT_OK", version("RGT"), numpy.__version__, version("setuptools"))
PY
"$HINT_ENV/bin/rgt-hint" --help
"$HINT_ENV/bin/rgt-hint" footprinting --help
echo HINT_ENV_READY
