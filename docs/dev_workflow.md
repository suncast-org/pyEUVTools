# Development Workflow

## Repository model

The canonical upstream repository should live under `suncast-org`.
Contributors are expected to fork the repository and contribute through pull requests.

## Versioning

Versioning is managed with `bumpver`:

```bash
bumpver update --patch
bumpver update --minor
bumpver update --major
```

The current scaffold version is `0.0.0` to mark the repository as pre-alpha and
explicitly not ready for a public release. The first real release target is
`0.1.0`, which should only be cut after the package exposes a genuinely usable
AIA response API.

## Build and publish

Build locally with:

```bash
python -m build
```

PyPI publishing is intentionally disabled as a default release path while the
repository remains in scaffold mode. The publish workflow is manual-only and
includes a guard against publishing the placeholder scaffold version.

## Zenodo

Zenodo release metadata is tracked in `.zenodo.json`.
GitHub releases tagged as `v*` are intended to be archived by Zenodo.
