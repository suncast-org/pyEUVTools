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
- `build_aia_effective_area`
- `build_aia_effective_area_set`
- `build_aia_temperature_response` for the raw folding step analogous to SSW `aia_bp_make_tresp.pro`
- `build_aia_temperature_response_set` for multi-channel raw folding on a shared emissivity grid
- `build_aia_temperature_response_idl_view` to package that folded matrix into the same normalized `instrument/channels/LOGTE/ALL` structure used by the IDL benchmark loader
- `build_aia_temperature_response_gx_payload` to package that same temperature response into the exact structured-array field layout expected by downstream `ComputeEUV`-style consumers: `ds`, `NT`, `Nchannels`, `logte`, `all`
- `aia_get_response` as a compact Python wrapper over the current AIA response milestone

The current temperature-response builder is intentionally narrower than the full
IDL `aia_get_response(/temperature, ...)` path. It performs the core numerical
folding step: interpolate the wavelength response onto the emissivity wavelength
grid, zero the out-of-band region, and integrate over wavelength for each
temperature bin. The surrounding SSW control flow, correction structures, and
`chiantifix` behavior are now partially implemented through a Python-readable
export of the SSW `aia_V#_chiantifix.genx` grid.

For the current `0.1.0` milestone, `aia_get_response` is intended to cover:

- compact EUV `area` / `effective_area` responses
- compact `emissivity` responses sourced from the hybrid export
- compact `temperature` responses with the explicit correction states `raw`, `evenorm`, and `evenorm_chiantifix`

The following remain later milestones rather than `0.1.0` requirements:

- `full` structures
- `all` channel mode beyond the standard thin-filter EUV set
- `uv` channels

The compact Python wrapper is deliberately non-interactive. It does not inherit
the SSW prompting behavior for under-specified correction choices. Instead, the
public surface accepts only scientifically valid correction states through the
`correction=` keyword:

- `raw`
- `evenorm`
- `evenorm_chiantifix`

The legacy `evenorm=` and `chiantifix=` keywords remain temporarily for
compatibility, but they are deprecated. A nominal `chiantifix`-only request is
rejected in the public API rather than being silently promoted, because the
package is meant to be safe for automated workflows.

Returned temperature-response metadata now includes a single authoritative
`correction_state` field, while the legacy `requested_state` and
`effective_state` fields are kept aligned to that same normalized value for
compatibility with existing artifacts and tests.

For downstream GX integration, the intended public bridge is
`build_aia_temperature_response_gx_payload(...)`. It returns:

- a length-1 structured NumPy array ready for direct downstream packing
- the exact dtype used to build that array
- a lightweight metadata dictionary carrying instrument, channels,
  `correction_state`, `response_units`, the chosen `ds_arcsec`, and the nested
  normalized IDL-view metadata

This keeps the response-construction logic in `pyEUVTools` while avoiding a hard
dependency on `gximagecomputing` implementation types.

For `0.1.0`, the required correction grid is shipped as packaged runtime data
under `src/pyeuvtools/data/aia/chiantifix-exports/`. The IDL helper
`scripts/idl/ExportAIAChiantifix.pro` remains the contributor refresh path for
rebuilding that packaged asset from the SSW `.genx` source.

## EUVI module

`pyeuvtools.response.euvi` provides:

- `resolve_euvi_sra_path` to resolve the packaged STEREO/EUVI SRA calibration file for Ahead or Behind
- `load_euvi_sra` to load the SRA wavelength/effective-area calibration data
- `build_euvi_effective_area` to build one channel effective-area curve
- `build_euvi_temperature_response_set` to fold the EUVI effective areas through the packaged AIA hybrid emissivity grid
- `build_euvi_temperature_response_idl_view` to expose the normalized `instrument/channels/LOGTE/ALL` view
- `build_euvi_temperature_response_gx_payload` to return the structured-array payload expected by downstream `ComputeEUV`-style consumers

The EUVI implementation intentionally follows the current GX Simulator path:
it uses the S1 filter, the standard 171, 195, 284, and 304 A channels, and one
packaged SRA calibration file per spacecraft:

- `src/pyeuvtools/data/euvi/sra/ahead_sra_001.geny`
- `src/pyeuvtools/data/euvi/sra/behind_sra_001.geny`

These response functions are static. The public constructors accept `obstime`
as a future-compatible placeholder, but the current calculation does not use it
and does not return observer ephemeris, roll, or position-angle metadata. Those
quantities should be computed by caller-side geometry code when they are needed.

For downstream GX integration, the intended public bridge is
`build_euvi_temperature_response_gx_payload(...)`. It returns the same
high-level triple as the AIA bridge: a length-1 structured NumPy payload, the
dtype used to build it, and metadata describing the instrument, spacecraft,
channels, response units, pixel scale, and normalized IDL-style view.

## EUI module

`pyeuvtools.response.eui` provides static Solar Orbiter/EUI response helpers:

- `resolve_eui_response_path` to resolve the packaged FSI or HRI GX response curve
- `build_eui_effective_area` to load the wavelength response and convert it to the units used by the AIA temperature fold
- `build_eui_temperature_response_set` to fold the EUI response through an emissivity grid
- `build_eui_temperature_response_idl_view` to expose the normalized `instrument/channels/LOGTE/ALL` view
- `build_eui_temperature_response_gx_payload` to return the structured-array payload expected by downstream `ComputeEUV`-style consumers

The EUI implementation follows the GX Simulator path for the 174 A band. It uses
one packaged response curve for each detector:

- `src/pyeuvtools/data/eui/EUIFSI_GXResponse.sav`
- `src/pyeuvtools/data/eui/EUIHRI_GXResponse.sav`

The public constructors accept `obstime` as a future-compatible placeholder, but
the current calculation is static and does not return Solar Orbiter ephemeris or
roll metadata.

## SXT and TRACE modules

`pyeuvtools.response.sxt` and `pyeuvtools.response.trace` provide static loaders
for the already-folded GX temperature-response structures:

- `resolve_sxt_response_path`
- `load_sxt_temperature_response_idl_view`
- `build_sxt_temperature_response_gx_payload`
- `resolve_trace_response_path`
- `load_trace_temperature_response_idl_view`
- `build_trace_temperature_response_gx_payload`

The packaged runtime files are:

- `src/pyeuvtools/data/sxt/sxt_response.sav`
- `src/pyeuvtools/data/trace/trace_response.sav`

The SXT loader mirrors GX channel normalization by converting `GAL12/GAL13`
labels to `A12/A13`. TRACE preserves the GX channel labels `171oa`, `195oa`,
and `284oa`. As with EUVI and EUI, `obstime` is retained only as a future
placeholder and no ephemeris fields are returned.

## CHIANTI backend prototype

`pyeuvtools.response.chianti` currently provides:

- `get_fiasco_backend_status` to report whether `fiasco` is importable and whether its configured CHIANTI database is accessible
- `ensure_fiasco_database` to ask `fiasco` to provision its configured ASCII and HDF5 CHIANTI databases if they are missing
- `rebuild_fiasco_database` to repair a partial or corrupt local HDF5 cache from the ASCII CHIANTI tree
- `build_fiasco_ion_spectrum_grid` to build a real wavelength/temperature spectrum grid from an explicit ion subset
- `save_fiasco_spectrum_grid` to persist that expensive CHIANTI-backed spectrum grid as a `.npz` cache artifact
- `load_fiasco_spectrum_grid` to reload that cache artifact for repeated folds without rebuilding the spectrum
- `screen_fiasco_ions_for_temperature_grid` to find which explicit ions actually support a requested temperature grid under the current backend settings
- `FiascoBackendStatus` to carry the backend version, configured database roots, and current availability state

This is intentionally a backend-readiness helper, not a temperature-response builder.
It exists to separate `fiasco installed` from `database actually usable`, which is
the next concrete gate for the Python-native CHIANTI path.

This backend is currently provisional and is not the default production path for
the package. The optional `fiasco` dependency and its database are therefore not
required for a normal `pyeuvtools` installation, and the CHIANTI-backend tests
are excluded from the default pytest run unless explicitly requested.

When the ASCII CHIANTI tree is available, the status helper also reports the
detected CHIANTI database version.

The ion-spectrum helper is narrower than a full CHIANTI emissivity engine, but it
provides the first real scientific bridge between `fiasco` and the raw AIA benchmark
comparison path by returning a binned wavelength/temperature surface for a chosen ion set.

The ion-screening helper complements that bridge by letting callers preflight a
candidate ion list with the same temperature grid and low-level `fiasco` kwargs,
such as `use_two_ion_model` or `include_protons`, before attempting a larger spectrum build.

The spectrum-grid cache helpers are intended for repeated local parity runs where the CHIANTI build dominates runtime but the fold inputs have not changed.

## Hybrid genx export prototype

`pyeuvtools.response.hybrid` now provides the first hybrid-backend scaffolding:

- `load_aia_hybrid_genx_export` to load a normalized export assembled from the
	source AIA `fullinst` and `fullemiss` `.genx` products
- `build_aia_temperature_response_from_hybrid_export` to fold that normalized
	export through the existing Python AIA temperature-response path

By default, those helpers now resolve the highest installed exported AIA
response version under the packaged runtime-data tree
`src/pyeuvtools/data/aia/genx-exports/` and load the matching
`aia_hybrid_genx_export_v1.sav`. Callers can instead pass an explicit path or a
version selector such as `emversion="V9"` when they need to pin an older
artifact for regression or comparison work.

The shipped repository therefore carries two copies with different roles:

- runtime package data under `src/pyeuvtools/data/aia/genx-exports/`
- benchmark/provenance copies under `benchmark-data/aia/genx-exports/`

User-generated exports still default to an external user-local directory unless
`outdir` is passed explicitly to the IDL exporter.

The hybrid temperature-response constructor now mirrors the main SSW selector
split more closely:

- `version` selects the instrument response version by resolving the matching
	`fullinst` file when available
- `emversion` selects the exported emissivity artifact version under the
	packaged runtime-data tree
- `respversion` selects a specific degradation response table, either by path or
	by matching a version/timestamp-like filename fragment under the AIA response tree

The current contract is intentionally narrow. It does not attempt to reproduce
the full SSW response-control flow inside the export itself. Instead it defines a
stable interchange surface for the upstream instrument and emissivity products so
Python can use those compact data directly.

The currently published hybrid comparison snapshot should therefore be read as a
raw-baseline artifact in the narrow benchmark sense: the vendored IDL reference
records `evenorm=0` and `chiantifix=0`, while crosstalk is not recorded as a
separate metadata field in that fixture.

The hybrid comparison CLI follows the same policy: its default artifact output
directory now lives outside the repository, and contributors must pass an
explicit repo-local artifact directory when they intentionally want to refresh
committed benchmark artifacts.

## IDL comparison helpers

`pyeuvtools.response.compare` provides:

- `load_idl_aia_response` to read a GX-style AIA response SAV fixture
- `compare_aia_response_to_idl` to compare that fixture against the shipped Python AIA layer
- `compare_aia_temperature_response_to_idl` to compare a Python-folded temperature-response matrix against the raw IDL benchmark
- `save_aia_temperature_response_comparison_data` to persist a completed comparison as a `.npz` artifact for later replotting
- `load_aia_temperature_response_comparison_data` to reload that `.npz` artifact without recomputing the CHIANTI bridge
- `plot_aia_temperature_response_comparison` to save a channel-by-channel visual comparison of the IDL and Python temperature-response curves versus `logte`

The comparison is intentionally structural at this stage. It records channel and
instrument agreement and surfaces blocking gaps when the IDL and Python layers do
not yet represent the same scientific object.

When an emissivity grid is available, `compare_aia_temperature_response_to_idl`
can perform the direct matrix comparison against the IDL `ALL` temperature-response
array and report per-channel numerical differences.

The same normalized structure is now available on the Python side through
`build_aia_temperature_response_idl_view`, which makes it possible to inspect or
serialize a Python-built response with the same logical shape as the SSW/IDL
benchmark before chasing remaining numerical differences.

It also checks whether the IDL fixture metadata records the response-generation
flags needed for reproducibility, including `evenorm` and `chiantifix`.

The current comparison helpers remain useful for interim validation against
legacy GX-style fixtures, but the long-term scientific target is the raw IDL
temperature-response benchmark defined in `docs/benchmark_spec.md`.

For channel-specific interpretation, AIA 335 should currently be treated as a lower-confidence validation channel than 171, 193, or 211. Public references report passband inconsistencies, higher-order contamination, and incomplete spectral content in the 335 A region: Boerner et al. 2013 (Sol. Phys. 289, 2377; arXiv:1307.8045) and Trabert and Beiersdorfer 2018 (A&A 617, A8; DOI 10.1051/0004-6361/201833256).

## Current scientific scope

The shipped API currently covers the AIA wavelength-response layer via `aiapy`.
It is time-dependent through the observation time input and uses the `jsoc`
correction table by default. It does not yet claim GX-compatible temperature-response
equivalence.
