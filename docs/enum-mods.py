#!/usr/bin/env python

import os
from typing import Dict

import chevron

apidir = os.path.abspath(os.path.join(__file__, "..", "source", "api"))
tmpltdir = os.path.abspath(os.path.join(__file__, "..", "template"))


def load(template):
    with open(
        os.path.abspath(os.path.join(__file__, "..", "template", template)),
        encoding="utf-8",
    ) as mstch:
        return mstch.read()


def render(template: str, name: str, ctx):
    txt = chevron.render(template, ctx)

    with open(os.path.join(apidir, f"{name}.rst"), "w", encoding="UTF-8") as rst:
        rst.write(txt)


def all_modules():
    root = os.path.abspath(os.path.join(__file__, "../.."))
    prefix = os.path.join(root, "")
    for current, dirnames, filenames in os.walk(os.path.join(root, "cxx_flow")):
        dirnames[:] = [dirname for dirname in dirnames if dirname != "__pycache__"]

        parent = current[len(prefix) :].replace(os.sep, ".")

        for filename in filenames:
            mod, ext = os.path.splitext(filename)
            if ext != ".py":
                continue
            if mod == "__init__":
                if "." in parent:
                    yield parent
                continue
            if mod.startswith("__"):
                continue
            yield f"{parent}.{mod}"


def package_tree():
    modules = {
        mod: {"name": mod, "underline": "=" * len(mod)} for mod in sorted(all_modules())
    }

    modules["cxx_flow"] = {}

    for mod in modules:
        try:
            self = modules[mod]
            parent_name = ".".join(self["name"].split(".")[:-1])
            parent = modules[parent_name]
        except KeyError:
            continue
        try:
            parent["children"].append(self)
        except KeyError:
            parent["children"] = [self]

    for mod in modules:
        self = modules[mod]
        try:
            children = self["children"]
            self["children"] = list(sorted(children, key=lambda obj: obj["name"]))
            self["has_children"] = len(children) > 0
        except KeyError:
            continue

    return modules


def render_autodocs(modules: Dict[str, dict]):
    render(
        load("api.index.rst.mustache"),
        "index",
        {"module": modules["cxx_flow"]["children"]},
    )

    del modules["cxx_flow"]

    template = load("api.rst.mustache")
    for mod in modules:
        render(template, mod, modules[mod])

    print(f"Wrote {len(modules)} modules")


def main():
    for root, dirnames, filenames in os.walk(apidir):
        dirnames[:] = []

        for filename in filenames:
            if os.path.splitext(filename)[1] != ".rst":
                continue
            os.remove(os.path.join(root, filename))

    modules = package_tree()
    render_autodocs(modules)


if __name__ == "__main__":
    main()
