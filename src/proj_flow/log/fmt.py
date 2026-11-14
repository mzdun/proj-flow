# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.fmt** contains formatting routines for various targets.
"""

from proj_flow.log import commit, msg


def format_commit_message(log: commit.ChangeLog):
    """
    Format the changelog for the body of a release commit, wrapped at 78
    columns.

    :param log: changes to format
    :returns: commit message body, preceded by an empty line
    """
    return msg.CommitMessage().format_changelog(log)
