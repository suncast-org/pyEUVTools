# pyEUVTools: EUV Instrument Response Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.12-blue?logo=python)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/pyeuvtools.svg?logo=pypi&logoColor=white)](https://pypi.org/project/pyeuvtools/)
[![Docs](https://img.shields.io/badge/docs-mkdocs-1f6feb.svg)](https://suncast-org.github.io/pyEUVTools/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20029729.svg)](https://doi.org/10.5281/zenodo.20029729)

## Overview

**pyEUVTools** is a SunCAST Python package for building, inspecting, and exporting
EUV instrument response products.

The project is designed to become a reusable response-function layer for the
broader SunCAST Python ecosystem, including packages such as `pyCHMP` and
`pyGXrender`, while remaining usable as a standalone scientific library.

The first backend focus is **SDO/AIA**. The package now also includes a static
**STEREO/EUVI** temperature-response builder for GX-compatible downstream use.

## Project Status

`pyEUVTools` is publicly released on PyPI and archived from GitHub releases by Zenodo.

Zenodo concept DOI: [10.5281/zenodo.20029729](https://doi.org/10.5281/zenodo.20029729)

The concrete `0.1.0` release gate is documented in [docs/dev_workflow.md](docs/dev_workflow.md).
In short, the first release must include a documented usable AIA API, validated
scientific behavior, at least one downstream-consumable output path, and tests
for the shipped public surface.

## Current Scope

- AIA wavelength-response wrappers powered by `aiapy`
- raw AIA temperature-response folding equivalent to the numerical step in SSW `aia_bp_make_tresp.pro`
- static STEREO/EUVI temperature-response payloads for Ahead and Behind, using packaged SRA calibration files and the same AIA hybrid emissivity grid used by the AIA path
- optional `fiasco` backend introspection and database bootstrap helpers for Python-native CHIANTI access
- IDL fixture comparison helpers for assessing structural parity against GX-style AIA response SAV files
- canonical benchmark planning for raw IDL AIA temperature-response fixtures with full provenance
- response-table data models for future multi-instrument support
- a package layout intended to grow into a generalized EUV response toolkit

## Planned Scope

- export/import helpers for GX-compatible response structures
- support for additional instruments such as TRACE, EUI, and SXT

## Installation

Install the published package from PyPI:

```bash
python -m pip install pyeuvtools
```

For local development, use an editable install:

```bash
git clone https://github.com/suncast-org/pyEUVTools.git
cd pyEUVTools
python -m pip install -e .[dev]
```

For a runtime-only editable install:

```bash
git clone https://github.com/suncast-org/pyEUVTools.git
cd pyEUVTools
python -m pip install -e .
```

For the optional Python-native CHIANTI prototype backend:

```bash
python -m pip install -e .[chianti]
```

The `fiasco`/CHIANTI path is currently a provisional backend rather than the
default production route. Installing the optional `chianti` extra is therefore
not required for normal package use.

## Contributor Artifact Policy

This repository may ship committed reference artifacts for documentation,
benchmark parity, and reviewable contributor refreshes, but ordinary user runs
should not write into the clone by default.

- User-generated benchmark outputs and hybrid exports default to user-local locations under `~/.pyeuvtools/` or a system temp directory fallback when `HOME` is unavailable.
- Repo-local writes are intentional contributor actions and should use explicit paths such as `--artifact-dir benchmark-results/...` or IDL `outdir='benchmark-data/...'`.
- The currently shipped runtime AIA V9 exports live under `src/pyeuvtools/data/aia/`.
- The currently shipped EUVI SRA calibration files live under `src/pyeuvtools/data/euvi/sra/`.
- The currently committed benchmark/provenance copy of the AIA V9 hybrid export remains at `benchmark-data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav`.

For a backend-local note describing what this prototype already covers, what was
validated, and why active development paused in favor of the hybrid
genx-derived approach, see `src/pyeuvtools/response/README.md`.

Default test runs also exclude the provisional CHIANTI backend tests. To run
them explicitly:

```bash
python -m pytest -m chianti_backend
```

## Quick Example

```python
from astropy.time import Time
from pyeuvtools.response.aia import build_aia_wavelength_response

response = build_aia_wavelength_response(171, Time("2020-11-26T19:58:31"))
table = response.to_table()

print(response.channel)
print(response.response.unit)
print(table.colnames)
```

## Documentation

Project documentation lives in the [docs/](docs) directory and is intended to be
published with GitHub Pages.

- [Project overview](docs/index.md)
- [Installation](docs/install.md)
- [Usage](docs/usage.md)
- [Development workflow](docs/dev_workflow.md)
- [API notes](docs/api.md)
- [Dependency plan](docs/dependency_plan.md)
- [Benchmark specification](docs/benchmark_spec.md)
- [Hybrid backend design](docs/hybrid_backend_design.md)

## Versioning and Releases

- Package versioning is managed with `bumpver`
- PyPI publishing remains disabled locally until the final release approval is given
- Zenodo metadata is tracked in `.zenodo.json` and intended to mint a DOI for releases
- Release-facing API changes are summarized in `CHANGELOG.md`

For this repository, Zenodo and PyPI are intentionally decoupled:

- a GitHub release under `suncast-org/pyEUVTools` is the event intended for Zenodo archival
- PyPI publishing is a separate manual GitHub Actions workflow and is not triggered automatically by a tag or GitHub release
- the current Zenodo metadata credits Gelu M. Nita as the named software creator while explicitly acknowledging maintenance in the `suncast-org` GitHub organization

## Status

This repository now ships a usable compact AIA response API, static STEREO/EUVI
temperature responses, and public GX bridge helpers needed for downstream
ComputeEUV packing. In particular, the Python `aia_get_response` wrapper covers
compact `effective_area`, `emissivity`, and `temperature` responses with explicit
non-interactive correction states: `raw`, `evenorm`, and `evenorm_chiantifix`.

The local metadata now targets **0.1.0**, but the release is still intentionally
held pending explicit approval. Remaining broader SSW surface coverage such as
`full`, `all`, and `uv` stays documented as later-milestone work rather than as
part of the compact `0.1.0` promise.
