# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import re
from typing import Iterator, List, NamedTuple, Optional

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


class Arg(NamedTuple):
    value: str
    offset: int


class Command(NamedTuple):
    name: str
    args: List[Arg]
    offset: int


class Project(NamedTuple):
    name: Arg
    version: Arg
    stability: Arg
    description: Arg

    @property
    def ver(self):
        return f"{self.version.value}{self.stability.value}"

    @property
    def pkg(self):
        return f"{self.name.value}-{self.ver}"

    @property
    def tag(self):
        return f"v{self.ver}"


def _token_stream(text: str) -> Iterator[Token]:
    tok_regex = "|".join("(?P<%s>%s)" % pair for pair in TOKENS)
    get_token = re.compile(tok_regex).match
    offset = 0

    mo = get_token(text)
    while mo is not None:
        token_type = mo.lastgroup
        if token_type not in ["COMMENT", "WS"]:
            value = mo.group(token_type)
            yield Token(type=token_type, value=value, offset=offset)
        offset = mo.end()
        mo = get_token(text, offset)


def _command(cmd: Token, stream: Iterator[Token]):
    result = Command(name=cmd.value, args=[], offset=cmd.offset)
    if next(stream)[0] != "OPEN":
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


def _cmake(filename: str):
    commands: List[Command] = []

    with open(filename, "r", encoding="UTF-8") as f:
        stream = _token_stream(f.read())
    for tok in stream:
        if tok.type == "IDENT":
            commands.append(_command(tok, stream))

    return commands


def get_project(dirname: str) -> Project:
    commands = _cmake(os.path.join(dirname, "CMakeLists.txt"))

    project_name: Optional[Arg] = None
    version = Arg("0.1.0", -1)
    version_stability: Optional[Arg] = None
    description = Arg("", -1)

    for cmd in commands:
        if cmd.name == "project":
            project_name = cmd.args[0]
            args = cmd.args[1:]
            project_dict = {
                name.value: value for name, value in zip(args[::2], args[1::2])
            }
            version = project_dict.get("VERSION", version)
            description = project_dict.get("DESCRIPTION", "")
            if version_stability is not None:
                break
        elif cmd.name == "set":
            var_name = cmd.args[0]
            if var_name.value == "PROJECT_VERSION_STABILITY":
                version_stability = cmd.args[1]
                if project_name is not None:
                    break

    if project_name is None:
        project_name = Arg("", -1)
    if version_stability is None:
        version_stability = Arg("", -1)

    project_version = Project(
        name=project_name,
        version=version,
        stability=version_stability,
        description=description,
    )

    return project_version
