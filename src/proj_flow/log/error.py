# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.error** declares a number of exceptions, which can be
raised during the changelog operations.
"""


class ReleaseError(Exception):
    """
    Base of the errors stopping a release.

    :param message: description of the error
    """

    def __init__(self, message: str):
        super().__init__()
        self.message = message


class NoProjectError(ReleaseError):
    """
    No project suite recognizes the project, so there is no version to bump.
    """

    def __init__(self):
        super().__init__("No project definition found.")


class VersionNotAdvancing(Exception):
    """
    Changes since the previous release do not bump the version.

    :param version: current version of the project
    """

    def __init__(self, version: str):
        super().__init__()
        self.message = f"[{version}] Version did not change, not doing anything."
        self.version = version
