# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.cmake.parser** contains simple CMake parser.
"""

import os
import re
from pathlib import Path
from typing import Iterator, List, NamedTuple, Optional

from proj_flow.api.release import NO_ARG, Arg

TOKENS = [
    ("COMMENT", r"#.*"),
    ("STR", r'"[^"]*"'),
    ("OPEN", r"\("),
    ("CLOSE", r"\)"),
    ("IDENT", r'[^ \t\r\n()#"]+'),
    ("WS", r"\s+"),
]


class Token(NamedTuple):
    type: str
    value: str
    offset: int


class Command(NamedTuple):
    name: str
    args: List[Arg]
    offset: int


class CMakeProject(NamedTuple):
    name: Arg
    version: Arg
    stability: Arg
    description: Arg


def _token_stream(text: str) -> Iterator[Token]:
    tok_regex = "|".join("(?P<%s>%s)" % pair for pair in TOKENS)
    get_token = re.compile(tok_regex).match
    offset = 0

    mo = get_token(text)
    while mo is not None:
        token_type = mo.lastgroup
        if not token_type:
            break
        if token_type not in ["COMMENT", "WS"]:
            value = mo.group(token_type)
            yield Token(type=token_type, value=value, offset=offset)
        offset = mo.end()
        mo = get_token(text, offset)


def _command(cmd: Token, stream: Iterator[Token]):
    result = Command(name=cmd.value, args=[], offset=cmd.offset)
    tok = next(stream, None)
    if tok is None or tok.type != "OPEN":
        return result
    for tok in stream:
        if tok.type == "CLOSE":
            break
        elif tok.type == "OPEN":
            continue
        elif tok.type == "STR":
            result.args.append(Arg(value=tok.value[1:-1], offset=tok.offset + 1))
        elif tok.type == "IDENT":
            result.args.append(Arg(value=tok.value, offset=tok.offset))
        else:
            print(tok)

    return result


def _cmake(filename: Path):
    commands: List[Command] = []

    with open(filename, "r", encoding="UTF-8") as f:
        stream = _token_stream(f.read())
    for tok in stream:
        if tok.type == "IDENT":
            commands.append(_command(tok, stream))

    return commands


def _patch(directory: str, arg: Arg, value: str):
    with open(
        os.path.join(directory, "CMakeLists.txt"), "r", encoding="UTF-8"
    ) as input:
        text = input.read()

    patched = text[: arg.offset] + value + text[arg.offset + len(arg.value) :]

    with open(
        os.path.join(directory, "CMakeLists.txt"), "w", encoding="UTF-8"
    ) as input:
        input.write(patched)


_SINGLE_VALUE_KEYWORDS = ["VERSION", "DESCRIPTION", "HOMEPAGE_URL"]


def _project_keywords(args: List[Arg]):
    # Only the single-value keywords take the next argument as their value;
    # anything else, e.g. LANGUAGES with its list of languages, is skipped
    # one argument at a time.
    result: dict[str, Arg] = {}
    index = 0
    while index < len(args):
        name = args[index].value
        if name in _SINGLE_VALUE_KEYWORDS and index + 1 < len(args):
            result[name] = args[index + 1]
            index += 2
            continue
        index += 1
    return result


def get_project(dirname: Path) -> Optional[CMakeProject]:
    """
    Read the project information from ``CMakeLists.txt`` in given directory.
    The name, ``VERSION`` and ``DESCRIPTION`` are taken from the
    first ``project()`` command and the stability from the
    ``set(PROJECT_VERSION_STABILITY ...)`` command. A missing version
    defaults to ``0.1.0`` and missing stability and description default to
    :data:`proj_flow.api.release.NO_ARG`.

    :param dirname: directory containing the ``CMakeLists.txt``
    :returns: the project information with offsets of each value in the
        file, or ``None``, if there is no ``CMakeLists.txt`` or it has no
        ``project()`` command
    """
    try:
        commands = _cmake(dirname / "CMakeLists.txt")
    except FileNotFoundError:
        return None

    project_name: Optional[Arg] = None
    version = Arg("0.1.0", -1)
    version_stability: Optional[Arg] = None
    description = NO_ARG

    for cmd in commands:
        if cmd.name == "project" and project_name is None and cmd.args:
            project_name = cmd.args[0]
            project_dict = _project_keywords(cmd.args[1:])
            version = project_dict.get("VERSION", version)
            description = project_dict.get("DESCRIPTION", description)
            if version_stability is not None:
                break
        elif cmd.name == "set" and len(cmd.args) > 1:
            var_name = cmd.args[0]
            if var_name.value == "PROJECT_VERSION_STABILITY":
                version_stability = cmd.args[1]
                if project_name is not None:
                    break

    if project_name is None:
        return None
    if version_stability is None:
        version_stability = NO_ARG

    return CMakeProject(
        name=project_name,
        version=version,
        stability=version_stability,
        description=description,
    )
