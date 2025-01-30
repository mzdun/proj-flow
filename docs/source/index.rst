C++ flow
===================================

**C++ flow** aims at being a one-stop tool for C++ projects, from creating new
project, though building and verifying, all the way to publishing releases to
the repository. It will run a set of known steps and will happily consult your
project what do you want to call any subset of those steps.

Currently, it will make use of Conan for external dependencies, CMake presets
for config and build and GitHub CLI for releases.

Check out the :doc:`usage` section for further information, including
how to :ref:`installation` the project.

.. note::

   This project is under active development.

Contents
--------

.. toctree::
   :maxdepth: 2

   usage
   commands/index
   steps/index
   template
   config
   api/index
