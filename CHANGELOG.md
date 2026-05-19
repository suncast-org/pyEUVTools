# Changelog

## 0.1.3 - Static STEREO/EUVI Response Builder

### Added

- Static STEREO/EUVI temperature-response builder for Ahead and Behind using
  packaged GX SRA calibration files.
- EUVI effective-area, normalized IDL-view, and ComputeEUV-compatible payload
  helpers.
- Documentation for the EUVI static-response contract, including the S1 default
  filter, standard EUVI channels, `obstime` as a future placeholder, and no
  returned ephemeris metadata.
- Parity coverage against the GX/IDL EUVI response artifacts through an external
  local comparison workflow.

## 0.1.2 - README Status Correction

### Changed

- The README project-status section now reflects the live release state without
  version-specific future-tense wording that would go stale on PyPI.
- The README now includes the Zenodo concept DOI badge and stable DOI link for
  citation and archival discovery.

## 0.1.1 - Release Metadata Cleanup

### Changed

- The published project metadata now reflects that `0.1.0` was already released
  on PyPI and GitHub rather than still being in a local pre-release state.
- The README now advertises the live PyPI package and hosted documentation with
  release-facing badges.
- Zenodo and citation metadata now target the `0.1.1` follow-up patch release.

## 0.1.0 - Released

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

- First public release of `pyEUVTools` on PyPI and GitHub.
- The release metadata explicitly acknowledges the `suncast-org` GitHub
  organization in the Zenodo-facing project description and notes.
