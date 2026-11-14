.. _command-bootstrap:

``./flow bootstrap``
====================

Synopsis
--------

.. code-block::

   $ ./flow bootstrap [--no-venv]
   $ GITHUB_ENV=<file path> ./flow bootstrap

Description
-----------

This command does nearly nothing, but when it is paired with ``./flow`` helper,
it is the simplest way to finish ``proj-flow`` bootstrapping, where the helper
creates a virtual environment as needed and installs a compatible version of
the package.

In case a ``$GITHUB_ENV`` environment variable is defined, when this command is
ran, the current value of ``$PATH`` environment variable is stored in file
pointed to by the ``$GITHUB_ENV`` variable. As a result, each step in current
GitHub workflow job will have current virtual environment activated as well.

Both those features are used by ``.github/workflows/build.yml`` file generated
by :ref:`command-init` in ``build`` job, so that all :ref:`command-run`
commands following the bootstrap share the same *Project Flow* installation.

Finally, the command warns about GitHub workflow jobs, which run *Project Flow*
on a Python version it does not support. A job runs *Project Flow*, if it uses
the ``proj-flow-actions/bootstrap`` action, or if any of its ``run`` scripts
calls ``proj-flow``, ``python -m proj_flow``, ``.flow/flow.py`` or ``./flow``.
The Python version of such a job is taken from the ``python-version`` of its
``actions/setup-python`` and ``proj-flow-actions/bootstrap`` steps, from their
``python-version-file``, or from ``.python-version``. For instance, with
*Project Flow* requiring Python 3.12 or newer:

.. code-block:: console

   $ ./flow bootstrap
   -- Flow is now ready
   -- .github/workflows/build.yml: job `build`, step `proj-flow-actions/bootstrap@v1` sets up Python 3.10, but proj-flow requires Python >=3.12

Versions, which cannot be checked reliably, such as ranges, ``3.x`` or
``${{ matrix.python }}``, are skipped. The warnings never fail the command.

``--no-venv``
   Bootstrap the *Project Flow* without the private virtual environment,
   installing it into the current Python instead. This is useful when the
   environment is already managed, e.g. by ``pyenv``, or when Pyton
   artifacts built and installed by this project should be available outside
   of it, e.g. to run them on data in other directories.

   .. note::

      This flag is actually used by the ``./flow`` helper, not by the
      ``bootstrap`` command. The helper needs to set up the expected
      environment before looking up the command in the available
      ``proj-flow``. As a side effect, a call with a typo (like in the examples
      below) will be reported as an error, but by that time ``proj-flow`` will
      already be installed in the local ``.venv``, which might not be
      the expected result.

      .. code-block:: console

         $ ./flow boostrap --no-venv
         $ ./flow bootstrap --no-env
