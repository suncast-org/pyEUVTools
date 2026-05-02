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

## Current Scope

- AIA wavelength-response wrappers powered by `aiapy`
- response-table data models for future multi-instrument support
- a package layout intended to grow into a generalized EUV response toolkit

## Planned Scope

- AIA temperature-response builder compatible with GX-style response tables
- export/import helpers for GX-compatible response structures
- support for additional instruments such as TRACE, EUVI, EUI, and SXT

## Installation

Install the latest release from PyPI:

```bash
pip install pyeuvtools
```

For development:

```bash
git clone https://github.com/suncast-org/pyEUVTools.git
cd pyEUVTools
python -m pip install -e .[dev]
```

## Quick Example

```python
from astropy.time import Time
from pyeuvtools.response.aia import build_aia_wavelength_response_set

responses = build_aia_wavelength_response_set(Time("2020-11-26T19:58:31"))

print(responses.instrument)
print(responses.channels)
print(responses.responses["171"])
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
- PyPI publishing is handled through GitHub Actions using trusted publishing
- Zenodo metadata is tracked in `.zenodo.json` and intended to mint a DOI for releases

## Status

This repository is the initial scaffold for the package. The AIA wavelength
response wrapper is implemented. The GX-compatible temperature response layer is
planned but not yet implemented.
