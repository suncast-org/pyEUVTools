# Hybrid Raw Reference Snapshot

This directory preserves the repo-local hybrid benchmark outputs intentionally
published on 2026-05-04 for the current AIA V9 raw-reference run.

## Purpose

These files are the retained direct-comparison outputs for the hybrid
genx-derived path after the duplicate smoke snapshot and the intermediate
`hybrid-v9-regen` developer run were removed as local pre-publish artifacts.

## Provenance

- workflow: `scripts/run_hybrid_raw_compare.py`
- export input: `benchmark-data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav`
- repo-local artifact directory:
  `benchmark-results/aia/hybrid-genx/2026-05-04-raw-reference/hybrid_raw_compare`
- contributor command documented in `docs/usage.md`

## Scope

- `hybrid_raw_compare/`
  - preserved here as the retained direct runner output
  - contains the saved comparison plot and `.npz` data bundle for the published
    hybrid reference run
  - corresponds to the raw baseline state: no `evenorm`, no `chiantifix`

## Notes

- this snapshot documents the direct hybrid-versus-raw-IDL comparison only; it
  is not a benchmark-wrapper run and does not represent every local hybrid test
- the vendored IDL benchmark metadata confirms `evenorm=0` and `chiantifix=0`
  for this reference state; it does not record crosstalk as a separate field,
  so the published `raw` label is precise for `evenorm`/`chiantifix` but not a
  full statement about every lower-level response toggle
- ordinary user runs should continue to write to `~/.pyeuvtools/...` by
  default; this repo-local directory is an explicit contributor-published
  reference artifact
- the removed `2026-05-03-smoke` directory was content-equivalent to this
  snapshot and is intentionally not retained as a separate published artifact