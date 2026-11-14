.. _command-webidl-gen:

.. note::

   This command is part of ``proj_flow.ext.webidl`` extension.

``./flow webidl gen``
=====================

Synopsis
--------

.. code-block::

   $ ./flow webidl gen --cfg json-file --binary-dir project-binary-dir

Description
-----------

Run the mustache code generation on WebIDL definitions named in the config.
Each output is generated once per version, and each versioned output once for
all the versions.

Next to each generated file, there is a ``.json`` file with the full context
the template was rendered with. Files are only written, if their contents
change, so the build does not see unneeded updates.

The command is called by the build, through the rules written by
:ref:`webidl cmake<command-webidl-cmake>`, from the project source directory.

``--cfg json-file``
   The WebIDL generation config.

``--binary-dir project-binary-dir``
   Binary directory of the CMake project.

See also
--------

- :ref:`webidl<command-webidl>`, for the config format, the extended attributes and
  the template context
