Usage
=====

.. _installation:

Installation
------------

To create a new project with *Project Flow*, first install it using pip:

.. code-block:: console

   (.venv) $ pip install proj-flow

Every project created with *Project Flow* has a self-bootstrapping helper
script, which will install `proj-flow` if it is needed, using either current
virtual environment or switching to a private virtual environment (created
inside `.flow/.venv` directory). This is used by the GitHub workflow in the
generated projects through the `bootstrap` command.

On any platform, this command (and any other) may be called from the root of the
project with:

.. code-block:: console

   $ python .flow/flow.py bootstrap

From Bash with:

.. code-block:: console

   $ ./flow bootstrap

From PowerShell with:

.. code-block:: console

   $ .\flow bootstrap

Creating a project
------------------

A fresh C++ project can be created with a

.. code-block:: console

   $ proj-flow init cxx

This command will ask multiple questions to build Mustache context for the
project template. For more information, see :ref:`command-init`.
