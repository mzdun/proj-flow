# Commit Guidelines

This project uses [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/). The commit history is the source of both the version bumps and the changelog, so each commit message should say what kind of change it brings.

```
<type>[(<scope>)][!]: <subject>

[body]

[footers]
```

## Subject

| Type | Use for | Version bump | Changelog section |
|------|---------|--------------|-------------------|
| `feat` | new feature visible to the users of the project | MINOR | New Features |
| `fix` | bug fix visible to the users of the project | PATCH | Bug Fixes |
| `docs` | changes to the documentation | PATCH | Bug Fixes |
| `assets` | artwork only: icons, images and similar | | |
| `build` | build system and external dependencies | | |
| `chore` | maintenance, which does not touch the product code | | |
| `ci` | CI configuration and scripts | | |
| `perf` | performance improvements | | |
| `refactor` | code changes, which neither fix a bug nor add a feature | | |
| `revert` | reverting a previous commit | | |
| `style` | formatting only, no change in behavior | | |
| `test` | adding or correcting tests | | |

Only the `feat` and `fix` sections are part of the changelog by default; the other types are listed there only on request.

The optional scope names the part of the project the change applies to, e.g. `fix(parser): ...`. Pick the scopes, which make sense for this project and use them consistently.

The subject:

- uses the imperative, present tense: "add", not "added" nor "adds",
- starts with a lowercase letter and has no period at the end,
- is short enough to read in a one-line log.

## Body

The body is optional. When present, it explains the motivation for the change and how it differs from the previous behavior, rather than repeating the diff.

## Footers

### Referencing issues

Issues closed by the commit are listed in a `Closes` (or `Fixes`) footer, the ones only related to it in a `Refs` footer:

```
Closes: #234
Refs: #123, #245
```

### Breaking changes

A change, which breaks compatibility, has a `!` after the type (or scope) and a `BREAKING CHANGE` footer as the last part of the message. The footer describes the change, the reason for it and the way to migrate. Any breaking change bumps the MAJOR version.

```
feat(cli)!: rename --out to --output

BREAKING CHANGE: the `--out` option is now called `--output`, consistent with
the configuration file. Replace `--out` with `--output` in your scripts.
```
