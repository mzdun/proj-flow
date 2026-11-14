# Roadmap

- [x] GitHub setup
- [x] Auto-release
- [x] Breaking change works
- [x] `chmod +x`, but on Windows
- [x] `./flow github release --retract`, retract a release, if chore commit is at HEAD
- [ ] bug_report's `version.options`: change to
  1. Current (vX.Y.Z)
  2. Previous (vX.Y-1.Z)
  3. Older, than vX.Y-1.Z
- [ ] New GitHub YAMLs in template
- [ ] GitHub bootstrap action
- [ ] Tests
- [ ] `proj-flow init <lang> --update`
- [ ] C++
  - [ ] Update package dependencies in Conan / default to CMake 4+
  - [ ] Allow for `libs/` vs `src/`/`include/`
  - [ ] `.github/ISSUE_TEMPLATE` to YAML
  - [ ] Fix Conan cache directory
  - [ ] Overall refresh the template
  - [ ] Icons extension uses "wall" as package name
  - [ ] `find_package(GTest REQUIRED)` duplicated
