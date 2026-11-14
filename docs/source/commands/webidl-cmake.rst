.. _command-webidl-cmake:

.. note::

   This command is part of ``proj_flow.ext.webidl`` extension.

``./flow webidl cmake``
=======================

Synopsis
--------

.. code-block::

   $ ./flow webidl cmake --cfg json-file --binary-dir project-binary-dir [--target name]

Description
-----------

Write the CMake configuration based on given config. The resulting
``<config>.cmake`` file, e.g. ``idl/model.json.cmake`` in the current binary
directory:

- adds all the generated files to the sources of the target,
- runs :ref:`webidl gen<command-webidl-gen>` to build them, using the dependency file
  from :ref:`webidl depfile<command-webidl-depfile>` to know when to rebuild them,
- re-runs this command and :ref:`webidl depfile<command-webidl-depfile>`, when the config
  changes.

The command is called by ``add_webidl_generation()`` from
:ref:`webidl init<command-webidl-init>`, from the project source directory.

``--cfg json-file``
   The WebIDL generation config.

``--binary-dir project-binary-dir``
   Binary directory of the CMake project.

``--target name``
   *(optional)* Name of the target to add generated files to.

See also
--------

- :ref:`webidl<command-webidl>`, for the config format
