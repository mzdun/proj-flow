# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.sign.win32** provides code signing with SignTool
from Windows SDKs.
"""

import base64
import json
import os
import platform
import struct
import subprocess
import sys
from typing import Iterable, List, Optional, Tuple

from proj_flow.api.env import Config, Msg, Runtime

from .api import ENV_KEY, SigningTool, get_key, signing_tool

if sys.platform == "win32":
    import winreg

    @signing_tool.add
    class Win32SigningTool(SigningTool):
        def is_active(self, config: Config, rt: Runtime):
            return _is_active(config.os, rt)

        def sign(self, config: Config, rt: Runtime, files: List[str]):
            rt.print("signtool", *(os.path.basename(file) for file in files))
            return _sign(files, rt)

        def is_signable(self, filename: str, as_package: bool):
            if as_package:
                _, ext = os.path.splitext(filename)
                if ext.lower() == ".msi":
                    return True
                # suport NSIS by checking if the archive is a PE
            return _is_pe_exec(filename)

    Version = Tuple[int, int, int]

    machine = {"ARM64": "arm64", "AMD64": "x64", "X86": "x86"}.get(
        platform.machine(), "x86"
    )

    def _find_sign_tool(rt: Runtime) -> Optional[str]:
        with winreg.OpenKeyEx(  # type: ignore
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots"  # type: ignore
        ) as kits:
            try:
                kits_root = winreg.QueryValueEx(kits, "KitsRoot10")[0]  # type: ignore
            except FileNotFoundError:
                rt.message("sign/win32: No KitsRoot10 value")
                return None

            versions: List[Tuple[Version, str]] = []
            try:
                index = 0
                while True:
                    ver_str = winreg.EnumKey(kits, index)  # type: ignore
                    ver = tuple(int(chunk) for chunk in ver_str.split("."))
                    index += 1
                    versions.append((ver, ver_str))  # type: ignore
            except OSError:
                pass
        versions.sort()
        versions.reverse()
        rt.message(
            "sign/win32: Regarding versions:",
            ", ".join(version[1] for version in versions),
        )
        for _, version in versions:
            # C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe
            sign_tool = os.path.join(kits_root, "bin", version, machine, "signtool.exe")
            if os.path.isfile(sign_tool):
                rt.message("sign/win32: using:", sign_tool)
                return sign_tool
        return None

    def _is_active(os_name: str, rt: Runtime):
        if os_name != "windows":
            return False
        key = get_key(rt)
        return (
            key is not None
            and key.token is not None
            and key.secret is not None
            and _find_sign_tool(rt) is not None
        )

    _IMAGE_DOS_HEADER = "HHHHHHHHHHHHHH8sHH20sI"
    _IMAGE_NT_HEADERS_Signature = "H"
    _IMAGE_DOS_HEADER_size = struct.calcsize(_IMAGE_DOS_HEADER)
    _IMAGE_NT_HEADERS_Signature_size = struct.calcsize(_IMAGE_NT_HEADERS_Signature)
    _MZ = 23117
    _PE = 17744

    def _is_pe_exec(path: str):
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

    def _sign(files: Iterable[str], rt: Runtime):
        key = get_key(rt)

        if key is None or key.token is None or key.secret is None:
            rt.fatal("sign: the key is missing")

        sign_tool = _find_sign_tool(rt)
        if sign_tool is None:
            rt.message("proj-flow: sign: signtool.exe not found", level=Msg.ALWAYS)
            return 0

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
