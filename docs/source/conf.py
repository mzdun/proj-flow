# Configuration file for the Sphinx documentation builder.

# -- Project information
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(__file__, "../../../src")))

import proj_flow

project = "Project Flow"
copyright = "2025, Marcin Zdun"
author = "Marcin Zdun"

release = ".".join(proj_flow.__version__.split(".", 2)[:2])
version = proj_flow.__version__

# -- General configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]

# -- Options for HTML output

html_theme = "sphinx_rtd_theme"

# -- Options for EPUB output
epub_show_urls = "footnote"

autodoc_member_order = "bysource"


# -- Signatures of @arg.command() functions
#
# Command functions declare their CLI arguments with
# ``typing.Annotated[T, arg.Argument(...)]``. The runtime needs those
# annotations, but in the API docs they only add noise (the argument help is
# already rendered as ``:param:`` by the decorator), so show the bare ``T``.


def _strip_annotated(annotation):
    import typing

    if typing.get_origin(annotation) is typing.Annotated:
        return typing.get_args(annotation)[0]
    return annotation


def _process_signature(app, what, name, obj, options, signature, return_annotation):
    if what not in ("function", "method") or not signature:
        return None
    if "Annotated" not in signature:
        return None

    import inspect

    from sphinx.util.inspect import stringify_signature

    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return None

    params = [
        param.replace(annotation=_strip_annotated(param.annotation))
        for param in sig.parameters.values()
    ]
    sig = sig.replace(parameters=params)

    show_annotation = app.config.autodoc_typehints in ("both", "signature")
    unqualified = app.config.autodoc_typehints_format == "short"
    stripped = stringify_signature(
        sig,
        show_annotation=show_annotation,
        show_return_annotation=False,
        unqualified_typehints=unqualified,
    )
    return stripped, return_annotation


# -- Builtin types in annotations
#
# Sphinx resolves an unknown ``class`` reference (e.g. the builtin ``type`` in
# ``t: type``) by falling back to attributes, matching any documented object,
# whose name ends with the target. This links the builtin ``type`` to fields
# like ``Argument.type`` or ``Commit.type``. Leave such references to
# intersphinx instead, unless the project itself defines the name.


def _patch_builtin_class_refs():
    import builtins

    from sphinx.domains.python import PythonDomain

    resolve_xref = PythonDomain.resolve_xref

    def resolve_builtin_aware(self, env, fromdocname, builder, type, target, *args):
        if (
            type == "class"
            and isinstance(getattr(builtins, target, None), builtins.type)
            and target not in self.objects
        ):
            return None
        return resolve_xref(self, env, fromdocname, builder, type, target, *args)

    PythonDomain.resolve_xref = resolve_builtin_aware


def setup(app):
    app.connect("autodoc-process-signature", _process_signature)
    _patch_builtin_class_refs()
