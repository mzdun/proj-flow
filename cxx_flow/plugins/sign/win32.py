# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import base64
import json
import os
import platform
import struct
import subprocess
import sys
import winreg
from typing import Iterable, List, NamedTuple, Optional, Tuple

ENV_KEY = "SIGN_TOKEN"

Version = Tuple[int, int, int]

machine = {"ARM64": "arm64", "AMD64": "x64", "X86": "x86"}.get(
    platform.machine(), "x86"
)


def find_sign_tool() -> Optional[str]:
    with winreg.OpenKeyEx(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots"
    ) as kits:
        try:
            kits_root = winreg.QueryValueEx(kits, "KitsRoot10")[0]
        except FileNotFoundError:
            return None

        versions: List[Tuple[Version, str]] = []
        try:
            index = 0
            while True:
                ver_str = winreg.EnumKey(kits, index)
                ver = tuple(int(chunk) for chunk in ver_str.split("."))
                index += 1
                versions.append((ver, ver_str))
        except OSError:
            pass
    versions.sort()
    versions.reverse()
    for _, version in versions:
        # C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe
        sign_tool = os.path.join(kits_root, "bin", version, machine, "signtool.exe")
        if os.path.isfile(sign_tool):
            return sign_tool
    return None


def get_key_():
    env = os.environ.get(ENV_KEY)
    if env is not None:
        return env
    filename = os.path.join(os.path.expanduser("~"), "signature.key")
    if os.path.isfile(filename):
        with open(filename, encoding="UTF-8") as file:
            return file.read().strip()
    filename = os.path.join(".", "signature.key")
    if os.path.isfile(filename):
        with open(filename, encoding="UTF-8") as file:
            return file.read().strip()

    return None


class Key(NamedTuple):
    token: str
    secret: bytes


def get_key() -> Optional[Key]:
    key = get_key_()
    if key is None:
        return None
    obj = json.loads(key)
    token = obj.get("token")
    secret = obj.get("secret")
    return Key(
        base64.b64decode(token).decode("UTF-8") if token is not None else None,
        base64.b64decode(secret) if secret is not None else None,
    )


def is_active(os_name: str):
    if os_name != "windows":
        return False
    key = get_key()
    return (
        find_sign_tool() is not None
        and key is not None
        and key.token is not None
        and key.secret is not None
    )


_IMAGE_DOS_HEADER = "HHHHHHHHHHHHHH8sHH20sI"
_IMAGE_NT_HEADERS_Signature = "H"
_IMAGE_DOS_HEADER_size = struct.calcsize(_IMAGE_DOS_HEADER)
_IMAGE_NT_HEADERS_Signature_size = struct.calcsize(_IMAGE_NT_HEADERS_Signature)
_MZ = 23117
_PE = 17744


def is_pe_exec(path: str):
    with open(path, "rb") as exe:
        mz_header = exe.read(_IMAGE_DOS_HEADER_size)
        dos_header = struct.unpack(_IMAGE_DOS_HEADER, mz_header)
        if dos_header[0] != _MZ:
            return False

        PE_offset = dos_header[-1]
        if PE_offset < _IMAGE_DOS_HEADER_size:
            return False

        if PE_offset > _IMAGE_DOS_HEADER_size:
            exe.read(PE_offset - _IMAGE_DOS_HEADER_size)

        pe_header = exe.read(_IMAGE_NT_HEADERS_Signature_size)
        signature = struct.unpack(_IMAGE_NT_HEADERS_Signature, pe_header)[0]
        return signature == _PE


def sign(files: Iterable[str]):
    key = get_key()

    if key is None or key.token is None or key.secret is None:
        print("cxx-flow: sign: the key is missing", file=sys.stderr)
        return 1

    sign_tool = find_sign_tool()
    if sign_tool is None:
        print("cxx-flow: sign: signtool.exe not found", file=sys.stderr)
        sys.exit(0)

    with open("temp.pfx", "wb") as pfx:
        pfx.write(key.secret)

    args = [
        sign_tool,
        "sign",
        "/f",
        "temp.pfx",
        "/p",
        key.token,
        "/tr",
        "http://timestamp.digicert.com",
        "/fd",
        "sha256",
        "/td",
        "sha256",
        *files,
    ]

    result = 1
    try:
        result = subprocess.run(args, shell=False).returncode
    finally:
        os.remove("temp.pfx")

    return result
