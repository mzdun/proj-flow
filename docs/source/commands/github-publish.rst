.. _command-github-publish:

.. note::

   This command is part of ``proj_flow.ext.github`` extension.

``./flow github publish``
=========================

Synopsis
--------

.. code-block::

   $ ./flow github publish [--ref release] [--upload directory]

Description
-----------

Upload package artifacts to a GitHub release and in case the release is still
in draft, publish it.

``--ref release``
   *(optional)* Publish this release draft. In case this is called from within
   GitHub Actions and your release is named exactly like the tag used
   to trigger this flow, you can use ``${{github.action_ref}}`` variable.
   Defaults to current tag.

``--upload directory``
   *(optional)* If present, upload files from the directory to the referenced
   release before publishing.
