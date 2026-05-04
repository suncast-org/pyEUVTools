# Changelog

## 0.1.0 - Pending Release Approval

### Changed

- `aia_get_response` now exposes a non-interactive public `correction=` API with
  the scientifically valid states `raw`, `evenorm`, and
  `evenorm_chiantifix`.
- The legacy `evenorm=` and `chiantifix=` keywords remain temporarily as a
  compatibility layer, but they now emit a deprecation warning.
- A legacy `chiantifix`-only public request is now rejected instead of being
  silently normalized, so automated workflows do not depend on hidden coercion.

### Added

- Temperature-response metadata now includes `correction_state` as the
  authoritative normalized correction label.
- The published hybrid reference workflow now includes a wrapper and summary
  artifact for refreshing both committed comparison snapshots together.
- `build_aia_temperature_response_gx_payload(...)` now exposes the exact
  `ComputeEUV`-compatible structured payload shape for downstream GX consumers.

### Packaging

- Local release metadata now targets `0.1.0` while remaining intentionally
  unpublished until final approval.
- The release metadata now explicitly acknowledges the `suncast-org` GitHub
  organization in the Zenodo-facing project description and notes.