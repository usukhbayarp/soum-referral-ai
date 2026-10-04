"""Noninteractive entrypoint reusing the installed Anaconda MLX environment.

Its optional readline extension segfaults on this host. Disabling line editing
for this process avoids importing that extension; no environment is modified.
Usage: python -m scripts.mlx_python MODULE [args...]
       python -m scripts.mlx_python --script PATH [args...]
"""

import runpy
import sys
from pathlib import Path


def main():
    sys.modules["readline"] = None
    if len(sys.argv) < 2:
        raise SystemExit("Supply a Python module or --script PATH")
    if sys.argv[1] == "--script":
        sys.argv = sys.argv[2:]
        if not sys.argv:
            raise SystemExit("--script requires a path")
        sys.path.insert(0, str(Path(sys.argv[0]).resolve().parent))
        runpy.run_path(sys.argv[0], run_name="__main__")
    else:
        sys.argv = sys.argv[1:]
        runpy.run_module(sys.argv[0], run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
