# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.uname** provides platform information usable in packaging.
"""

import platform
from typing import Optional, Tuple

NameStr = str
VersionStr = Optional[str]
ArchStr = str


def uname() -> Tuple[NameStr, VersionStr, ArchStr]:
    """
    Return normalized information from :py:mod:`platform` module.

    Specifically, the machine architecture is swapped from "amd64" to "x86_64",
    which is more common in package filenames.

    On Windows system, with OS not easily returning current version and with
    high level of backward compatibility, system version is removed
    all-together.

    On Linux systems, true name of the system is retrieved, using
    :py:func:`platform.freedesktop_os_release`. On systems, where Python is
    missing this function, a fallback is made to "linux" and version returned
    by :py:func:`platform.uname`.

    :returns: a tuple consisting of system name, version and
       machine architecture

    :see: :ref:`command-system` command
    """
    _platform = platform.uname()
    platform_name = _platform.system.lower()
    platform_version = _platform.version
    platform_arch = _platform.machine.lower()

    if platform_arch == "amd64":
        platform_arch = "x86_64"

    system_nt = platform_name.split("_nt-", 1)

    if len(system_nt) > 1:
        platform_name = system_nt[0]
        platform_version = None
    elif platform_name == "windows":
        platform_version = None
    elif platform_name == "linux":
        try:
            os_release = platform.freedesktop_os_release()
        except AttributeError:
            os_release = {"ID": "linux", "NAME": "Linux"}

        platform_id = os_release.get("ID", os_release.get("NAME"))
        version_id = os_release.get("VERSION_ID", platform_version)
        if platform_id is not None:
            if platform_id[:9] == "opensuse-":
                platform_id = "opensuse"
            platform_name = platform_id.lower()
            if version_id != "" and version_id[0] in "0123456789":
                platform_version = ".".join(version_id.split(".", 2)[:2])

    return (
        platform_name,
        platform_version,
        platform_arch,
    )
