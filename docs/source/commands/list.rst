.. _command-list:

``./flow list``
=================

Synopsis
--------

.. code-block::

   $ ./flow list [--alias] [--all] [--builtin] [--configs] [--pipe] [--steps]

Description
-----------

The `./flow list` command prints the CLI params a `cxx-flow` or `./flow` can
take. Most of the output is about possible :ref:`command-run` command parameters
or aliases.

``--builtin``
    Print list of known first-category commands.

``--steps``
    Print all known steps available to ``./flow run``.

``--alias``
    Print all ``./flow run`` aliases taken from flow config file from
    ``"entry"`` object. In a freshly-initialized project it is something like

    .. code-block:: json

        {
            "config": [ "Conan", "CMake" ],
            "build": [ "Build" ],
            "verify": [
                "Build", "Test", "Sign", "Pack", "SignPackages",
                "Store", "BinInst", "DevInst"
            ],
            "test": [ "Build", "Test" ]
        }

    Each key in this object can be used as a command replacing ``run``. For
    instance, calling

    .. code-block:: console

        $ ./flow config [args...]

    is the same, as if calling

    .. code-block:: console

        $ ./flow run --step Conan,CMake [args...]

``--configs``
    Print all key names from ``.flow/matrix.json``. This information can be used
    to decide, which ``-D`` parameters to ``./flow run`` make sense in
    current project.

``--all``
    Print all the above.

``--pipe``
    Print the parameters without any fancy editing.
