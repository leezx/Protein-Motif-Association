#!/usr/bin/env python3
"""Stream a subprocess log to a file while removing URL credentials and queries."""
import argparse
import re
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path


def redact_url(match: re.Match[str]) -> str:
    parsed = urlsplit(match.group(0))
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def redact_text(value: str) -> str:
    return re.sub(r'''https?://[^\s"'<>]+''', redact_url, value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    try:
        with args.log.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, errors="replace", bufsize=1)
            assert process.stdout is not None
            for line in process.stdout:
                log.write(redact_text(line))
                log.flush()
            return process.wait()
    except OSError as exc:
        args.log.write_text(redact_text(f"REDACTED_COMMAND_START_FAILED:{exc}\n"), encoding="utf-8")
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
