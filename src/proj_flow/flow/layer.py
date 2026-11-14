# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.flow.layer** supports :ref:`template` layers.
"""

import json
import os
import shutil
from dataclasses import dataclass
from typing import List, Optional, Union, cast

import chevron

from proj_flow.api import ctx, env
from proj_flow.base import path_get

When = Union[str, List[str], None]


def _when_conditions(when: When) -> List[str]:
    if not when:
        return []
    if isinstance(when, str):
        return [when]
    return when


def _wrap_in_conditions(text: str, when: When) -> str:
    """
    Wraps ``text`` in mustache sections, one for each condition in ``when``.
    All conditions must hold. A condition starting with ``^`` is negated,
    just like an inverted section in mustache.
    """
    for condition in reversed(_when_conditions(when)):
        kind = "#"
        if condition.startswith("^"):
            kind = "^"
            condition = condition[1:]
        text = f"{{{{{kind}{condition}}}}}\n{text}{{{{/{condition}}}}}\n"
    return text


@dataclass
class FileInfo:
    """
    Single file of a template layer.
    """

    #: Path of the file, relative to the layer directory.
    src: str
    #: Path of the file in the new project.
    dst: str
    #: The file is passed through mustache before being written.
    is_mustache: bool
    #: The file should be marked executable in Git.
    is_executable: bool
    #: Condition(s) from the ``filelist.<path>.when`` of the layer config.
    when: When = None

    @classmethod
    def from_json(cls, src: str, filelist: dict, context: ctx.SettingsType):
        """
        Describe a file using the ``filelist`` object of the layer config. The
        destination is the rendered ``path`` from the config, if present, or
        the source path with the ``.mustache`` extension removed.

        :param src: path of the file, relative to the layer directory
        :param filelist: the ``filelist`` object of the layer config
        :param context: the mustache context of the new project
        """
        basename, ext = os.path.splitext(src)
        is_mustache = ext == ".mustache"
        key = src.replace(os.sep, "/")
        json_file = cast(dict, filelist.get(key, {}))
        path = cast(Optional[str], json_file.get("path"))
        when = cast(When, json_file.get("when"))
        is_executable = cast(bool, json_file.get("executable"))
        dst = (
            chevron.render(path, context).replace("/", os.sep)
            if path is not None
            else basename if is_mustache else src
        )
        return cls(
            src=src,
            dst=dst,
            is_mustache=is_mustache,
            is_executable=is_executable,
            when=when,
        )

    def template(self):
        """
        :returns: mustache template rendering the source path, if the file's
            conditions hold, or nothing otherwise
        """
        return _wrap_in_conditions(f"{self.src}\n", self.when)

    def run(self, root: str, rt: env.Runtime, context: ctx.SettingsType):
        """
        Write the file into the new project, rendering it through mustache, if
        needed, and keeping the file mode. With ``--dry-run``, only print the
        destination.

        :param root: directory of the layer
        :param rt: runtime used for messages and ``--dry-run``
        :param context: the mustache context of the new project
        """
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

    def get_git_checks(self):
        """
        :returns: this file, if it should be marked executable in Git
        """
        if self.is_executable:
            yield self


@dataclass
class LayerInfo:
    """
    Template layer: a directory of files with its JSON config next to it.
    """

    #: Directory of the layer.
    root: str
    #: Files of the layer, which pass their conditions.
    files: List[FileInfo]
    #: Condition(s) from the ``when`` of the layer config.
    when: When = None

    @classmethod
    def from_fs(cls, layer_dir: str, context: ctx.SettingsType):
        """
        Read the layer config (``<layer_dir>.json``) and the files of the
        layer, keeping only the files whose conditions, and the conditions of
        the layer, hold in the context.

        :param layer_dir: directory of the layer
        :param context: the mustache context of the new project
        """
        with open(f"{layer_dir}.json", encoding="UTF-8") as f:
            layer_info: dict = json.load(f)
        when = cast(When, layer_info.get("when"))
        filelist = cast(dict, layer_info.get("filelist", {}))

        sources: List[str] = []
        prefix = os.path.join(layer_dir, "")
        for curr_dir, dirs, files in os.walk(layer_dir):
            dirs[:] = [dirname for dirname in dirs if dirname not in ["__pycache__"]]
            files[:] = [
                filename
                for filename in files
                if os.path.splitext(filename)[1] not in [".pyc", ".pyo", ".pyd"]
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
        result.files = list(filter(lambda file: file.src in allowed_files, files))

        return result

    @property
    def name(self):
        """Name of the layer directory."""
        return os.path.basename(self.root)

    @property
    def pkg(self):
        """
        Name of the package providing the layer, shown before the layer files
        in the ``[pkg:name]`` header.
        """
        # <package>/template/layers/<layer>
        return os.path.basename(
            os.path.dirname(os.path.dirname(os.path.dirname(self.root)))
        )

    def template(self):
        """
        :returns: mustache template rendering the source paths of the files,
            which pass both their own and the layer's conditions
        """
        return _wrap_in_conditions(
            "".join(file.template() for file in self.files), self.when
        )

    def run(self, rt: env.Runtime, context: ctx.SettingsType):
        """
        Write all the files of the layer into the new project.

        :param rt: runtime used for messages and ``--dry-run``
        :param context: the mustache context of the new project
        """
        if not rt.silent:
            if rt.use_color:
                print(f"\033[2;30m[{self.pkg}:{self.name}]\033[m")
            else:
                print(f"[{self.pkg}:{self.name}]")
        for file in self.files:
            file.run(self.root, rt, context)
        if not rt.silent:
            print()

    def get_git_checks(self):
        """
        :returns: the files of the layer, which should be marked executable in
            Git
        """
        for file in self.files:
            for special in file.get_git_checks():
                yield special


def copy_license(rt: env.Runtime, context: ctx.SettingsType):
    """
    Write the ``LICENSE`` file chosen with ``COPY.LICENSE``, if any.

    :param rt: runtime used for messages and ``--dry-run``
    :param context: the mustache context of the new project
    """
    license = path_get(context, "COPY.LICENSE")
    if not license:
        return

    licenses_dir = os.path.abspath(
        os.path.join(ctx.package_root, ctx.template_dir, "licenses")
    )
    license_file = f"{license}.mustache"
    info = FileInfo(license_file, "LICENSE", is_mustache=True, is_executable=False)
    info.run(licenses_dir, rt, context)


def gather_package_layers(package_root: str, context: ctx.SettingsType):
    """
    Read all the layers of a package's template, i.e. the directories in
    ``template/layers`` with a JSON config next to them.

    :param package_root: directory of the package providing the template
    :param context: the mustache context of the new project
    :returns: the layers having any files left after filtering
    """
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
