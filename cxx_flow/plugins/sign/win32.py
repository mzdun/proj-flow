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

from cxx_flow.api.env import Runtime

ENV_KEY = "SIGN_TOKEN"

Version = Tuple[int, int, int]

machine = {"ARM64": "arm64", "AMD64": "x64", "X86": "x86"}.get(
    platform.machine(), "x86"
)


def find_sign_tool(rt: Runtime) -> Optional[str]:
    with winreg.OpenKeyEx(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots"
    ) as kits:
        try:
            kits_root = winreg.QueryValueEx(kits, "KitsRoot10")[0]
        except FileNotFoundError:
            rt.message("sign/win32: No KitsRoot10 value")
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
    rt.message(
        "sign/win32: Regarding versions:", ", ".join(version[1] for version in versions)
    )
    for _, version in versions:
        # C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe
        sign_tool = os.path.join(kits_root, "bin", version, machine, "signtool.exe")
        if os.path.isfile(sign_tool):
            rt.message("sign/win32: using:", sign_tool)
            return sign_tool
    return None


class Key(NamedTuple):
    token: str
    secret: bytes


def _get_key_from_contents(key: str, rt: Runtime):
    try:
        obj = json.loads(key)
    except json.decoder.JSONDecodeError:
        rt.message("sign/win32: the signature is not a valid JSON document")
        return None

    if not isinstance(obj, dict):
        rt.message("sign/win32: the signature is missing required fields")
        return None

    token = obj.get("token")
    secret = obj.get("secret")
    if not isinstance(token, str) or not isinstance(secret, str):
        rt.message("sign/win32: the signature is missing required fields")
        return None

    return Key(
        base64.b64decode(token).decode("UTF-8"),
        base64.b64decode(secret),
    )


def get_key(rt: Runtime) -> Optional[Key]:
    rt.message(f"sign/win32: trying ${ENV_KEY}")
    env = os.environ.get(ENV_KEY)
    if env:
        key = _get_key_from_contents(env, rt)
        if key is not None:
            return key
    local_signature = os.path.join(".", "signature.key")
    home_signature = os.path.join(os.path.expanduser("~"), "signature.key")
    for filename in [local_signature, home_signature]:
        rt.message(f"sign/win32: trying {filename}")
        if os.path.isfile(filename):
            with open(filename, encoding="UTF-8") as file:
                result = file.read().strip()
                key = _get_key_from_contents(result, rt)
                if key is not None:
                    return key

    rt.message("sign/win32: no key set up")

    return None


def is_active(os_name: str, rt: Runtime):
    if os_name != "windows":
        return False
    key = get_key(rt)
    return (
        key is not None
        and key.token is not None
        and key.secret is not None
        and find_sign_tool(rt) is not None
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


def sign(files: Iterable[str], rt: Runtime):
    key = get_key(rt)

    if key is None or key.token is None or key.secret is None:
        print("cxx-flow: sign: the key is missing", file=sys.stderr)
        return 1

    sign_tool = find_sign_tool(rt)
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
