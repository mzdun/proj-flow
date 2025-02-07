# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.error** declares a number of exceptions, which can be
raised during the changelog operations.
"""


class ReleaseError(Exception):
    def __init__(self, message: str):
        super().__init__()
        self.message = message


class NoProjectError(ReleaseError):
    def __init__(self):
        super().__init__("No project definition found.")


class TagExistsError(ReleaseError):
    def __init__(self, tag: str):
        super().__init__(f"Tag {tag}] already exists.")
        self.tag = tag


class VersionNotAdvancing(Exception):
    def __init__(self, version: str):
        super().__init__()
        self.message = f"[{version}] Version did not change, not doing anything."
        self.version = version
