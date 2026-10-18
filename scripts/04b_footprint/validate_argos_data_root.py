#!/usr/bin/env python3
"""Fail closed unless an Argos data path is the repo-configured PMA footprint root."""
import argparse
import os
from pathlib import Path


def validate_data_root(candidate: Path, configured_pma_data: Path) -> Path:
    expected = (configured_pma_data / "atac_footprint").resolve()
    observed = candidate.resolve()
    if observed != expected:
        raise ValueError(f"ARGOS_DATA_ROOT_DOES_NOT_MATCH_REPOSITORY_CONFIG:{observed}")
    if not (observed / "raw").is_dir() or not (observed / "processed" / "round1").is_dir():
        raise ValueError(f"ARGOS_DATA_ROOT_LAYOUT_INVALID:{observed}")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("configured_pma_data", type=Path)
    args = parser.parse_args()
    print(validate_data_root(args.candidate, args.configured_pma_data))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        raise SystemExit(str(exc))
