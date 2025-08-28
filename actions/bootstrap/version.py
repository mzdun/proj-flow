# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json
import os
from platform import machine
from typing import cast

VAR_NAME = "CXX_FLOW_VERSION"
VARIABLE = ""
IS_FLOW_APP = False

RUNNER = cast(dict, json.loads(os.environ["RUNNER_CONTEXT"]))
RUNNER_OS = RUNNER.get("os", os.name)
RUNNER_ARCH = RUNNER.get("arch", machine() or "unk-arch")

try:
    with open(".flow/flow.py", encoding="UTF-8") as flow_py:
        for line in flow_py:
            if not line.startswith(VAR_NAME):
                continue

            var_list = line.split("=", 1)
            if len(var_list) != 2:
                continue

            var = var_list[0].strip()
            if var != VAR_NAME:
                continue

            val = var_list[1].strip()
            start = val[:1]
            if start not in "\"'":
                continue

            VARIABLE = val[1:].split(start, 1)[0].strip()
            break

    IS_FLOW_APP = True

except FileNotFoundError:
    pass

VENV_CACHE_KEY = f"venv-{RUNNER_OS}-{RUNNER_ARCH}-{VARIABLE}"

with open(os.environ["GITHUB_OUTPUT"], "a", encoding="UTF-8") as out:
    print(f"version={VARIABLE}", file=out)
    print(f"venv-cache-key={VENV_CACHE_KEY}", file=out)
    print(f"is-flow-app={json.dumps(IS_FLOW_APP)}", file=out)
