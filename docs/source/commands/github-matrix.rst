.. _command-github-matrix:

``./flow github matrix``
====================

Synopsis
--------

.. code-block::

   $ ./flow github matrix [--official]
   $ GITHUB_ACTIONS=true ./flow github matrix [--official]
   $ GITHUB_ACTIONS=true GITHUB_OUTPUT=<file path> ./flow github matrix [--official]

Description
-----------

In simplest form, this command prints a JSON with all possible configurations
built from ``.flow/matrix.yml``, with all inclusions and exclusions defined
there. Additionally, any ``"os"`` value present in the flow config file under
``"lts"`` is expanded to list of LTS systems. Currently in freshly-initialized
project the config contains Ubuntu LTS versions from 2020 till 2024:

.. code-block:: yaml

   lts:
      ubuntu:
       - ubuntu-20.04
       - ubuntu-22.04
       - ubuntu-24.04

.. note::

   This particular expansion, ``lts.ubuntu``, is deprecated in favor of
   automatically calculating the active Ubuntu LTS releases, with any given
   LTS being present, if the expansion is calculated after April 30th of
   the LTS release year and before February 1st five years after LTS release.

``--official``
   Cut matrix to release builds only by merging matrix definition in
   ``.flow/matrix.yml`` with ``.flow/official.yml``. In case of freshly
   generated version of this file, this means the matrix is built over

   .. code-block:: yaml

      matrix:
         compiler: [ "gcc", "msvc" ]
         build_type: [ "Release" ]
         sanitizer: [ false ]
         os: [ "ubuntu-20.04", "ubuntu-22.04", "ubuntu-24.04", "windows" ]

``$GITHUB_ACTIONS`` / ``$GITHUB_OUTPUT``
   If ``$GITHUB_ACTIONS`` environment variable is present, the result is packed
   into structure understood by GitHub Actions. If the ``$GITHUB_OUTPUT``
   variable is defined as well, file pointed to by this variable is used instead
   of stdout for the workflow matrix.
