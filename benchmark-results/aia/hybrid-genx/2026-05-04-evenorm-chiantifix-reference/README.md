# Hybrid Evenorm Chiantifix Reference Snapshot

This directory preserves the repo-local hybrid benchmark outputs intentionally
published on 2026-05-04 for the current AIA V9 evenorm-chiantifix reference
run.

## Purpose

These files are the retained direct-comparison outputs for the hybrid
genx-derived path against the vendored corrected IDL benchmark.

## Provenance

- workflow: `scripts/run_hybrid_raw_compare.py`
- export input: `src/pyeuvtools/data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav`
- benchmark input: `benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431.sav`
- repo-local artifact directory:
  `benchmark-results/aia/hybrid-genx/2026-05-04-evenorm-chiantifix-reference/hybrid_raw_compare`
- contributor command documented in `docs/usage.md`

## Scope

- `hybrid_raw_compare/`
  - preserved here as the retained direct runner output
  - contains the saved comparison plot and `.npz` data bundle for the published
    corrected hybrid reference run
  - corresponds to the corrected reference state: `evenorm=1`, `chiantifix=1`

## Notes

- this snapshot documents the direct hybrid-versus-corrected-IDL comparison;
  it is not a benchmark-wrapper timing run
- ordinary user runs should continue to write to `~/.pyeuvtools/...` by
  default; this repo-local directory is an explicit contributor-published
  reference artifact