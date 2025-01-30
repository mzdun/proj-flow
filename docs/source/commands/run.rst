.. _command-run:

``./flow run``
=================

Synopsis
--------

.. code-block::

   $ ./flow run [--dry-run] [-D [config ...]] [--official] [-s [step ...]]

Description
-----------

The `./flow run` command is the heart of daily work with *C++ flow*. Depending on
which steps are taken and which configs are selected, various flows are
performed. For instance, calling

.. code-block:: console

    $ ./flow run -s Conan,CMake -Dos=ubuntu -Dcompiler=gcc -Dbuild_type=Debug -Dbuild_type=Release -Dsanitizer=off

will configure Conan dependencies and CMake build directory for both Debug and
Release build, using Ninja build system, with no sanitizer. However, this
incantation is quite mouthful. It is so long, the browser needs to add a
scrollbar to display it.

The *C++ flow* addresses this in three ways. First, the aliases. They list
number of steps they represent and are configurable through flow config file in
``"entry"`` object. It so happens, that alias named "config" covers those two
steps, changing the call to

.. code-block:: console

    $ ./flow config -Dos=ubuntu -Dcompiler=gcc -Dbuild_type=Debug -Dbuild_type=Release -Dsanitizer=off

Second approach is done through definition shortcuts which *C++ flow* reads from
the same config file, this time from object named ``"shortcuts"``. Again, in a
freshly-initialized config file, there is a shortcut named "both", covering both
Debug and Release builds with sanitizer turned off. Since the shortcut names are
added to ``./flow run`` as switches, the call changes to

.. code-block:: console

    $ ./flow config -Dos=ubuntu -Dcompiler=gcc --both

Third approach deals with expected toolset. Shortcuts are not used in GitHub
workflow, they are designed to be used specifically in day-to-day work by
developers. The day-to-day work is performed mostly on dev machine, so the "os"
is sort-of predefined. With matching "compiler" (with the meaning of *matching*
taken from flow config file, from under ``"compiler.os-default"``), each
non-empty shortcut (such as ``--both``) id extended with two additional configs.
So, ``--both``, ``--dev``, ``--rel`` and all other shortcuts would get
``-Dos=ubuntu -Dcompiler=gcc`` on Ubuntu and ``-Dos=windows -Dcompiler=msvc``
on Windows. As a result, to configure Conan and Clang for both Debug and Release,
for current OS and compiler, the call becomes:

.. code-block:: console

    $ ./flow config --both

Similarly, to build Debug binaries, the ``./flow run`` incantation would be

.. code-block:: console

    $ ./flow config --dev

.. note::

    The ``clang`` selection is not yet ported from original project, but it is
    planned.

``-D config``
    Adds a positive filter to the cartesian product of all possible
    configurations. The ``config`` has a form of ``key=value``, where the key
    is one of the keys into ``"matrix"`` object in ``.flow/matrix.json``
    definition and the value is one of the possible values for that key. In case
    of boolean flags, such as ``sanitizer``, the true value is one of "true",
    "on", "yes", "1" and "with-<key>", i.e. "with-sanitizer" for sanitizer.

    When building a cartesian product stretched over all matrix keys of all
    usable configs, by default all the possible values for this key are taken.
    But as soon as, for a given key, it will appear in one of the ``-D`` params,
    that axis will only contain the values from ``-D`` params and not the matrix
    definition.

``--official``
    If preset, it will further reduce the size of cartesian product of usable
    configs by merging matrix definition in ``.flow/matrix.json`` with
    ``.flow/official.json``.

``-s step`` / ``--step step``
    List any number of steps to perform during this run.
