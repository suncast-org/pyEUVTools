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

## Required benchmark artifacts

The canonical benchmark set should contain two artifacts.

### 1. Raw benchmark artifact

This is the primary scientific reference. It should contain the direct IDL
`aia_get_response` output plus a provenance structure.

Recommended saved variables:

- `raw_response`: the direct IDL response returned by `aia_get_response`
- `metadata`: a provenance structure with the required fields listed below

### 2. Derived GX-style compatibility artifact

This is a secondary artifact derived deterministically from `raw_response`.
It exists to support downstream GX-compatible workflows and compatibility tests.

Recommended saved variables:

- `response`: normalized GX-style structure
- `gxresponse`: alias of `response` for compatibility
- `metadata`: provenance structure matching the raw artifact and explicitly
  stating that the GX-style structure is derived from `raw_response`

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
- `benchmark_role`, for example `raw_reference` or `gx_derived`

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
3. Derive a GX-style compatibility structure from the Python result.
4. Validate the derived Python GX-style structure against the IDL-derived
   compatibility artifact.

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
5. Optionally derive and save the GX-style compatibility structure.
6. Emit or record checksums for the benchmark artifacts.

## Repository policy

Because the canonical AIA benchmark fixture is small, it is reasonable to vendor
the benchmark artifact directly in `pyEUVTools` for reproducible testing, as
long as its provenance and checksum are tracked alongside it.