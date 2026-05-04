# Hybrid Backend Design

## Goal

The current pure-Python `fiasco` branch proved scientifically useful as a probe,
but too expensive as the default path because the dominant runtime cost sits in
per-ion CHIANTI intensity evaluation before the AIA fold ever begins.

The hybrid path keeps the AIA-side folding logic in Python while importing the
compact upstream products that SSW already materializes in the AIA `.genx`
response files.

## First contract

The first hybrid contract is a normalized export built from:

- `aia_V9_all_fullinst.genx`
- `aia_V9_fullemiss.genx`

The export contains only the fields that the Python side needs for parity work
and auditability, not the full opaque `.genx` payload.

## Chosen file format

The initial export format is a normalized IDL SAVE file rather than HDF5.

Why:

- it is straightforward to write reliably from SSW/IDL
- `pyEUVTools` already depends on `scipy.io.readsav` for benchmark loading
- it avoids a second layer of IDL HDF5 type-mapping work before the field
  contract is stable

This is a transport choice, not a long-term requirement. Once the schema and the
loader behavior are stable, the same logical contract can be re-emitted as HDF5
without changing the Python-side abstraction.

## Export contents

Top-level export fields:

- format name and version
- source file paths for `fullinst` and `fullemiss`
- EUV channel list
- emissivity wavelength grid
- emissivity `logte` grid
- emissivity matrix from `fullemiss.total.emissivity`
- selected emissivity provenance fields from `fullemiss.general`

Per-channel fields from `fullinst`:

- wavelength grid
- effective area from the short-form channel structure
- geometric area
- plate scale
- electrons per DN
- electrons per eV
- focal-plane filter transmission
- entrance-filter transmission
- primary and secondary mirror reflectance
- CCD quantum efficiency
- contamination transmission

## Python-side shape

The initial Python loader lives in `pyeuvtools.response.hybrid` and exposes:

- `load_aia_hybrid_genx_export(...)`
- `build_aia_temperature_response_from_hybrid_export(...)`

That second helper deliberately reuses the existing raw folding path instead of
introducing a second temperature-response integrator. The hybrid work therefore
changes the upstream emissivity source first, while keeping the numerical fold
surface stable.

## Immediate milestone

The first milestone is the raw no-correction path:

1. export normalized upstream data from the `.genx` sources
2. load that export in Python
3. fold it through the existing AIA response machinery
4. compare directly against the canonical raw IDL benchmark

`evenorm` and `chiantifix` remain separate follow-on layers.

## Why this is the pragmatic next step

- it preserves traceability to the SSW source products already used by the IDL path
- it avoids paying the full `fiasco` spectrum-synthesis cost during each runtime comparison
- it gives the project a concrete interchange contract that can be versioned,
  archived, and compared across future backend revisions

## Next implementation tasks

1. run `scripts/idl/ExportAIAHybridGenx.pro` against the local SSW tree with an explicit output directory and explicit `fullinst`/`fullemiss` source pair, then preserve the resulting export in `benchmark-data/aia/genx-exports/`
2. add one committed test fixture or private local fixture path for the normalized hybrid export
3. compare `build_aia_temperature_response_from_hybrid_export(...)` against the raw benchmark
4. decide whether the hybrid path should continue to use `aiapy` for the wavelength-response layer or whether more of the instrument side should also be taken directly from the exported `fullinst` data