.. _command-init:

``proj-flow init``
==================

Synopsis
--------

.. code-block::

   $ proj-flow init [-y] [--ctx] project [path]

Description
-----------

The `proj-flow init` command creates a new project in current directory.

It first builds the mustache context for the :ref:`directory template<template>`
by prompting for all the interactive :ref:`settings<interactive-settings>` and
:ref:`switches<interactive-switches>` and calculating the context based on
gathered answers. For each of the prompt, pressing ENTER while not giving any
answer will take the default value into the context. For lists, this is the
first item, for simple string, this is the value in the square brackets, for
switches it is the "yes" answer.

All the files in various directory template layers are filtered, whether they
should populate the project or not. All the ``.mustache`` files are then passed
through the mustache engine and written to project directory, all other files
follow suit. Finally, Git repository is initialized and initial commit is made
out of all files copied into the project directory.

``project``
    Type of project to create. Currently, only one project type is supported,
    named ``cxx``, which builds the same project layout old command built.

``path``
    Optional parameter, pointing to some other directory. The directory will be
    created, if it does not exist yet.

``-y`` / ``--yes``
    The interactive phase is omitted and the initial values are taken from the
    default values for each setting and switch.

``--ctx``
    The JSON file named ``.context.json`` will be added to project, but also
    ignored by Git. This file will include the full Mustache context calculated
    during the interactive phase.
