# Hybrid Benchmark Reference Snapshots

This directory retains the published repo-local hybrid benchmark comparison
artifacts for the canonical AIA reference states.

## Published snapshots

- `2026-05-04-raw-reference/`
  - comparison against the vendored raw IDL benchmark
  - scientific state: no `evenorm`, no `chiantifix`
- `2026-05-04-evenorm-chiantifix-reference/`
  - comparison against the vendored corrected IDL benchmark
  - scientific state: `evenorm=1`, `chiantifix=1`

Each snapshot contains a `hybrid_raw_compare/` directory with:

- `aia_hybrid_raw_compare_data.npz`
- `aia_hybrid_raw_compare.png`

Use `scripts/run_hybrid_reference_compare_pair.py` to regenerate both published
comparison outputs in one command.