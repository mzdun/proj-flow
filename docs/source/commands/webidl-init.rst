.. _command-webidl-init:

.. note::

   This command is part of ``proj_flow.ext.webidl`` extension.

``./flow webidl init``
======================

Synopsis
--------

.. code-block::

   $ ./flow webidl init

Description
-----------

Copy ``flow_webidl.cmake`` to ``.flow/cmake``. The file is only written, if
it is missing or differs from the one in the installed *Project Flow*, so
calling this command again updates the helper after an upgrade.

After including it in the project's CMake files with
``include(flow_webidl)``, the ``add_webidl_generation(TARGET CONFIG)``
function calls the :ref:`webidl cmake<command-webidl-cmake>` and
:ref:`webidl depfile<command-webidl-depfile>` commands for given JSON config, at
configuration time, and includes the resulting CMake file.

See also
--------

- :ref:`webidl<command-webidl>`, for a complete example
