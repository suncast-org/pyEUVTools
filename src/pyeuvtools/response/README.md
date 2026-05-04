# Response Backend Notes

This directory contains the shipped AIA response builders together with the
provisional Python-native CHIANTI backend.

## Optional `fiasco` path

The optional CHIANTI path currently lives in `chianti.py` and is intentionally
kept in the repository as unfinished work rather than as the default production
backend.

### What was implemented

- backend readiness helpers:
  - `get_fiasco_backend_status`
  - `ensure_fiasco_database`
  - `rebuild_fiasco_database`
- explicit line-data probing so a partially usable HDF5 cache does not get
  reported as temperature-response ready just because `fiasco.list_ions()`
  succeeds
- explicit-ion screening with `screen_fiasco_ions_for_temperature_grid`
- explicit-ion spectrum synthesis through `build_fiasco_ion_spectrum_grid`
- `.npz` cache persistence for both screening results and built spectrum grids
- fine-grained timing and profiling hooks for the spectrum-build stage,
  including per-ion attribution inside the mirrored
  `IonCollection.spectrum` control flow
- end-to-end comparison and benchmark drivers in:
  - `scripts/run_screened_raw_compare.py`
  - `scripts/benchmark_screened_raw_compare.py`

### What was validated

- the optional-install and optional-test policy is now explicit:
  - install through `.[chianti]`
  - run backend tests explicitly with `pytest -m chianti_backend`
- unit coverage for the provisional backend lives in `tests/test_chianti.py`
  and covers:
  - backend readiness reporting
  - database ensure/rebuild helpers
  - ion screening
  - spectrum-grid building
  - cache save/load helpers
  - timing callback and profiling hooks
- live local runs established that the code can:
  - provision a usable local `fiasco` database
  - screen broad ion sets
  - build real CHIANTI-backed spectrum grids
  - fold those grids through the AIA response and compare against the raw IDL
    benchmark

### Where this line of work stopped

This path was paused after it became clear that the main remaining blocker was
not package structure or missing hooks, but runtime cost and upstream-data
shape.

The critical findings were:

- the dominant cost sits inside per-ion `fiasco` intensity evaluation during
  `IonCollection.spectrum`, not in the downstream AIA fold
- caching helps repeated local runs, but it only caches products that are built
  after the expensive CHIANTI synthesis already happened
- the SSW/IDL AIA response path appears to rely on compact `.genx` upstream
  products that are much closer to the final emissivity inputs than the current
  pure-Python runtime path
- because of that upstream difference, a practical Python path is unlikely to
  reach comparable runtime simply by tuning the current `fiasco` workflow

### Why the project switched to a hybrid approach

For now, the more practical direction is a hybrid backend that imports or
exports compact genx-derived upstream products and performs the remaining fold
steps in Python. That route is expected to preserve scientific traceability to
the benchmark while avoiding the largest recurring runtime cost in the current
pure-Python CHIANTI prototype.

### Status of this backend

- keep it in-tree as a documented prototype and reference implementation
- keep `fiasco` optional at install time
- keep its tests opt-in by marker rather than part of the default test run
- do not treat it as the default temperature-response backend until it either
  reaches acceptable parity and performance or provides capabilities the hybrid
  route cannot

### If development resumes here

The next useful tasks on this branch would be:

1. pin and verify the exact CHIANTI-version strategy against the canonical raw
   benchmark provenance
2. determine whether any additional upstream preprocessing can be moved out of
   runtime while still remaining Python-native
3. use this path primarily as a scientific cross-check against the hybrid
   backend, not as the first route to production performance