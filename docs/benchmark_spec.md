# Canonical Benchmark Specification

## Purpose

The `0.1.0` scientific benchmark for `pyEUVTools` should not depend solely on a
previously generated GX-style response SAV whose provenance is incomplete.

The canonical benchmark should instead be a raw IDL AIA temperature-response
artifact produced directly from `aia_get_response` with fully recorded
generation settings.

## Canonical IDL call

The benchmark script should call:

```idl
response = aia_get_response(timedepend_date=obs_time_vms, /temperature, /dn, /evenorm, /chiantifix)
```

The benchmark script may wrap this call for logging, metadata capture, and file
writing, but the scientific source object for parity should be this direct IDL
response structure.

For the initial benchmark, the repository draft script is:

- `scripts/idl/GenerateCanonicalAIABenchmark.pro`

## Initial benchmark date

The initial benchmark date for `0.1.0` should be pinned to:

- `2025-11-26T15:34:31.400`

This keeps the first raw benchmark aligned with the existing SunCAST test-model
epoch already used elsewhere in the workspace, while replacing the incomplete
legacy fixture provenance with a direct and reproducible IDL source artifact.

## Required benchmark artifacts

For `0.1.0`, only the raw benchmark artifact is required.

The derived GX-style compatibility artifact is explicitly deferred until after
the first scientific release target is met.

### 1. Raw benchmark artifact

This is the primary scientific reference. It should contain the direct IDL
`aia_get_response` output plus a provenance structure.

Recommended saved variables:

- `raw_response`: the direct IDL response returned by `aia_get_response`
- `metadata`: a provenance structure with the required fields listed below

### Deferred artifact: GX-style compatibility layer

GX-style derived artifacts may be added later, but they are not part of the
minimum benchmark contract for validating the Python implementation or issuing
the first public release.

## Required provenance fields

The `metadata` structure for the raw benchmark must record at least:

- `instrument`
- `obs_time`
- `timedepend_date`
- `evenorm`
- `chiantifix`
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

For `0.1.0`, scientific parity should be evaluated against the raw benchmark
artifact first.

The derived GX-style artifact is a downstream compatibility target, not the
primary scientific reference.

## Python parity target

The intended order of implementation is:

1. Reproduce the raw IDL AIA temperature-response structure in Python.
2. Document any remaining scientific mismatches explicitly.
3. Release `0.1.0` once the raw benchmark parity target and provenance
   requirements are satisfied.
4. Add GX-style compatibility artifacts later as a follow-on milestone.

## Interim status

Until the canonical raw benchmark artifact is committed, the existing
`pyGXrender-test-data` AIA response fixture remains useful for structural checks
only. It should not be treated as the sole scientific release benchmark because
it does not currently record all required generation flags.

## Expected generator contract

The canonical IDL benchmark script should:

1. Accept a fixed observation time.
2. Call `aia_get_response` with explicit temperature, DN, `evenorm`, and
   `chiantifix` settings.
3. Save the raw response structure.
4. Save full provenance metadata.
5. Emit or record checksums for the benchmark artifacts.

The first draft of this contract is implemented in:

- `scripts/idl/GenerateCanonicalAIABenchmark.pro`

## Repository policy

Because the canonical AIA benchmark fixture is small, it is reasonable to vendor
the benchmark artifact directly in `pyEUVTools` for reproducible testing, as
long as its provenance and checksum are tracked alongside it.