.. _command-tests:

.. note::

   This command is part of ``proj_flow.ext.tests`` and
   ``proj_flow.ext.test_runner`` extensions.

``./flow tests``
================

Synopsis
--------

.. code-block::

   $ ./flow tests runner --preset CONFIG [--tests DIR] [--version SEMVER]
                         [--run [ID ...]] [--nullify]
                         [--ctrf CTRF] [--ctrf-report-name REPORT_NAME]
   $ RUN_LINEAR=1 POOL_SIZE=<threads> ./flow tests runner ...

Description
-----------

The ``tests`` command groups test helpers and runners. The group itself comes
from ``proj_flow.ext.tests`` extension, which also adds ``JUnitToCtrf`` and
``MergeCtrfFiles`` :doc:`run steps<../steps/index>`. The ``runner`` subcommand
comes from ``proj_flow.ext.test_runner`` extension.

``./flow tests runner``
-----------------------

Run the project's executable against a set of JSON test cases, checking its
stdout and stderr against expected values. The executable is looked up in the
``bin`` directory of the binary directory of given CMake preset.

``--preset CONFIG``
   Name of CMake build preset from ``CMakePresets.json``. The preset must have
   both ``binaryDir`` and ``CMAKE_BUILD_TYPE``.

``--tests DIR``
   *(optional)* Directory with the JSON test cases, relative to
   ``test-runner.testsuite.root``; test cases are enumerated recursively.
   Defaults to the root itself. If the directory does not exist, but
   a directory with the same name exists inside
   ``test-runner.testsuite.default-set``, that one is used.

``--version SEMVER``
   *(optional)* Version to patch the output with. Defaults to the current
   version of the project.

``--run [ID ...]``
   *(optional)* Run only the tests with these numbers. Numbers can be given as
   separate arguments or as a comma-separated list.

``--nullify``
   *(optional)* Do not run the tests. Instead, set the ``"expected"`` field of
   the selected test cases to ``null``.

``--ctrf CTRF``
   *(optional)* Write a `CTRF <https://ctrf.io>`_-compatible report to this
   file.

``--ctrf-report-name REPORT_NAME``
   *(optional)* Name of the CTRF report.

``$RUN_LINEAR``
   If set to anything but ``0``, run all tests one after another. Otherwise,
   only the tests marked as linear are run that way and all other tests are run
   in parallel.

``$POOL_SIZE``
   Number of threads running the tests in parallel. Defaults to twice the
   number of CPUs.

The runner is configured with :ref:`config-test-runner` section of the flow
config.

Running from CTest
::::::::::::::::::

The ``runner`` can be registered with CTest directly. Assuming
:ref:`command-init` generated a ``CMakeLists.txt`` with ``$MYPROJ_TESTING``
flag, and the presets are named after the lowercase build type, one way of
wiring the ``runner`` to the testing harness is:

.. code-block:: cmake

   find_package(Python3 COMPONENTS Interpreter REQUIRED)

   if (MYPROJ_TESTING)
     string(TOLOWER "${CMAKE_BUILD_TYPE}" TEST_RUNNER_PRESET)

     add_test(
       NAME ${PROJECT_NAME}-runner
       COMMAND "${Python3_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/.flow/flow.py"
         tests runner
         --preset "${TEST_RUNNER_PRESET}"
         --ctrf "${TEST_REPORT_DIR}/${PROJECT_NAME}-runner.json"
       WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
     )
   endif()

The ``WORKING_DIRECTORY`` is needed, because the runner reads both
``CMakePresets.json`` and the flow config from the current directory. Calling
``.flow/flow.py`` through ``${Python3_EXECUTABLE}`` works the same on all
platforms, where ``./flow`` would not.

With ``TEST_REPORT_DIR`` pointing to ``${PROJECT_BINARY_DIR}/test-results``,
as in a freshly-initialized project, the CTRF report lands in the default
``test.ctrf-dir`` and is picked up by the ``MergeCtrfFiles`` step.

.. note::

   CTest does not build anything, so the tested executable must be built
   before ``ctest`` is called, e.g. with ``./flow test``, which runs the Build
   step before the Test step.
