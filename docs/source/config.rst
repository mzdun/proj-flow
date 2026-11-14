Flow config
===========

Flow config file is a YAML file saved as ``.flow/config.yml`` (a ``.yaml`` or
``.json`` file is read as well). It is used by various parts of *Project Flow*
to negotiate some details with the project maintainer. Before reading the
project config, *Project Flow* reads the user config from
``~/.config/proj-flow.yml`` (or ``.yaml``, or ``.json``); the project config
is then merged over it.

``cmake``
---------

Settings used by various CMake-based steps.

.. _config-cmake-vars:

``cmake.vars``
--------------

Object consisting of CMake variables, which should be used by the CMake
configuration step. Each key in the object is the name of the variable and
the corresponding value references the source of CMake variable value.

If the reference starts with a ``"?"``, then this variable is an ``"ON"`` /
``"OFF"`` variable, otherwise it will be a string variable. Then if the rest
of the reference starts with ``config:``, the config for current run will be
used to retrieve the value. Finally, if that start was ``runtime:``, the
:class:`Runtime<proj_flow.api.env.Runtime>` object is queried for the value.

Currently the default value is passed through Mustache engine:

.. code-block:: yaml

    cmake:
      vars:
        {{NAME_PREFIX}}_COVERAGE: "?config:coverage"
        {{NAME_PREFIX}}_SANITIZE: "?config:sanitizer"
        {{NAME_PREFIX}}_CUTDOWN_OS: "?runtime:cutdown_os"
        {{NAME_PREFIX}}_W_ERROR: "?config:w-error"

The ``w-error`` is not a key in ``.flow/matrix.yml``, so it is ``OFF``, unless
added to the configs with ``./flow run -E w-error=on``.

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
Alternatively, an object with ``steps`` list and ``doc`` string, which will be
used as the help for the alias. Without the ``doc``, the help is
``Shortcut for "run -s <steps>"``.

.. code-block:: yaml

    entry:
      config: [ Conan, CMake ]
      docs:
        doc: Build the documentation
        steps: [ RTD ]

.. _config-extensions:

``extensions``
--------------

A list of Python modules to import, before any command is run. Each of them
can register new commands, steps, changelog generators, etc. Modules can be
taken from installed packages, or from the ``.flow/extensions`` directory of
the project.

.. code-block:: yaml

    extensions:
      - proj_flow.ext.github
      - proj_flow.ext.tests

The built-in extensions are:

``proj_flow.ext.cplusplus``
    Conan and CMake steps for C++ projects.
``proj_flow.ext.github``
    The :ref:`github<command-github-matrix>` commands.
``proj_flow.ext.python``
    Steps for Python projects; cannot be used together with
    ``proj_flow.ext.cplusplus``.
``proj_flow.ext.markdown_changelog`` / ``proj_flow.ext.re_structured_changelog``
    Changelog in ``CHANGELOG.md`` or ``CHANGELOG.rst`` format.
``proj_flow.ext.sign``
    Sign and SignPackages steps.
``proj_flow.ext.store``
    StoreTests, StorePackages and Store steps.
``proj_flow.ext.tests``
    The :ref:`tests<command-tests>` command, JUnitToCtrf and MergeCtrfFiles
    steps.
``proj_flow.ext.test_runner``
    The :ref:`tests runner<command-tests>` command.
``proj_flow.ext.tools``
    The :ref:`tools<command-tools>` commands.
``proj_flow.ext.webidl``
    The :ref:`webidl<command-webidl>` commands.

.. _config-lts:

``lts``
-------

An object used by ``ci matrix`` to expand various platform to lists of their
current LTS variants.

``lts.ubuntu``
--------------

.. deprecated:: 0.13

    Remove this list from the config; the Ubuntu LTS systems are taken from
    the list of GitHub runners, see :ref:`command-github-matrix`.

A list of Ubuntu LTS systems, e.g.

.. code-block:: yaml

    lts:
      ubuntu:
        - ubuntu-22.04
        - ubuntu-24.04

``lts.windows``
---------------

A list of Windows Server systems available as GitHub runners. Unlike Ubuntu,
this list is not downloaded, so without it, ``"windows"`` configs run on
``windows-latest``. Currently, the runners are:

.. code-block:: yaml

    lts:
      windows:
        - windows-2022
        - windows-2025-vs2026
        - windows-2025
        - windows-11-arm

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
        - { github_os: ubuntu-24.04, sanitizer: true }
        - { github_os: ubuntu-24.04, compiler: clang }

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

.. _config-test:

``test``
--------

An object used by the JUnitToCtrf and MergeCtrfFiles steps from
``proj_flow.ext.tests`` extension. All the directories are relative to the
build directory of current config.

``test.gtest-dir`` / ``test.junit-dir`` / ``test.junit-dirs``
    A directory, or a list of directories, with JUnit XML reports to convert.
``test.ctrf-dir``
    A directory for converted CTRF JSON files. Defaults to ``test-results``.
``test.ctrf-report``
    The merged CTRF report. Defaults to ``ctrf-tests.json``.

.. _config-test-runner:

``test-runner``
---------------

An object used by the ``./flow tests runner`` command from
``proj_flow.ext.test_runner`` extension.

``test-runner.target``
    *(required)* Name of the executable to test, without the ``.exe``
    extension.
``test-runner.install``
    A list of CMake install components to install before the tests are run.
``test-runner.patches``
    An object of built-in patches applied to output of the tested program.
``test-runner.report_env``
    Prefix of environment variables to report together with the tests.
``test-runner.testsuite.root``
    *(required)* A directory with the JSON test cases.
``test-runner.testsuite.data``
    A directory with the data for the tests, relative to the root.
``test-runner.testsuite.default-set``
    A subdirectory of the root to look into, when ``--tests`` does not name
    a directory directly under the root.

Each test case is a JSON or YAML file described by the
``schema/test-runner.yaml`` JSON schema from *Project Flow* repository.

``version-updates``
-------------------

An object used by ``proj_flow.minimal.ext.versions`` extension during
``./flow github release``. Each key is a path of a file and each value is
a text containing ``$VERSION``. When the version changes, the text with
previous version is replaced with the text with new version in that file.

.. code-block:: yaml

    version-updates:
      schema/test-runner.yaml: tags/v$VERSION/
