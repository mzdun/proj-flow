.. _template:

Directory template
==================

*Project Flow* directory template consist of layers. Each layer will be used
only if a switch is turned on in the mustache context (if that switch is named
in layer config). Every file, whose extension is ``.mustache``, will have this
extension removed while copying the file to its destination, with the contents
processed by mustache engine.

Mustache context
----------------

Currently, a handful of ``proj-flow init`` settings are defined, each building
the mustache context a bit.

.. _interactive-settings:

Interactive settings
::::::::::::::::::::

Each setting defaults to first value, if it represents a list, or the current
value itself if is is a scalar.

+-------------------------+----------------------------------------------------+
| Context path            | Interactive label and values                       |
+=========================+====================================================+
| ``PROJECT.NAME``        | Project name                                       |
|                         |                                                    |
|                         | *Current directory name*                           |
+-------------------------+----------------------------------------------------+
| ``PROJECT.DESCRIPTION`` | Project description                                |
|                         |                                                    |
|                         | *Empty*                                            |
+-------------------------+----------------------------------------------------+
| ``PROJECT.EMAIL``       | Valid email, e.g. for CODE_OF_CONDUCT              |
|                         |                                                    |
|                         | *Result of calling* ``git config user.email``      |
+-------------------------+----------------------------------------------------+
| ``COPY.YEAR``           | Year for copyright notices                         |
|                         |                                                    |
|                         | *Current year*                                     |
+-------------------------+----------------------------------------------------+
| ``COPY.HOLDER``         | Holder of the copyright                            |
|                         |                                                    |
|                         | *Result of calling* ``git config user.name``       |
+-------------------------+----------------------------------------------------+
| ``COPY.LICENSE``        | License                                            |
|                         |                                                    |
|                         | *one of*                                           |
|                         |                                                    |
|                         | - ``MIT``                                          |
|                         | - ``0BSD``                                         |
|                         | - ``Unlicense``                                    |
|                         | - ``WTFPL``                                        |
|                         | - ``Zlib``                                         |
+-------------------------+----------------------------------------------------+
| ``INCLUDE_PREFIX``      | Prefix for includes (as in #include                |
|                         | "{PREFIX}/version.hpp")                            |
|                         |                                                    |
|                         | *Current value of* ``PROJECT.NAME`` *context*      |
+-------------------------+----------------------------------------------------+
| ``NAME_PREFIX``         | CMake variable name prefix                         |
|                         |                                                    |
|                         | *Current value of* ``PROJECT.NAME``, *upper cased  |
|                         | and safe for variable names*                       |
+-------------------------+----------------------------------------------------+
| ``NAMESPACE``           | C++ namespace for the project                      |
|                         |                                                    |
|                         | *Current value of* ``PROJECT.NAME``, *safe for C++ |
|                         | identifiers*                                       |
+-------------------------+----------------------------------------------------+
| ``EXT``                 | Extension for code files                           |
|                         |                                                    |
|                         | *one of*                                           |
|                         |                                                    |
|                         | - ``.cpp``                                         |
|                         | - ``.cc``                                          |
|                         | - ``.cxx``                                         |
|                         |                                                    |
|                         | `(see note)`                                       |
+-------------------------+----------------------------------------------------+
| ``SRCDIR``              | Directory for code files                           |
|                         |                                                    |
|                         | ``src``                                            |
+-------------------------+----------------------------------------------------+
| ``INCLUDEDIR``          | Directory for include files                        |
|                         |                                                    |
|                         | ``include`` `(see note)`                           |
+-------------------------+----------------------------------------------------+
| ``PROJECT.TYPE``        | CMake project type                                 |
|                         |                                                    |
|                         | *one of*                                           |
|                         |                                                    |
|                         | - ``console-application``                          |
|                         | - ``win32-application``                            |
|                         | - ``static-library``                               |
|                         | - ``shared-library``                               |
|                         | - ``plugin-library``                               |
|                         |                                                    |
|                         | `(see note)`                                       |
+-------------------------+----------------------------------------------------+

.. note::

    During the interactive phase, the ``EXT`` context is a string holding one of
    the three code extensions, but afterwards it is removed and replaced with
    an object consisting of ``EXT.cxx`` (holding the original extension) and
    ``EXT.hxx`` (holding matching header extension, one of ``.hpp``, ``.hh`` and
    ``.hxx``).

.. note::

    The ``INCLUDEDIR`` context default value is ``"include"``, but after
    the interactive phase it is amended to ``"{INCLUDEDIR}/{INCLUDE_PREFIX}"``.

.. note::

    During the post process phase, ``PROJECT.TYPE`` context is used to add a
    ``cmake`` context according to mapping below:

    +-------------------------+-------------------------------------+
    | Project type            | ``cmake`` context                   |
    +=========================+=====================================+
    | ``console-application`` | .. code-block:: json                |
    |                         |                                     |
    |                         |    {                                |
    |                         |        "cmd": "add_executable",     |
    |                         |        "type": "",                  |
    |                         |        "console-application": true, |
    |                         |        "console": true,             |
    |                         |        "application": true,         |
    |                         |        "link_access": "PRIVATE",    |
    |                         |    },                               |
    |                         |                                     |
    +-------------------------+-------------------------------------+
    | ``win32-application``   | .. code-block:: json                |
    |                         |                                     |
    |                         |    {                                |
    |                         |        "cmd": "add_executable",     |
    |                         |        "type": " WIN32",            |
    |                         |        "win32-application": true,   |
    |                         |        "win32": true,               |
    |                         |        "application": true,         |
    |                         |        "link_access": "PRIVATE",    |
    |                         |    },                               |
    |                         |                                     |
    +-------------------------+-------------------------------------+
    | ``static-library``      | .. code-block:: json                |
    |                         |                                     |
    |                         |    {                                |
    |                         |        "cmd": "add_library",        |
    |                         |        "type": " STATIC",           |
    |                         |        "static-library": true,      |
    |                         |        "static": true,              |
    |                         |        "library": true,             |
    |                         |        "link_access": "PUBLIC",     |
    |                         |    },                               |
    |                         |                                     |
    +-------------------------+-------------------------------------+
    | ``shared-library``      | .. code-block:: json                |
    |                         |                                     |
    |                         |    {                                |
    |                         |        "cmd": "add_library",        |
    |                         |        "type": " SHARED",           |
    |                         |        "shared-library": true,      |
    |                         |        "shared": true,              |
    |                         |        "library": true,             |
    |                         |        "link_access": "PUBLIC",     |
    |                         |    },                               |
    |                         |                                     |
    +-------------------------+-------------------------------------+
    | ``plugin-library``      | .. code-block:: json                |
    |                         |                                     |
    |                         |    {                                |
    |                         |        "cmd": "add_library",        |
    |                         |        "type": " MODULE",           |
    |                         |        "plugin-library": true,      |
    |                         |        "plugin": true,              |
    |                         |        "library": true,             |
    |                         |        "link_access": "PUBLIC",     |
    |                         |    },                               |
    |                         |                                     |
    +-------------------------+-------------------------------------+

.. _interactive-switches:

Interactive switches
::::::::::::::::::::

Switches are used mostly to guard inclusion of various template layers. Each of
them allows true/false answers and all are ``true`` by default. The interactive
prompts accept ``yes``, ``on`` and ``1`` for true value, and ``no``, ``off``
and ``0`` for false value.

+-------------------------+--------------------------------------------------+
| Context switch          | Interactive label                                |
+=========================+==================================================+
| ``with_conan``          | Use Conan for dependency manager                 |
+-------------------------+--------------------------------------------------+
| ``with_cmake``          | Use CMake                                        |
+-------------------------+--------------------------------------------------+
| ``with_github_actions`` | Use Github Actions                               |
+-------------------------+--------------------------------------------------+
| ``with_github_social``  | Use Github ISSUE_TEMPLATE, CONTRIBUTING.md, etc. |
+-------------------------+--------------------------------------------------+

.. _non-interactive-settings:

Non-interactive settings
::::::::::::::::::::::::

In addition to above, there are some context settings, which are only calculated
after the interactive phase. With already mentioned, those are:

+------------------------------+--------------------------------+
| Context path                 | Value source                   |
+==============================+================================+
| ``EXT.cxx``                  | *Current value of* ``EXT``     |
+------------------------------+--------------------------------+
| ``EXT.hxx``                  | *Header analogue for* ``EXT``  |
+------------------------------+--------------------------------+
| ``cmake``                    | *Object mapped using*          |
|                              | ``PROJECT.TYPE``               |
+------------------------------+--------------------------------+
| ``${``                       | ``"${"``                       |
+------------------------------+--------------------------------+
| ``CMAKE_VERSION``            | ``"3.28"``                     |
+------------------------------+--------------------------------+
| ``PROJECT.WIX.UPGRADE_GUID`` | ``uuid.uuid4()``               |
+------------------------------+--------------------------------+

.. note::

    The ``${`` context path is useful in mustached CMake scripts, where a
    variable reference would start with a mustache replacement. In such case

    .. code-block::

        ${{{PREFIX}}_SUFFIX}

    would result in bad context lookup. This could be fixed with a

    .. code-block::

        {{${}}{{PREFIX}}_SUFFIX}

    which would replace ``${`` with itself, the ``PREFIX`` with its proper
    value, rendering the whole thing as a proper CMake variable expression.

Layer schema
------------

For a given layer directory, there exists a JSON config named after the
directory (e.g. ``layer.json`` for ``layer/``). Each config must be a JSON
object with each property is optional (so a minimal config would be just
an empty object, or ``{}``).

``when``
    If present, names a mustache context, which must be true-ish in order for
    any file to be copied over. If this property is missing, the layer is always
    added to the project.
``filelist``
    If present, it is an object allowing special treatment of files in the
    layer. Any file not mentioned here will be treated as if both their ``when``
    and ``path`` were missing. If this property is missing, it will be treated
    as an empty object, as if all files in layer were missing from it.
``filelist.<in-layer-path>.when``
    If present, names a mustache context, which must be true-ish in order for
    *this file* to be copied over. If this property is missing, the file is
    added as if naming an always-true context.
``filelist.<in-layer-path>.path``
    If present, names a mustache expression, which will be used for destination
    filename. If this property is missing, the source filename is used, with
    the `.mustache` extension removed as needed.

Layer example
-------------

.. code-block::
    :caption: Layer listing

    +- layer/
       +- code/
       |  +- main.mustache
       |  +- header.mustache
       +- flow
       +- flow.cmd
       +- README.md.mustache

.. code-block:: json
    :caption: layer.json

    {
        "filelist": {
            "code/main.mustache": {
                "path": "{{SRCDIR}}/main{{EXT.cxx}}",
                "when": "cmake.application"
            },
            "code/header.mustache": {
                "path": "{{INCLUDEDIR}}/main{{EXT.hxx}}",
            }
        }
    }

.. code-block:: json
    :caption: Mustache context

    {
        "EXT": { "cxx": "cpp", "hxx": "hpp" },
        "SRCDIR": "source",
        "INCLUDEDIR": "include/project",
        "cmake": { "application": false }
    }

.. code-block::
    :caption: Layer listing

    +- project/
       +- include/
       |  +- project/
       |     +- main.hpp
       +- flow
       +- flow.cmd
       +- README.md

Here, both ``include/project/main.hpp`` and ``README.md`` are filtered through
the mustache engine and other files copied directly. If the
``cmake.application`` context was true, the project directory would have an
additional ``source/main.cpp`` file rendered from ``layer/code/main.mustache``.
