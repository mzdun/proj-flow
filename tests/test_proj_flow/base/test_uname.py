# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import platform

from proj_flow.base.uname import uname


def windows_uname(system: str):
    def wrap():
        return platform.uname_result(
            system=system,
            node="machine-name",
            release="11",
            version="10.0.22631",
            machine="AMD64",
        )

    return wrap


def linux_uname():
    return platform.uname_result(
        system="Linux",
        node="machine-name",
        release="6.11.0-17-generic",
        version="#17~24.04.2-Ubuntu SMP PREEMPT_DYNAMIC Mon Jan 20 22:48:29 UTC 2",
        machine="x86_64",
    )


def ubuntu_24_freedesktop_os_release():
    return {
        "NAME": "Ubuntu",
        "ID": "ubuntu",
        "VERSION_ID": "24.04",
        "VERSION": "24.04.2 LTS (Noble Numbat)",
    }


def leap_freedesktop_os_release():
    return {
        "NAME": "openSUSE Leap",
        "ID": "opensuse-leap",
        "VERSION_ID": "15.6",
        "VERSION": "15.6",
    }


def arch_freedesktop_os_release():
    return {
        "NAME": "Arch Linux",
        "ID": "arch",
        "VERSION_ID": "20240915.0.262934",
    }


def test_check_current_platform(mocker):
    mocker.patch(
        "platform.freedesktop_os_release", wraps=ubuntu_24_freedesktop_os_release
    )
    name, version, arch = uname()
    if os.name == "posix":
        assert name == "ubuntu"
        assert version is not None
    else:
        assert name == "windows"
        assert version is None
    assert arch == "x86_64"


def test_check_current_platform_no_os_release(monkeypatch):
    monkeypatch.delitem(platform.__dict__, "freedesktop_os_release")
    name, version, arch = uname()
    if os.name == "posix":
        assert name == "linux"
        assert version is not None
    else:
        assert name == "windows"
        assert version is None
    assert arch == "x86_64"


def test_force_windows_nt(mocker):
    mocker.patch("platform.uname", wraps=windows_uname("Windows_NT-11"))
    name, version, arch = uname()
    assert name == "windows"
    assert version is None
    assert arch == "x86_64"


def test_force_windows(mocker):
    mocker.patch("platform.uname", wraps=windows_uname("Windows"))
    name, version, arch = uname()
    assert name == "windows"
    assert version is None
    assert arch == "x86_64"


def test_force_ubuntu(mocker):
    mocker.patch("platform.uname", wraps=linux_uname)
    mocker.patch(
        "platform.freedesktop_os_release", wraps=ubuntu_24_freedesktop_os_release
    )
    name, version, arch = uname()
    assert name == "ubuntu"
    assert version == "24.04"
    assert arch == "x86_64"


def test_force_suse_leap(mocker):
    mocker.patch("platform.uname", wraps=linux_uname)
    mocker.patch("platform.freedesktop_os_release", wraps=leap_freedesktop_os_release)
    name, version, arch = uname()
    assert name == "opensuse"
    assert version == "15.6"
    assert arch == "x86_64"


def test_force_arch(mocker):
    mocker.patch("platform.uname", wraps=linux_uname)
    mocker.patch("platform.freedesktop_os_release", wraps=arch_freedesktop_os_release)
    name, version, arch = uname()
    assert name == "arch"
    assert version == "20240915.0"
    assert arch == "x86_64"
