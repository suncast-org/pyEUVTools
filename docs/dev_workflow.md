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

## First Release Criteria

Version `0.1.0` is the first public release target. It should not be cut until
all of the following are true.

### API criteria

- The package exposes at least one AIA API that is useful on its own rather than
	only mirroring a thin internal wrapper.
- That API accepts an observation time and returns a stable, documented result.
- The returned object model is explicit enough for downstream packages to depend
	on without guessing field names, units, or channel ordering.
- The `build_aia_temperature_response()` placeholder is either implemented for a
	supported path or replaced by a clearly named public API that covers the first
	intended release use case.

### Scientific criteria

- The Python AIA response must be compared against the canonical IDL-produced
	AIA response structure for at least one shared observation date.
- The canonical benchmark ladder for `0.1.0` should start with a raw IDL
	`aia_get_response` temperature-response artifact generated with no `evenorm`
	or `chiantifix` corrections applied and recorded with full provenance.
- Correction-layer benchmarks with `evenorm` and then `evenorm + chiantifix`
	should be generated as follow-on references so those layers can be validated
	separately from the raw baseline.
- The older `pyGXrender-test-data` fixture corresponding to
	`resp_aia_20251126T153431.sav` may be used for interim structural checks, but
	it is not sufficient as the sole scientific benchmark for `0.1.0` because its
	provenance is incomplete.
- The benchmark fixture provenance must record the response-generation choices
	needed for reproducibility, including both the requested correction state and
	the actually applied `evenorm` and `chiantifix` state.
- The benchmark fixture provenance must also record the exact response source
	files, generator script, generation timestamp, IDL version, and SSW context
	used to produce the raw benchmark artifact.
- AIA time-dependent behavior is exercised with at least one validated example
	date.
- Output units, wavelength grids, channel ordering, and correction choices are
	documented.
- The implementation states exactly what is and is not scientifically equivalent
	to the IDL/SSW response path.
- Any structural mismatches between the Python result and the IDL fixture must
	be documented as either resolved, intentionally normalized, or explicitly out
	of scope for `0.1.0`.
- Any remaining scientific gaps are documented as deliberate non-goals for
	`0.1.0`, not left ambiguous.

### Interoperability criteria

- There is at least one export or conversion path that a downstream SunCAST tool
	can consume directly.
- A minimal end-to-end example shows the package being used from import through
	usable output.
- The package can be installed and used without requiring knowledge of the
	internal repository layout.

### Quality criteria

- Tests cover the first public AIA API, including at minimum one success path
	and one failure or validation path.
- The documented example is runnable and consistent with the shipped API.
- The package builds successfully with `python -m build`.
- The version, changelog or release notes, citation metadata, and Zenodo
	metadata are updated for the release.

### Release decision rule

If the repository still mainly provides scaffolding, placeholders, or thin
pass-through wrappers, the version must remain below `0.1.0`.

The benchmark artifact and generator contract are documented in `docs/benchmark_spec.md`.

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
