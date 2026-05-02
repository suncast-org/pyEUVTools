# pyEUVTools: EUV Instrument Response Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.10-blue?logo=python)](https://www.python.org/)

## Overview

**pyEUVTools** is a SunCAST Python package for building, inspecting, and exporting
EUV instrument response products.

The project is designed to become a reusable response-function layer for the
broader SunCAST Python ecosystem, including packages such as `pyCHMP` and
`pyGXrender`, while remaining usable as a standalone scientific library.

The first backend focus is **SDO/AIA**. The immediate goal is to provide a clean
Python interface to the time-dependent AIA instrument response machinery already
available through `aiapy`, and then build toward GX-compatible temperature
response tables on top of that foundation.

## Project Status

`pyEUVTools` is currently **pre-alpha**. The repository is intentionally in a
scaffold-and-implementation phase and is **not intended for a public PyPI release yet**.

The planned first real release target is **0.1.0**, and that milestone should only
be cut after the package provides a clearly usable AIA response API beyond the
current thin wrapper layer.

The concrete `0.1.0` release gate is documented in [docs/dev_workflow.md](docs/dev_workflow.md).
In short, the first release must include a documented usable AIA API, validated
scientific behavior, at least one downstream-consumable output path, and tests
for the shipped public surface.

## Current Scope

- AIA wavelength-response wrappers powered by `aiapy`
- IDL fixture comparison helpers for assessing structural parity against GX-style AIA response SAV files
- response-table data models for future multi-instrument support
- a package layout intended to grow into a generalized EUV response toolkit

## Planned Scope

- AIA temperature-response builder compatible with GX-style response tables
- export/import helpers for GX-compatible response structures
- support for additional instruments such as TRACE, EUVI, EUI, and SXT

## Installation

There is no public PyPI release yet. Use a development install:

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

## Versioning and Releases

- Package versioning is managed with `bumpver`
- PyPI publishing is disabled by default until the first usable AIA response API is implemented
- Zenodo metadata is tracked in `.zenodo.json` and intended to mint a DOI for releases

## Status

This repository is the initial scaffold for the package. The AIA wavelength
response wrapper is implemented, but the package is not yet considered ready for
public release. The GX-compatible temperature response layer is planned but not
yet implemented, and **0.1.0** remains the target for the first real release.
