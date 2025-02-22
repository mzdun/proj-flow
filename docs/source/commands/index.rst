Commands
========

Synopsis
--------

.. code-block::

   $ cxx-init [-h] [-v] [-C [dir]] command ...
   $ cxx-init command [-h] [--dry-run] [--silent | --verbose] ...

   $ ./flow [-h] [-v] [-C [dir]] command ...
   $ ./flow command [-h] [--dry-run] [--silent | --verbose] ...

Description
-----------

``-h`` / ``--help``
   Without the command, or before the command, show the help for proj-flow
   and exit. After the command, show the help for that command and exit.

``-v`` / ``--version``
   Show proj-flow's version and exit.

``-C dir``
   Run as if proj-flow was started in <dir> instead of the current working
   directory. This directory must exist.

``command``
   Name of the command or ``run`` alias to call.

``--dry-run``
   No persistent operations are performed: no files and directories are deleted,
   created nor changed; no network communication is performed.

   .. note::

      If the ``--dry-run`` is used through ``./flow`` helper, the helper may
      still create private virtual environment and install ``proj-flow`` package
      as needed.

``--silent``
   Output as little as possible. If an external tool is called, it is free to
   output whatever it wants.

``--verbose``
   Output even more output, than normal.

See also
--------

.. toctree::
   :maxdepth: 1

   init
   bootstrap
   run
   github-matrix
   github-release
   github-publish
   system
   list
