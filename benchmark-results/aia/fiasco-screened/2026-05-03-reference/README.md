# Fiasco Reference Snapshot

This directory preserves the pre-hybrid benchmark outputs produced by the
provisional `fiasco`-screened workflow as they existed on 2026-05-03.

## Purpose

These files are a historical reference snapshot for the Python-native CHIANTI
prototype before the active implementation focus moved to the hybrid
genx-derived path.

## Contents

- `screened_raw_compare/`
  - preserved here as the retained reference copy
  - contains the direct runner outputs that were present at archive time
- `benchmark_screened_raw_compare/`
  - preserved here as the retained reference copy
  - contains the benchmark-wrapper outputs and `benchmark_summary.json`

## Notes

- the older generic `artifacts/` directory has since been removed from the
  repository as stale pre-publish output
- newer script defaults now write backend-aware outputs under
  `benchmark-results/aia/<backend-label>/<artifact-tag>/...`
- future hybrid runs should use their own backend label rather than reusing this
  `fiasco-screened` reference snapshot