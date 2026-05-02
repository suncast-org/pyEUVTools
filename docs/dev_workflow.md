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

## Build and publish

Build locally with:

```bash
python -m build
```

Publishing to PyPI is intended to happen through the GitHub Actions publish workflow
triggered from GitHub releases or version tags.

## Zenodo

Zenodo release metadata is tracked in `.zenodo.json`.
GitHub releases tagged as `v*` are intended to be archived by Zenodo.
