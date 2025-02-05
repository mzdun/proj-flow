.. _command-bootstrap:

``./flow bootstrap``
====================

Synopsis
--------

.. code-block::

   $ ./flow bootstrap
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
