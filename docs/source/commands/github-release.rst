.. _command-github-release:

``./flow github release``
=========================

Synopsis
--------

.. code-block::

   $ ./flow github release [--all] [--force level] [--publish {ON,OFF}]
   $ GITHUB_ACTIONS=true GITHUB_OUTPUT=<file path> ./flow github release ...

Description
-----------

Bump the project version based on current git logs, create a ``"chore"``
commit for the change, attach an annotated tag with the version number
and push it all to GitHub.

``--all``
   *(optional)* Take all Conventional Commits. Normally, only ``feat:``, ``fix:``
   and ``docs:`` (upgraded to ``fix(docs):``) are taken into changelog. With this
   flags everything with recognized structure is used to populate the changelog.

``--force level``
   *(optional)* Ignore the version change calculated from changelog and
   instead use this value. Allowed values are: *patch*, *fix*, *minor*, *feat*,   
   *feature*, *major*, *breaking* and *release*.

``--publish {ON,OFF}``
   *(optional)* If this flag is present and set to *ON*, publish the release
   during this command. Otherwise, create a draft release.

``$GITHUB_ACTIONS`` / ``$GITHUB_OUTPUT``
   If ``$GITHUB_ACTIONS`` and ``$GITHUB_OUTPUT`` environment variables are both
   present, two output variables are created for the workflow step:

   - **tag** is a string with calculated next tag value (if any) and
   - **released** is a boolean value indicating, if a release happened (i.e.
     the **tag** is non-null).
