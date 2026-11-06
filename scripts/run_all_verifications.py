"""Run the repository regression suites and critical browser smoke checks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _python_executable() -> str:
    venv_python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    return str(venv_python if venv_python.is_file() else Path(sys.executable))


def _npm_command(*args: str) -> tuple[str | list[str], bool]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise FileNotFoundError("npm was not found on PATH")
    command = [npm, *args]
    # Windows batch shims must be launched through the command shell.
    if os.name == "nt" and Path(npm).suffix.lower() in {".cmd", ".bat"}:
        return subprocess.list2cmdline(command), True
    return command, False


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8", errors="replace")


def _run(label: str, command: str | list[str], shell: bool, log) -> int:
    _configure_stdout()
    print(f"\n=== {label} ===", flush=True)
    print(f"$ {command}", flush=True)
    log.write(f"\n=== {label} ===\n$ {command}\n")
    log.flush()
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        message = f"Could not start command: {exc}"
        print(message, flush=True)
        log.write(message + "\n")
        return 127

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        log.write(line)
    code = process.wait()
    log.write(f"[exit code: {code}]\n")
    log.flush()
    print(f"[exit code: {code}]", flush=True)
    return code


def main() -> int:
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    log_path = artifacts / f"all-verifications-{stamp}.log"

    node = shutil.which("node")
    git = shutil.which("git")
    python = _python_executable()
    commands: list[tuple[str, str | list[str], bool]] = []

    try:
        commands.append(("JavaScript syntax check", *_npm_command("run", "syntax-check")))
        commands.append(("Full Node test suite", *_npm_command("test")))
    except FileNotFoundError as exc:
        commands.append(("npm availability", str(exc), False))

    if node:
        commands.extend(
            [
                ("Clinical safety browser E2E", [node, "tests/clinical_safety_e2e.js"], False),
                ("Product brand responsive browser E2E", [node, "tests/product_brand_e2e.js"], False),
            ]
        )
    else:
        commands.append(("Node availability", "node was not found on PATH", False))

    commands.append(("Full Python test suite", [python, "-m", "pytest", "-q"], False))
    if git:
        commands.append(("Whitespace and patch check", [git, "diff", "--check", "HEAD"], False))
    else:
        commands.append(("Git availability", "git was not found on PATH", False))

    results: list[tuple[str, int]] = []
    with log_path.open("x", encoding="utf-8", newline="\n") as log:
        log.write(f"Repository: {ROOT}\nStarted: {datetime.now().astimezone().isoformat()}\n")
        for label, command, shell in commands:
            code = _run(label, command, shell, log)
            results.append((label, code))

        passed = sum(code == 0 for _, code in results)
        failed = len(results) - passed
        summary = f"\nSummary: {passed}/{len(results)} steps passed; {failed} failed.\nLog: {log_path}\n"
        print(summary, flush=True)
        log.write(summary)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
