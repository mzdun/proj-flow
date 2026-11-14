.. _command-github-matrix:

``./flow github matrix``
========================

Synopsis
--------

.. code-block::

   $ ./flow github matrix [--pretty] [--official]
   $ GITHUB_ACTIONS=true ./flow github matrix [--official]
   $ GITHUB_ACTIONS=true GITHUB_OUTPUT=<file path> ./flow github matrix [--official]

Description
-----------

In simplest form, this command prints a JSON with all possible configurations
built from ``.flow/matrix.yml``, with all inclusions and exclusions defined
there. Additionally, the ``"ubuntu"`` value of ``"os"`` is expanded to the
list of Ubuntu LTS systems currently available as GitHub runners. The list is
downloaded from the ``src/proj_flow/flow/github-runners.yaml`` file on the
main branch of *Project Flow* repository, falling back to the copy installed
with the package. Currently, it contains:

.. code-block:: yaml

   ubuntu:
     - ubuntu-22.04
     - ubuntu-24.04
     - ubuntu-26.04

Any other ``"os"`` value present in the flow config file under ``"lts"`` is
expanded the same way, using instructions from :ref:`config.json<config-lts>`.

.. note::

   Listing Ubuntu versions in the flow config, under ``lts.ubuntu``, still
   overrides the downloaded list, but it is deprecated and produces
   a warning.

``--pretty``
   Indent the JSON document.

``--official``
   Cut matrix to release builds only by merging matrix definition in
   ``.flow/matrix.yml`` with ``.flow/official.yml``. In case of freshly
   generated version of this file, this means the matrix contains only

   .. code-block:: yaml

      matrix:
         compiler: [ "gcc", "msvc" ]
         build_type: [ "Release" ]
         sanitizer: [ false ]
         os: [ "ubuntu", "windows" ]

   with ``"ubuntu"`` expanded to current list of LTS runners.

``$GITHUB_ACTIONS`` / ``$GITHUB_OUTPUT``
   If ``$GITHUB_ACTIONS`` environment variable is present, the result is packed
   into structure understood by GitHub Actions. If the ``$GITHUB_OUTPUT``
   variable is defined as well, file pointed to by this variable is used instead
   of stdout for the workflow matrix.
