Flow config
===========

Flow config file is a YAML file saved as ``.flow/config.yml``. It is used by
various parts of *C++ flow* to negotiate some details with the project
maintainer.

``cmake``
---------

Settings used by various CMake-based steps.

``cmake.vars``
--------------

Object consisting of CMake variables, which should be used by the CMake
configuration step. Each key in the object is the name of the variable and
the corresponding value references the source of CMake variable value.

If the reference starts with a ``"?"``, then this variable is an ``"ON"`` /
``"OFF"`` variable, otherwise it will be a string variable. Then if the rest
of the reference starts with ``config:``, the config for current run will be
used to retrieve the value. Finally, if that start was ``runtime:``, the
:class:`Runtime<cxx_flow.api.env.Runtime>` object is queried for the value.

Currently the default value is passed through Mustache engine:

.. code-block:: yaml

    cmake:
      vars:
        {{NAME_PREFIX}}_COVERAGE: "?config:coverage"
        {{NAME_PREFIX}}_SANITIZE: "?config:sanitizer"
        {{NAME_PREFIX}}_CUTDOWN_OS: "?runtime:cutdown_os"

``compiler``
------------

An object containing knowledge about compilers used.

``compiler.names``
------------------

Names of the compilers to use, when configuring Conan and CMake with any
given compiler in the configuration from config matrix.

.. code-block:: yaml

    names:
      clang: [ clang, clang++ ]
      gcc: [ gcc, g++ ]

``compiler.names.<compiler>``
-----------------------------

A list of two items. First one will be used for ``$CC`` environment
variable, the other for ``$CXX`` variable.

.. code-block:: yaml

    [ clang, clang++ ]

.. code-block:: yaml

    [ gcc, g++ ]

.. warning::

    The environment modifications are not yet ported.

``compiler.os-default``
-----------------------

A map of default compilers for given platform, used, when ``$DEV_CXX``
environment variable is missing. Currently

.. code-block:: yaml

    { ubuntu: gcc, windows: msvc }

``entry``
---------

An object, where each key is an alias for ``run`` and each value is a list
of steps.

``entry.<alias>``
-----------------

List of step names, which should be run, when this alias is used as command.

``lts``
-------

An object used by ``ci matrix`` to expand various platform to lists of their
current LTS variants.

``lts.ubuntu``
--------------

A list of Ubuntu LTS systems. Currently

.. code-block:: yaml

    lts:
      ubuntu:
        - ubuntu-20.04
        - ubuntu-22.04
        - ubuntu-24.04

``package``
-----------

Object describing the details of behavior for Pack step.

``package.main-group``
----------------------

When CPack is configured to create an archive per component group, this will
name the group, which should be renamed to group-less filename. If missing, does
nothing.

``postproc``
------------

An object resembling fragment of flow matrix, but only excludes are being
read in current version.

``postproc.exclude``
--------------------

A list of matrix excludes to be applied after other matrix operations in
order to further limit the number of usable configurations. Currently, used
to limit configurations created by exploding the LTS platforms:

.. code-block:: yaml

    postproc:
      exclude:
        - { github_os: ubuntu-20.04, sanitizer: true }
        - { github_os: ubuntu-24.04, sanitizer: true }
        - { github_os: ubuntu-20.04, compiler: clang }

``shortcuts``
-------------

An object, whose keys represent flags in ``./flow run`` and whose values are
mapped to additional ``-D`` params.

.. code-block:: yaml

    shortcuts:
      dbg: { build_type: Debug, sanitizer: false }
      rel: { build_type: Release, sanitizer: false }
      both: { build_type: [ Debug, Release ], sanitizer: false }
      sane: { build_type: Debug, sanitizer: true }

.. _config-sign:

``sign``
--------

An object helping to decide what, if anything, should be signed during the
Sign and SignPackages steps.

``sign.directories``
--------------------

A list of directories, where the binaries to sign should be located. It prepends
the build directory, so if there is a ``"bin"`` directory and current config
works inside ``build/debug``, then the binaries should be located in
``build/debug/bin``. If missing, will default to

.. code-block:: python

    ["bin", "lib", "libexec", "share"]

``sign.exclude``
----------------

When browsing through ``sig.directories``, which binaries should *not* be
signed. When missing, defaults to

.. code-block:: python

    ["*-test"]
