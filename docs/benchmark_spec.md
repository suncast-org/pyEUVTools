# Canonical Benchmark Specification

## Purpose

The `0.1.0` scientific benchmark for `pyEUVTools` should not depend solely on a
previously generated GX-style response SAV whose provenance is incomplete.

The canonical benchmark set should instead be a family of raw IDL AIA
temperature-response artifacts produced directly from `aia_get_response` with
fully recorded generation settings.

## Effective SSW state model

For compatibility work, the important distinction is between requested keyword
state and effective SSW response state.

Requested states a user can ask for:

1. no `evenorm`, no `chiantifix`
2. `evenorm` only
3. `chiantifix` requested without `evenorm`
4. `evenorm` and `chiantifix`

Effective SSW states that matter scientifically:

1. `raw`: no `evenorm`, no `chiantifix`
2. `evenorm`: `evenorm` applied, `chiantifix` not applied
3. `evenorm_chiantifix`: both applied

The nominal `chiantifix`-only request is not an independent scientific state.
In SSW, requesting `chiantifix` for a temperature response forces `evenorm` on,
so that request normalizes to the `evenorm_chiantifix` state.

## Benchmark ladder

The benchmark ladder should be built in this order:

1. `raw` baseline: no `evenorm`, no `chiantifix`
2. `evenorm`-only benchmark
3. `evenorm_chiantifix` benchmark
4. optional `chiantifix`-only request artifact as a behavior check demonstrating
   that SSW normalizes it to `evenorm_chiantifix`

## Canonical IDL calls

Raw baseline:

```idl
response = aia_get_response(timedepend_date=obs_time_vms, /temperature, /dn, evenorm=0, chiantifix=0)
```

`evenorm` only:

```idl
response = aia_get_response(timedepend_date=obs_time_vms, /temperature, /dn, /evenorm, chiantifix=0)
```

`evenorm_chiantifix`:

```idl
response = aia_get_response(timedepend_date=obs_time_vms, /temperature, /dn, /evenorm, /chiantifix)
```

The benchmark script may wrap these calls for logging, metadata capture, and
file writing, but the scientific source object for parity should be the direct
IDL response structure in each case.

The repository draft script is:

- `scripts/idl/GenerateCanonicalAIABenchmark.pro`

## Initial benchmark date

The initial benchmark date for `0.1.0` should be pinned to:

- `2025-11-26T15:34:31.400`

This keeps the first raw benchmark aligned with the existing SunCAST test-model
epoch already used elsewhere in the workspace, while replacing the incomplete
legacy fixture provenance with a direct and reproducible IDL source artifact.

## Required benchmark artifacts

For `0.1.0`, the no-correction `raw` benchmark artifact is the primary baseline.

The `evenorm`-only and `evenorm_chiantifix` artifacts are strongly recommended
follow-on references for isolating correction-layer differences.

The derived GX-style compatibility artifact is explicitly deferred until after
the first scientific release target is met.

### 1. Raw baseline artifact

This is the primary scientific baseline. It should contain the direct IDL
`aia_get_response` output for the no-correction state plus a provenance
structure.

### 2. Correction-layer follow-on artifacts

These artifacts should use the same observation time and generator contract,
but with correction keywords varied one layer at a time:

- `evenorm`
- `evenorm_chiantifix`

An optional `chiantifix`-request artifact may also be generated to document the
fact that SSW normalizes this request to the `evenorm_chiantifix` effective state.

Recommended saved variables:

- `raw_response`: the direct IDL response returned by `aia_get_response`
- `metadata`: a provenance structure with the required fields listed below

### Deferred artifact: GX-style compatibility layer

GX-style derived artifacts may be added later, but they are not part of the
minimum benchmark contract for validating the Python implementation or issuing
the first public release.

## Required provenance fields

The `metadata` structure for a benchmark artifact must record at least:

- `instrument`
- `obs_time`
- `timedepend_date`
- `evenorm`
- `chiantifix`
- `requested_state`
- `effective_state`
- `idl_version`
- `ssw_root` or another stable SSW context identifier
- `generator`
- `generation_time_utc`
- `source_effarea_file`
- `source_emissivity_file`
- `response_units`
- `warnings_observed`

Strongly recommended additional fields:

- `effarea_version`
- `emiss_version`
- `source_model`
- `notes`
- `benchmark_role`, for example `raw_reference`

## Warning capture

The benchmark generation process should record whether IDL emitted floating-point
warnings such as divide-by-zero, underflow, overflow, or illegal operand.

These warnings do not automatically invalidate the benchmark, but they are part
of the provenance and must be recorded so the benchmark can be regenerated and
audited consistently.

## Benchmark decision rule

For `0.1.0`, scientific parity should be evaluated against the raw no-correction
benchmark artifact first.

After the raw baseline is matched, the `evenorm` layer should be validated, and
only then should the `chiantifix` layer be added.

The derived GX-style artifact is a downstream compatibility target, not the
primary scientific reference.

## Python parity target

The intended order of implementation is:

1. Reproduce the raw IDL AIA temperature-response structure in Python.
2. Add the `evenorm` correction layer and validate it separately.
3. Add the `chiantifix` correction layer in the same post-fold place where SSW
   applies it.
4. Document any remaining scientific mismatches explicitly.
5. Release `0.1.0` once the raw benchmark parity target and provenance
   requirements are satisfied.
6. Add GX-style compatibility artifacts later as a follow-on milestone.

## Interim status

The currently vendored canonical baseline artifact is the raw no-correction flavor and lives in:

- `benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431_raw.sav`

The previously vendored `evenorm_chiantifix` artifact remains useful as the next
correction-layer reference and still lives alongside it:

- `benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431.sav`

The older `pyGXrender-test-data` AIA response fixture remains useful for legacy
structural checks, but it is no longer the primary scientific release benchmark.

## Expected generator contract

The canonical IDL benchmark script should:

1. Accept a fixed observation time.
2. Call `aia_get_response` with explicit temperature, DN, and correction-state
   settings.
3. Save the raw response structure.
4. Save full provenance metadata, including requested and applied state.
5. Emit or record checksums for the benchmark artifacts.

The first draft of this contract is implemented in:

- `scripts/idl/GenerateCanonicalAIABenchmark.pro`

## Repository policy

Because the canonical AIA benchmark fixture is small, it is reasonable to vendor
benchmark artifacts directly in `pyEUVTools` for reproducible testing, as long
as provenance and checksums are tracked alongside them.

Generated comparison outputs, caches, timing logs, and benchmark summaries are
not part of that canonical benchmark-data contract. Those derived workflow
artifacts should live under backend-specific directories in `benchmark-results/`
so preserved `fiasco` reference runs and later hybrid runs do not overwrite one
another by default.

The initial vendored raw baseline checksum is tracked alongside the artifact in:

- `benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431_raw.sha256`