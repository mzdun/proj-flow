# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import subprocess
from dataclasses import dataclass, field


@dataclass
class ProcessIO:
    returncode: int = field(default=0)
    stdout: str = field(default_factory=str)
    stderr: str = field(default_factory=str)

    def as_dict(self):
        return {
            "return-code": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }

    def append(self, proc: subprocess.CompletedProcess[bytes]):
        self.returncode = proc.returncode
        if len(self.stdout) and len(proc.stdout):
            self.stdout += "\n"
        if len(self.stderr) and len(proc.stderr):
            self.stderr += "\n"
        self.stdout += proc.stdout.decode()
        self.stderr += proc.stderr.decode()
