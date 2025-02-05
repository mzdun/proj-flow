# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.log.fmt** contains formatting routines for various targets.
"""

from cxx_flow.log import commit, msg


def format_commit_message(log: commit.ChangeLog):
    return msg.CommitMessage().format_changelog(log)
