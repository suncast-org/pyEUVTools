# Dependency Plan

## Goal

This document captures the intended dependency strategy for reproducing the
canonical raw IDL AIA benchmark in Python without requiring users to install
SolarSoft.

## Guiding rule

`pyEUVTools` should treat SSW/IDL as a scientific reference for reverse
engineering and validation, not as a runtime dependency for end users.

## Benchmark target

The scientific target is the vendored raw no-correction AIA benchmark artifact at:

- `benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431_raw.sav`

Its metadata records the benchmark provenance, including:

- `evenorm=0`
- `chiantifix=0`
- effective-area and emissivity source files
- CHIANTI version, abundance file, and ionization-equilibrium file
- correction-applied flags

## Planned Python dependency split

### 1. AIA correction and degradation path

Planned source:

- `aiapy`

Why:

- `aiapy` already exposes AIA correction-table machinery and wavelength-response
  helpers.
- This is the most natural Python-native place to source the AIA effective-area
  and time-dependent correction behavior associated with the `evenorm` side of
  the benchmark.

Current status:

- already used for the shipped wavelength-response layer
- available without SSW

### 2. CHIANTI database and emissivity path

Candidate Python-native backends:

- `fiasco`
- `ChiantiPy`

Why this layer is needed:

- the raw IDL benchmark records CHIANTI-side provenance through `EMISSINFO`
- `chiantifix` and the `/temperature` response path depend on emissivity and
  ionization data that are not covered by `aiapy` alone

### 3. Validation target

Validation should always compare Python output against the vendored raw IDL
benchmark artifact, not use the benchmark as a runtime data dependency for the
algorithm itself.

## Assessment of candidate CHIANTI backends

### `fiasco`

Strengths:

- Python-native CHIANTI database download path
- supports multiple CHIANTI versions
- avoids any SSW requirement for users

Risks:

- the exact benchmark uses CHIANTI `9.0.1`, so version matching must be checked
- we still need to verify whether the necessary emissivity-side behavior for the
  AIA temperature-response reconstruction is available at the right abstraction
  level

Current verified prototype result:

- `pyEUVTools` now has a prototype helper that can ask `fiasco` to provision its
  configured database paths.
- In the current development environment, that helper successfully provisioned a
  usable local database and reported CHIANTI `11.0.2`.
- This confirms that Python-native provisioning is feasible, but it also makes
  the version-alignment problem explicit because the canonical raw AIA benchmark
  metadata records CHIANTI `9.0.1`.

### `ChiantiPy`

Strengths:

- established Python interface to CHIANTI
- uses the standard CHIANTI directory tree and `XUVTOP`

Risks:

- database installation is less self-managed than `fiasco`
- still requires the user or installer to provision the CHIANTI database tree

## What SSW tells us

The SSW tree indicates that the CHIANTI database is not fundamentally IDL-only.
SSW configures file locations and environment variables around a database tree.

Relevant evidence:

- `packages/chianti/setup/IDL_STARTUP` points CHIANTI at a filesystem location
- `for_checkabundance.pro` and related Forward routines resolve abundance and
  ionization files by path
- `ssw_upgrade,/chianti` and `sswdb_upgrade,/chianti` distinguish package code
  from database content

## Recommended runtime direction

For end-user installation, prefer a Python-native CHIANTI path and avoid making
SSW mandatory.

Current recommendation:

1. keep `aiapy` for AIA-side correction behavior
2. investigate `fiasco` first for CHIANTI database provisioning and access
3. add an explicit CHIANTI version-selection strategy so benchmark-parity work is
  not silently performed against a newer database than the canonical reference
4. use the raw benchmark to determine whether `fiasco` is sufficient or whether
  additional reconstruction work is needed for `chiantifix`

## Remaining reverse-engineering tasks

The following still need to be traced from the SSW implementation:

1. the exact computational path behind `aia_get_response(..., /temperature, /dn, /evenorm, /chiantifix)`
2. the exact meaning and effect of `chiantifix`
3. which data products are inputs versus derived intermediates
4. whether the Python-native CHIANTI backend can represent the required inputs
   directly or whether additional preprocessing is needed

## Near-term implementation plan

1. Confirm the `aiapy` side against the benchmark metadata and raw response
   shapes.
2. Prototype CHIANTI access with a Python-native backend, preferably `fiasco`.
3. Inspect the relevant SSW routines to isolate the `chiantifix` logic.
4. Build the Python temperature-response path against the vendored benchmark.
5. Only add GX-style compatibility layers after raw benchmark parity is achieved.