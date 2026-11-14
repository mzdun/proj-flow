.. _command-github-release:

``./flow github release``
=========================

Synopsis
--------

.. code-block::

   $ ./flow github release [--all] [--force level] [--publish {ON,OFF}]
                           [--changelog] [--omit range] [--with type [type ...]]
   $ ./flow github release --retract [--force-retract]
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

``--changelog``
   *(optional)* Even with ``--dry-run``, write the changes to project files,
   changelog, etc. Nothing is committed, tagged nor pushed. Useful for
   previewing the changelog before the release.

``--omit range``
   *(optional)* Hide these commits in the generated changelog. The value is
   anything ``git log`` accepts, either a single commit, or a range, such as
   ``abc123~..def456``. Can be used multiple times.

``--with type [type ...]``
   *(optional)* Use these Conventional Commit types in addition to
   *breaking*, *feat* and *fix*, e.g. ``--with docs refactor``.

``--retract``
   *(optional)* Instead of releasing, undo the release, whose ``"chore"``
   commit is at ``HEAD``: remove the GitHub release, delete the tag locally
   and remotely, reset the branch to ``HEAD~`` and push it with lease. If no
   GitHub repository is found among git remotes, the release is retracted
   locally only.

``--force-retract``
   *(optional)* With ``--retract``, remove the GitHub release even if it is
   no longer a draft. Cannot be used without ``--retract``.

``$GITHUB_ACTIONS`` / ``$GITHUB_OUTPUT``
   If ``$GITHUB_ACTIONS`` and ``$GITHUB_OUTPUT`` environment variables are both
   present, two output variables are created for the workflow step:

   - **tag** is a string with calculated next tag value (if any) and
   - **released** is a boolean value indicating, if a release happened (i.e.
     the **tag** is non-null).
