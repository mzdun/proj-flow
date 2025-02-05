Run steps
=========

Conan
-----

+-------------------+---------------------------------------+
| **Uses:**         | ``conan``                             |
+-------------------+---------------------------------------+
| **Needs:**        | ``conanfile.py`` or ``conanfile.txt`` |
+-------------------+---------------------------------------+
| **Aliased with:** | ``./flow config``                     |
+-------------------+---------------------------------------+

Prepares the external dependencies, by downloading and compiling Conan packages
as needed. Produces the ``build/conan`` directory with all the CMake targets.

CMake
-----

+-------------------+----------------------------------------------+
| **Uses:**         | ``cmake>=3.28``                              |
+-------------------+----------------------------------------------+
| **Needs:**        | ``CMakeLists.txt`` and ``CMakePresets.json`` |
+-------------------+----------------------------------------------+
| **Runs after:**   | Conan                                        |
+-------------------+----------------------------------------------+
| **Aliased with:** | ``./flow config``                            |
+-------------------+----------------------------------------------+

Prepares the build system in ``build/<build_type>`` directory (e.g.
``build/debug`` or ``build/release``)

Icons
-----

+-------------------+---------------------------+
| **Uses:**         | ``magick>=6`` on Windows, |
|                   | ``convert>=6`` otherwise  |
+-------------------+---------------------------+
| **Runs after:**   | Build                     |
+-------------------+---------------------------+

Uses the SVG images to create an ``data/assets/appicon.ico`` and
``data/assets/appicon-256.png``. Installed during ``proj-flow init`` as an
example of *Project Flow* extension read from project directory.

Build
-----

+-------------------+----------------------------------------------+
| **Uses:**         | ``cmake>=3.28``                              |
+-------------------+----------------------------------------------+
| **Needs:**        | ``CMakeLists.txt`` and ``CMakePresets.json`` |
+-------------------+----------------------------------------------+
| **Runs after:**   | Conan and CMake                              |
+-------------------+----------------------------------------------+
| **Aliased with:** | ``./flow build``, ``./flow test``            |
|                   | and ``./flow verify``                        |
+-------------------+----------------------------------------------+

Builds previously configured project in terms of ``cmake --build``.

Test
----

+-------------------+----------------------------------------------+
| **Uses:**         | ``cmake>=3.28`` and ``ctest>=3.28``          |
+-------------------+----------------------------------------------+
| **Needs:**        | ``CMakeLists.txt`` and ``CMakePresets.json`` |
+-------------------+----------------------------------------------+
| **Runs after:**   | Build                                        |
+-------------------+----------------------------------------------+
| **Aliased with:** | ``./flow test`` and ``./flow verify``        |
+-------------------+----------------------------------------------+

Runs all tests registered with CPack.

Sign
----

+-------------------+------------------------------------------------+
| **Needs:**        | A Windows run, a valid ``signtool`` exe path   |
|                   | and a key in either ``$SIGN_TOKEN``,           |
|                   | ``signature.json`` or ``~/signature.json``.    |
+-------------------+------------------------------------------------+
| **Runs after:**   | Build                                          |
+-------------------+------------------------------------------------+
| **Runs before:**  | Pack                                           |
+-------------------+------------------------------------------------+

.. warning::

    This step is only supported on Windows. On other systems it is
    quietly removed.

Signs all PE files in directories with binaries. For more information, see
:ref:`config-sign` flow config.

Pack
----

+-------------------+-------------------------------------------+
| **Uses:**         | ``cmake>=3.28`` and ``cpack>=3.28``;      |
|                   | if the ``"cpack_generator"`` contains     |
|                   | ``WIX``, also ``wix>=4,<5``               |
+-------------------+-------------------------------------------+
| **Needs:**        | ``CMakeLists.txt``, ``CMakePresets.json`` |
|                   | and non-empty ``"cpack_generator"`` list  |
|                   | in current config                         |
+-------------------+-------------------------------------------+
| **Runs after:**   | Build                                     |
+-------------------+-------------------------------------------+

Packs all archives and installers using CPack.

.. note::

    The WiX 4 dependency is not enforced yet


StoreTests
----------

+-------------------+------+
| **Runs after:**   | Test |
+-------------------+------+

Copies all files generated by tests to place they can be picked up by CI tools.

SignPackages
------------

+-------------------+------------------------------------------------+
| **Needs:**        | A Windows run, a valid ``signtool`` exe path   |
|                   | and a key in either ``$SIGN_TOKEN``,           |
|                   | ``signature.json`` or ``~/signature.json``.    |
+-------------------+------------------------------------------------+
| **Runs after:**   | Pack                                           |
+-------------------+------------------------------------------------+
| **Runs before:**  | StorePackages and Store                        |
+-------------------+------------------------------------------------+

.. warning::

    This step is only supported on Windows. On other systems it is
    quietly removed.

Signs all ``.msi`` files in packages directory.


StorePackages
-------------

+-------------------+------+
| **Runs after:**   | Pack |
+-------------------+------+

Copies all (possibly signed) archives and installers to place they can be picked
up by CI tools.

Store
-----

+-------------------+---------------+
| **Runs after:**   | Test and Pack |
+-------------------+---------------+

Runs both StoreTests and StorePackages

