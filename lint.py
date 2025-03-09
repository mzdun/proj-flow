# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import subprocess
import sys

LINTERS = ["black", "isort", "flake8", "mypy"]
if "pylint" in sys.argv[1:]:
    LINTERS.append("pylint")

print(" && ".join(f"{tool} ." for tool in LINTERS))

for tool in LINTERS:
    proc = subprocess.run([tool, "."], check=False)
    if proc.returncode:
        sys.exit(1)
