# API Notes

## Data model

`pyeuvtools.response.models.AIAChannelWavelengthResponse` stores:

- channel label
- observation time
- wavelength grid
- response values with units
- EVE correction flag
- correction source metadata

It exports to an `astropy.table.QTable` through `to_table()`.

`pyeuvtools.response.models.WavelengthResponseSet` stores:

- instrument name
- observation time
- ordered channel labels
- common wavelength grid
- per-channel response arrays

It exports to an `astropy.table.QTable` through `to_table()`, with one response
column per channel.

## AIA module

`pyeuvtools.response.aia` currently provides:

- `build_aia_wavelength_response`
- `build_aia_wavelength_response_set`
- `build_aia_temperature_response` (planned; currently raises `NotImplementedError`)

## CHIANTI backend prototype

`pyeuvtools.response.chianti` currently provides:

- `get_fiasco_backend_status` to report whether `fiasco` is importable and whether its configured CHIANTI database is accessible
- `ensure_fiasco_database` to ask `fiasco` to provision its configured ASCII and HDF5 CHIANTI databases if they are missing
- `FiascoBackendStatus` to carry the backend version, configured database roots, and current availability state

This is intentionally a backend-readiness helper, not a temperature-response builder.
It exists to separate `fiasco installed` from `database actually usable`, which is
the next concrete gate for the Python-native CHIANTI path.

When the ASCII CHIANTI tree is available, the status helper also reports the
detected CHIANTI database version.

## IDL comparison helpers

`pyeuvtools.response.compare` provides:

- `load_idl_aia_response` to read a GX-style AIA response SAV fixture
- `compare_aia_response_to_idl` to compare that fixture against the shipped Python AIA layer

The comparison is intentionally structural at this stage. It records channel and
instrument agreement and surfaces blocking gaps when the IDL and Python layers do
not yet represent the same scientific object.

It also checks whether the IDL fixture metadata records the response-generation
flags needed for reproducibility, including `evenorm` and `chiantifix`.

The current comparison helpers remain useful for interim validation against
legacy GX-style fixtures, but the long-term scientific target is the raw IDL
temperature-response benchmark defined in `docs/benchmark_spec.md`.

## Current scientific scope

The shipped API currently covers the AIA wavelength-response layer via `aiapy`.
It is time-dependent through the observation time input and uses the `jsoc`
correction table by default. It does not yet claim GX-compatible temperature-response
equivalence.
