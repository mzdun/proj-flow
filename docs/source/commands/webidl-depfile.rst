.. _command-webidl-depfile:

.. note::

   This command is part of ``proj_flow.ext.webidl`` extension.

``./flow webidl depfile``
=========================

Synopsis
--------

.. code-block::

   $ ./flow webidl depfile --cfg json-file --binary-dir project-binary-dir [--out dependency-file]

Description
-----------

Write the Makefile-style dependency file, which lists, for each generated
file, the config, the WebIDL files and the mustache template it is built
from. CMake generators use it to know when to regenerate the code.

The command is called by ``add_webidl_generation()`` from
:ref:`webidl init<command-webidl-init>`, from the project source directory.

``--cfg json-file``
   The WebIDL generation config.

``--binary-dir project-binary-dir``
   Binary directory of the CMake project.

``--out dependency-file``
   *(optional)* Output path of the dependency file. Defaults to
   ``<config>.deps`` in the current binary directory, e.g.
   ``idl/model.json.deps``.

See also
--------

- :ref:`webidl<command-webidl>`, for the config format
