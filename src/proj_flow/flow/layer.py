# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.flow.layer** supports :ref:`template` layers.
"""

import json
import os
import shutil
from dataclasses import dataclass
from typing import List, Optional, cast

import chevron

from proj_flow.api import ctx, env


@dataclass
class FileInfo:
    src: str
    dst: str
    is_mustache: bool
    when: Optional[str] = None

    @classmethod
    def from_json(cls, src: str, filelist: dict, context: ctx.SettingsType):
        basename, ext = os.path.splitext(src)
        is_mustache = ext == ".mustache"
        key = src.replace(os.sep, "/")
        json_file = cast(dict, filelist.get(key, {}))
        path = cast(Optional[str], json_file.get("path"))
        when = cast(Optional[str], json_file.get("when"))
        dst = (
            chevron.render(path, context).replace("/", os.sep)
            if path is not None
            else basename if is_mustache else src
        )
        return cls(src=src, dst=dst, is_mustache=is_mustache, when=when)

    def template(self):
        open_mstch = "{{"
        close_mstch = "}}"
        if self.when:
            return f"{open_mstch}#{self.when}{close_mstch}\n{self.dst}\n{open_mstch}/{self.when}{close_mstch}\n"
        return f"{self.dst}\n"

    def run(self, root: str, rt: env.Runtime, context: ctx.SettingsType):
        if not rt.silent:
            if rt.use_color:
                print(f"\033[2;30m+\033[m {self.dst}")
            else:
                print(f"+ {self.dst}")
        if rt.dry_run:
            return

        src = os.path.join(root, self.src)
        dst = os.path.abspath(self.dst)
        dirname = os.path.dirname(dst)
        os.makedirs(dirname, exist_ok=True)

        if self.is_mustache:
            with open(src, "rb") as inf:
                content = inf.read().decode("UTF-8")
            content = chevron.render(content, context)
            with open(dst, "wb") as outf:
                outf.write(content.encode("UTF-8"))
            shutil.copymode(src, dst, follow_symlinks=False)
            shutil.copystat(src, dst, follow_symlinks=False)
        else:
            shutil.copy2(src, dst, follow_symlinks=False)


@dataclass
class LayerInfo:
    root: str
    files: List[FileInfo]
    when: Optional[str] = None

    @classmethod
    def from_fs(cls, layer_dir: str, context: ctx.SettingsType):
        with open(f"{layer_dir}.json", encoding="UTF-8") as f:
            layer_info: dict = json.load(f)
        when = cast(Optional[bool], layer_info.get("when"))
        filelist = cast(dict, layer_info.get("filelist", {}))

        sources: List[str] = []
        prefix = os.path.join(layer_dir, "")
        for curr_dir, dirs, files in os.walk(layer_dir):
            dirs[:] = [dirname for dirname in dirs if dirname not in ["__pycache__"]]
            files[:] = [
                filename
                for filename in files
                if os.path.splitext(filename) not in [".pyc", ".pyo", ".pyd"]
            ]

            for filename in files:
                src = os.path.join(curr_dir, filename)
                if src.startswith(prefix):
                    src = src[len(prefix) :]
                sources.append(src)

        files = [FileInfo.from_json(src, filelist, context) for src in sources]
        files.sort(key=lambda info: info.dst)

        result = cls(root=layer_dir, files=files, when=when)
        allowed_files = set(
            filter(
                lambda path: path != "",
                chevron.render(result.template(), context).split("\n"),
            )
        )
        result.files = list(filter(lambda file: file.dst in allowed_files, files))

        return result

    @property
    def name(self):
        return os.path.basename(self.root)

    @property
    def pkg(self):
        return os.path.basename(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(self.root)))
            )
        )

    def template(self):
        open_mstch = "{{"
        close_mstch = "}}"
        result = ""
        if self.when:
            result += f"{open_mstch}#{self.when}{close_mstch}\n"
        result += "".join(file.template() for file in self.files)
        if self.when:
            result += f"{open_mstch}/{self.when}{close_mstch}\n"
        return result

    def run(self, rt: env.Runtime, context: ctx.SettingsType):
        if not rt.silent:
            if rt.use_color:
                print(f"\033[2;30m[{self.pkg}:{self.name}]\033[m")
            else:
                print(f"[{self.pkg}:{self.name}]")
        for file in self.files:
            file.run(self.root, rt, context)
        if not rt.silent:
            print()


def copy_license(rt: env.Runtime, context: ctx.SettingsType):
    license = context.get("COPY", {}).get("LICENSE")
    if not license:
        return

    licenses_dir = os.path.abspath(
        os.path.join(ctx.package_root, ctx.template_dir, "licenses")
    )
    license_file = f"{license}.mustache"
    info = FileInfo(license_file, "LICENSE", is_mustache=True)
    info.run(licenses_dir, rt, context)


def gather_package_layers(package_root: str, context: ctx.SettingsType):
    layers_dir = os.path.abspath(os.path.join(package_root, ctx.template_dir, "layers"))
    for root, dirs, files in os.walk(layers_dir):
        layer_dirs = [
            os.path.abspath(os.path.join(root, dirname))
            for dirname in dirs
            if f"{dirname}.json" in files
        ]
        dirs[:] = []

    layers = (LayerInfo.from_fs(layer_dir, context) for layer_dir in layer_dirs)
    return list(filter(lambda layer: len(layer.files) > 0, layers))
