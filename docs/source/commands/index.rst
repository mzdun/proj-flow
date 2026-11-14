Commands
========

Synopsis
--------

.. code-block::

   $ proj-flow [-h] [-v] [-C [dir]] command ...
   $ proj-flow command [-h] [--dry-run] [--silent | --verbose] ...

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
   Name of the command or ``run`` alias to call. Commands, which group other
   commands (e.g. ``github``), need the name of the subcommand as well; called
   without one, they print an error together with the list of their
   subcommands.

   Some of the commands are only available, if the extension providing them is
   listed in the :ref:`config-extensions` section of the flow config.

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
   tests
   tools
   webidl
