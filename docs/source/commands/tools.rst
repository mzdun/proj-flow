.. _command-tools:

.. note::

   This command is part of ``proj_flow.ext.tools`` extension.

``./flow tools``
================

Synopsis
--------

.. code-block::

   $ ./flow tools pragma-once
   $ ./flow tools run-linter [--log_level {ERROR,WARN,NOTICE,INFO,DEBUG}]

Description
-----------

The ``tools`` command groups various C++ tools and helpers.

``./flow tools pragma-once``
----------------------------

Check that ``#pragma once`` is present in all C and C++ headers (``.h``,
``.h++``, ``.hh``, ``.hpp`` and ``.hxx``) and absent from all source files
(``.c``, ``.c++``, ``.cc``, ``.cpp`` and ``.cxx``). The ``.git`` and ``build``
directories are skipped. Each file breaking the rule is printed.

``./flow tools run-linter``
---------------------------

Run the dockerized `super-linter <https://github.com/super-linter/super-linter>`_
locally, with the same settings, as the GitHub workflows of the project. All
the ``.github/workflows`` files are searched for steps using super-linter and
each such step is run through ``docker run``, with the ``env`` of the step
passed to the container. Values referencing ``${{ ... }}`` expressions are
skipped. The downloaded super-linter action definitions are cached in
``build/cache_db``.

``--log_level {ERROR,WARN,NOTICE,INFO,DEBUG}``
   *(optional)* Log level of super-linter. Defaults to ``INFO``.
