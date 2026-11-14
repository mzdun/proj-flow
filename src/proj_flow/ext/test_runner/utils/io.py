# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner.utils.io** defines :class:`ProcessIO`, collecting the return
code and the outputs of processes run by a test case.
"""

import subprocess
from dataclasses import dataclass, field


@dataclass
class ProcessIO:
    """
    Combined result of one or more processes, compared against the
    ``expected`` value of a test case.
    """

    #: Return code of the most recently appended process.
    returncode: int = field(default=0)
    #: Decoded standard outputs of all appended processes, joined with
    #: newlines.
    stdout: str = field(default_factory=str)
    #: Decoded standard errors of all appended processes, joined with
    #: newlines.
    stderr: str = field(default_factory=str)

    def as_dict(self):
        """
        Converts this object to the form stored as ``expected`` in a test
        case.

        :returns: dictionary with ``return-code``, ``stdout`` and ``stderr``
            keys
        """
        return {
            "return-code": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }

    def append(self, proc: subprocess.CompletedProcess[bytes]):
        """
        Adds results of another process. Takes over its return code and
        appends its decoded outputs, separated by a newline, if both previous
        and new output are not empty.

        :param proc: finished process with captured outputs
        """
        self.returncode = proc.returncode
        if len(self.stdout) and len(proc.stdout):
            self.stdout += "\n"
        if len(self.stderr) and len(proc.stderr):
            self.stderr += "\n"
        # invalid UTF-8 shows up as U+FFFD in the comparison, instead of
        # crashing the whole run
        self.stdout += proc.stdout.decode(errors="replace")
        self.stderr += proc.stderr.decode(errors="replace")
