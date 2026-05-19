# Usage

## Single-channel AIA wavelength response

```python
from astropy.time import Time
from pyeuvtools.response.aia import build_aia_wavelength_response

response = build_aia_wavelength_response(171, Time("2020-11-26T19:58:31"))
table = response.to_table()

print(response.channel)
print(response.response.unit)
print(table.colnames)
```

The returned object is a stable container with explicit metadata and a quantity-aware
table export path suitable for downstream use.

## Multi-channel AIA wavelength response set

```python
from astropy.time import Time
from pyeuvtools.response.aia import build_aia_wavelength_response_set

responses = build_aia_wavelength_response_set(Time("2020-11-26T19:58:31"))
table = responses.to_table()

print(responses.instrument)
print(responses.channels)
print(responses.wavelength.shape)
print(responses.responses["171"].shape)
print(table.colnames[:3])
```

## Current limitation

The package now exposes a compact public AIA temperature-response path through
`aia_get_response(...)` and the downstream bridge helper
`build_aia_temperature_response_gx_payload(...)`.

The remaining limitations for `0.1.0` are the broader SSW branches that are
still intentionally deferred:

- `full` structures
- `all` channel mode beyond the standard thin-filter EUV set
- `uv` channel support
- non-`dn` temperature-response branches

## Compact `aia_get_response` correction states

```python
from pyeuvtools.response import aia_get_response

response = aia_get_response(
	temperature=True,
	correction="evenorm_chiantifix",
	timedepend_date="2025-11-26T15:34:31",
)

print(response.metadata["correction_state"])
print(response.metadata["evenorm"])
print(response.metadata["chiantifix"])
```

The compact Python `aia_get_response` surface is intentionally non-interactive.
It only exposes scientifically valid correction states via `correction=`:

- `raw`
- `evenorm`
- `evenorm_chiantifix`

The legacy `evenorm=` and `chiantifix=` keywords remain as a temporary
compatibility layer, but they are deprecated and `chiantifix`-only requests are
rejected rather than silently coerced.

## Static STEREO/EUVI GX payload

```python
from pyeuvtools.response import build_euvi_temperature_response_gx_payload

payload, payload_dtype, meta = build_euvi_temperature_response_gx_payload(
    spacecraft="ahead",
    obstime="2025-11-26T15:34:31",
)

print(meta["instrument"])
print(meta["channels"])
print(payload_dtype.names)
print(payload["all"][0].shape)
```

The current EUVI path matches the static GX Simulator implementation. It uses
the packaged Ahead or Behind SRA calibration file, the S1 filter, the standard
171, 195, 284, and 304 A channels, and the packaged AIA hybrid emissivity grid.
The `obstime` argument is accepted for future time-dependent degradation support,
but it is not used by the current static calculation. Ephemeris and roll
metadata are deliberately left to caller-side geometry code.

## Generate and quick-plot from the exposed API

To generate a compact AIA response artifact through the public
`aia_get_response` API and quick-plot all channel curves on one panel, run:

```bash
PYTHONPATH=src python scripts/run_aia_get_response.py \
	--response-type temperature \
	--correction evenorm_chiantifix \
	--obstime 2025-11-26T15:34:31
```

By default this writes under:

- `~/.pyeuvtools/aia-get-response/temperature/evenorm_chiantifix/`

with both:

- `aia_temperature_evenorm_chiantifix.npz`
- `aia_temperature_evenorm_chiantifix.png`

The same CLI also supports compact area products:

```bash
PYTHONPATH=src python scripts/run_aia_get_response.py \
	--response-type effective_area \
	--correction evenorm \
	--obstime 2025-11-26T15:34:31
```

For `emissivity`, the CLI saves the compact `.npz` artifact but currently skips
the quick-plot step.

## Compare against the canonical IDL AIA fixture

```python
from pyeuvtools.response import canonical_aia_benchmark_path, compare_aia_response_to_idl

comparison = compare_aia_response_to_idl(
	canonical_aia_benchmark_path(),
	"2025-11-26T15:34:31",
)

print(comparison.channel_match)
print(comparison.idl_temperature_shape)
print(comparison.python_wavelength_samples)
print(comparison.blocking_gaps)
```

This helper is intended to make the current scientific gap explicit. Today the
canonical IDL fixture is a temperature-response structure, while the shipped Python
API still exposes wavelength responses.

## Compare a folded temperature-response candidate against the raw IDL benchmark

```python
import astropy.units as u
import numpy as np
from pyeuvtools.response import canonical_aia_benchmark_path, compare_aia_temperature_response_to_idl

comparison = compare_aia_temperature_response_to_idl(
	canonical_aia_benchmark_path(),
	emissivity_wavelength=u.Quantity([90.0, 95.0, 100.0], u.angstrom),
	emissivity_logte=np.linspace(4.0, 9.0, 101),
	emissivity=u.Quantity(np.ones((3, 101)), u.dimensionless_unscaled),
	obstime="2025-11-26T15:34:31",
)

print(comparison.logte_match)
print(comparison.max_absolute_difference)
print(comparison.max_relative_difference)
```

This comparison path expects an already chosen emissivity grid. It does not yet
construct the CHIANTI emissivity surface itself, but it removes the current
package-level blocker where the benchmark comparison stopped at the wavelength-response
abstraction boundary.

## Screen ions and try a broader CHIANTI-backed comparison

```python
import astropy.units as u
import numpy as np
from pyeuvtools.response import (
	build_fiasco_ion_spectrum_grid,
	canonical_aia_benchmark_path,
	compare_aia_temperature_response_to_idl,
	load_idl_aia_response,
	screen_fiasco_ions_for_temperature_grid,
)

idl = load_idl_aia_response(canonical_aia_benchmark_path())
full_logte = idl.logte
supported_mask = full_logte <= 8.55
supported_temperature = (10 ** full_logte[supported_mask]) * u.K

candidates = [
	"He 2", "C 4", "C 5", "C 6", "N 5", "N 6", "N 7", "O 4", "O 5", "O 6", "O 7", "O 8",
	"Ne 6", "Ne 7", "Ne 8", "Ne 9", "Mg 5", "Mg 6", "Mg 7", "Mg 8", "Mg 9", "Mg 10", "Mg 11", "Mg 12",
	"Si 7", "Si 8", "Si 9", "Si 10", "Si 11", "Si 12", "Si 13", "Si 14",
	"S 8", "S 9", "S 10", "S 11", "S 12", "S 13", "S 14", "S 15", "S 16",
	"Fe 8", "Fe 9", "Fe 10", "Fe 11", "Fe 12", "Fe 13", "Fe 14", "Fe 15", "Fe 16", "Fe 17", "Fe 18",
]

report = screen_fiasco_ions_for_temperature_grid(
	candidates,
	temperature=supported_temperature,
	density=1e9 / u.cm**3,
	use_two_ion_model=False,
	include_protons=False,
)

grid = build_fiasco_ion_spectrum_grid(
	report.supported_ions,
	temperature=supported_temperature,
	density=1e9 / u.cm**3,
	wavelength_range=u.Quantity([50.0, 400.0], u.angstrom),
	bin_width=1 * u.angstrom,
	use_two_ion_model=False,
	include_protons=False,
)

full_intensity = u.Quantity(
	np.zeros((grid.wavelength.size, full_logte.size)),
	grid.intensity.unit,
)
full_intensity[:, supported_mask] = grid.intensity

comparison = compare_aia_temperature_response_to_idl(
	canonical_aia_benchmark_path(),
	emissivity_wavelength=grid.wavelength,
	emissivity_logte=full_logte,
	emissivity=full_intensity,
	obstime="2025-11-26T15:34:31",
)

print(report.supported_ions)
print(comparison.max_absolute_difference)
print(comparison.max_relative_difference)
```

This is not yet a parity workflow. It is an exploratory bridge for checking how a
broader screened ion subset behaves against the raw benchmark over the currently
supported CHIANTI temperature range.

If you want to try the current broader-ion bridge directly from the command line,
run:

```bash
PYTHONPATH=src python scripts/run_screened_raw_compare.py
```

That command now saves its comparison and cache artifacts outside the
repository by default, typically under:

```text
~/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/
```

The default outputs include:

```text
~/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_compare.png
~/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_compare_data.npz
~/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_spectrum_grid.npz
~/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_screening.npz
```

The default path is still backend-aware, so the current `fiasco` prototype does
not silently reuse the same generic artifact location that a future hybrid
backend run would use, but it also no longer dirties the repository by default.
To preserve a historical snapshot instead of writing to the rolling `latest`
location, set a custom run tag:

```bash
PYTHONPATH=src python scripts/run_screened_raw_compare.py --artifact-tag 2026-05-03-fiasco-reference
```

You can choose an explicit user-local artifact directory with:

```bash
PYTHONPATH=src python scripts/run_screened_raw_compare.py \
	--artifact-dir "$HOME/.pyeuvtools/benchmark-results/aia/fiasco-screened/my-run/screened_raw_compare"
```

For contributor or release work where the result is intentionally meant to live
inside the repository, pass an explicit repo-local artifact directory. You can
also choose a single explicit output path with:

```bash
PYTHONPATH=src python scripts/run_screened_raw_compare.py --plot-output benchmark-results/aia/custom/my_compare.png
```

Once that data artifact exists, you can regenerate a fresh plot without rerunning the CHIANTI computation:

```bash
PYTHONPATH=src python scripts/run_screened_raw_compare.py \
	--plot-from-data "$HOME/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_compare_data.npz" \
	--plot-output "$HOME/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_compare_rerendered.png"
```

To skip the expensive CHIANTI spectrum build on repeated runs, save and reuse the spectrum-grid cache:

```bash
PYTHONPATH=src python scripts/run_screened_raw_compare.py \
	--spectrum-cache "$HOME/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_spectrum_grid.npz"

PYTHONPATH=src python scripts/run_screened_raw_compare.py \
	--reuse-spectrum-cache \
	--spectrum-cache "$HOME/.pyeuvtools/benchmark-results/aia/fiasco-screened/latest/screened_raw_compare/aia_screened_raw_spectrum_grid.npz"
```

The current comparison workflow keeps AIA 335 in the reports and plots, but treats it as a lower-confidence validation channel. Public literature reports passband inconsistencies, higher-order contamination, and incomplete spectral content near 335 A, so mismatches there should be interpreted more cautiously than in channels such as 171, 193, or 211. Relevant references include Boerner et al. 2013 (Sol. Phys. 289, 2377; arXiv:1307.8045) and Trabert and Beiersdorfer 2018 (A&A 617, A8; DOI 10.1051/0004-6361/201833256).

## Generate the normalized hybrid export

The published `aia_V9` hybrid export should be generated with an explicit output
directory and an explicit `.genx` source pair, even when those values match the
current defaults. That keeps the provenance statement simple: the artifact in
`benchmark-data/aia/genx-exports/aia_V9/` came from the command below.

From the repository root:

```bash
REPO_ROOT=$PWD
SSWIDL=/path/to/sswidl

cat <<EOF | "$SSWIDL"
.compile ${REPO_ROOT}/scripts/idl/ExportAIAHybridGenx.pro
ExportAIAHybridGenx, outdir='${REPO_ROOT}/benchmark-data/aia/genx-exports/aia_V9', response_dir='${SSW}/sdo/aia/response', fullinst_name='aia_V9_all_fullinst.genx', fullemiss_name='aia_V9_fullemiss.genx'
exit
EOF
```

The exporter still defaults to the current `aia_V9` source pair, but advanced
users do not need to edit the IDL script to work with a future response
release. Re-run the same command with a different `fullinst_name` and
`fullemiss_name`, or pass explicit `fullinst_file` and `fullemiss_file` paths.
If `outdir` is omitted, the exporter now writes outside the repository under a
user-local directory such as `~/.pyeuvtools/aia/genx-exports/aia_V10/` and only
uses a repository path when `outdir` is passed explicitly. That keeps the
cloned tree clean for normal users while still allowing contributors to
regenerate the committed repo artifact with an explicit repo-local `outdir`.

## Hybrid genx comparison

Once a normalized hybrid export exists, you can compare it directly against the
canonical raw IDL benchmark with:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py
```

With no explicit output arguments, the comparison artifacts now go to a
user-local directory outside the repository, typically:

```text
~/.pyeuvtools/benchmark-results/aia/hybrid-genx/latest/hybrid_raw_compare/
```

That default is intentionally safe for distributed clones: the repository can
ship reference benchmark artifacts and the committed `aia_V9` export, while a
user's own runs do not dirty the working tree unless they explicitly choose a
repo-local path.

With no explicit export arguments, the Python side now resolves the highest
packaged exported version under `src/pyeuvtools/data/aia/genx-exports/`,
mirroring the usual AIA-version preference that favors the newest installed
response.

To pin an older exported emissivity version for comparison work, pass an
emissivity-version selector:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--emversion V9
```

You can also split the selectors the same way SSW does:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--version V10 \
	--emversion V9 \
	--respversion V9
```

That means:

- `--version`: choose the instrument response version
- `--emversion`: choose the exported emissivity artifact version
- `--respversion`: choose the degradation response table version or path

You can still override the default lookup completely with an explicit path:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--hybrid-export benchmark-data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav
```

For user-local custom artifacts, pass an explicit artifact directory:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--artifact-dir "$HOME/.pyeuvtools/benchmark-results/aia/hybrid-genx/my-run/hybrid_raw_compare"
```

For contributor or release work where the result is intentionally meant to live
inside the repository, pass an explicit repo-local artifact directory:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--artifact-dir benchmark-results/aia/hybrid-genx/2026-05-04-raw-reference/hybrid_raw_compare \
	--hybrid-export benchmark-data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav
```

That published `2026-05-04-raw-reference` snapshot is the current raw baseline:
no `evenorm`, no `chiantifix`.

Without that explicit override, the workflow no longer writes backend-specific
outputs into the repository.

The explicit repo-local developer workflow writes under:

```text
benchmark-results/aia/hybrid-genx/latest/hybrid_raw_compare/
```

To preserve a historical snapshot instead of writing to the rolling `latest`
location, set a custom run tag:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--emversion V9 \
	--artifact-dir benchmark-results/aia/hybrid-genx/2026-05-03-hybrid-reference/hybrid_raw_compare \
	--artifact-tag 2026-05-03-hybrid-reference
```

Once the saved comparison data exists, you can regenerate a plot without
rerunning the hybrid fold:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--plot-from-data "$HOME/.pyeuvtools/benchmark-results/aia/hybrid-genx/latest/hybrid_raw_compare/aia_hybrid_raw_compare_data.npz" \
	--plot-output "$HOME/.pyeuvtools/benchmark-results/aia/hybrid-genx/latest/hybrid_raw_compare/aia_hybrid_raw_compare_rerendered.png"
```

## Correction-layer naming for contributor snapshots

Use distinct repo-local directories for each scientific state instead of
reusing the raw baseline path.

Recommended names:

- raw: `benchmark-results/aia/hybrid-genx/<date>-raw-reference/hybrid_raw_compare/`
- evenorm: `benchmark-results/aia/hybrid-genx/<date>-evenorm-reference/hybrid_raw_compare/`
- evenorm_chiantifix: `benchmark-results/aia/hybrid-genx/<date>-evenorm-chiantifix-reference/hybrid_raw_compare/`

To generate a local evenorm IDL reference artifact for a matching comparison,
run the IDL benchmark generator with `evenorm=1` and `chiantifix=0`:

```idl
GenerateCanonicalAIABenchmark, evenorm=1L, chiantifix=0L, outdir=file_expand_path(filepath('20251126T153431-evenorm', root_dir=filepath('aia', root_dir=filepath('benchmark-data', root_dir=filepath('.pyeuvtools', root_dir=getenv('HOME'))))))
```

Then compare the hybrid path against that explicit evenorm fixture:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--evenorm \
	--benchmark-path "$HOME/.pyeuvtools/benchmark-data/aia/20251126T153431-evenorm/aia_raw_response_20251126T153431_evenorm.sav" \
	--artifact-dir benchmark-results/aia/hybrid-genx/2026-05-04-evenorm-reference/hybrid_raw_compare \
	--artifact-tag 2026-05-04-evenorm-reference \
	--hybrid-export benchmark-data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav
```

The `evenorm_chiantifix` IDL fixture can already be generated and preserved with
its own name:

```idl
GenerateCanonicalAIABenchmark, evenorm=1L, chiantifix=1L, outdir=file_expand_path(filepath('20251126T153431-evenorm-chiantifix', root_dir=filepath('aia', root_dir=filepath('benchmark-data', root_dir=filepath('.pyeuvtools', root_dir=getenv('HOME'))))))
```

Then compare the hybrid path against that explicit `evenorm_chiantifix` fixture:

```bash
PYTHONPATH=src python scripts/run_hybrid_raw_compare.py \
	--evenorm \
	--chiantifix \
	--benchmark-path benchmark-data/aia/20251126T153431/aia_raw_response_20251126T153431.sav \
	--artifact-dir benchmark-results/aia/hybrid-genx/2026-05-04-evenorm-chiantifix-reference/hybrid_raw_compare \
	--artifact-tag 2026-05-04-evenorm-chiantifix-reference \
	--hybrid-export src/pyeuvtools/data/aia/genx-exports/aia_V9/aia_hybrid_genx_export_v1.sav
```

To regenerate both published comparison snapshots with one command, run:

```bash
PYTHONPATH=src python scripts/run_hybrid_reference_compare_pair.py
```

By default that wrapper writes the two repo-local reference outputs under:

- `benchmark-results/aia/hybrid-genx/2026-05-04-raw-reference/hybrid_raw_compare/`
- `benchmark-results/aia/hybrid-genx/2026-05-04-evenorm-chiantifix-reference/hybrid_raw_compare/`

The published reference layout is documented alongside the artifacts so it is
self-describing from the repository tree:

- `benchmark-results/aia/hybrid-genx/README.md`
	- top-level index for the retained hybrid reference snapshots
- `benchmark-results/aia/hybrid-genx/2026-05-04-raw-reference/README.md`
	- provenance and scope for the raw published snapshot
- `benchmark-results/aia/hybrid-genx/2026-05-04-evenorm-chiantifix-reference/README.md`
	- provenance and scope for the corrected published snapshot
- `benchmark-results/aia/hybrid-genx/reference_compare_pair_summary.json`
	- machine-readable summary emitted by the wrapper after refreshing both
		published comparisons

For `0.1.0`, the Python `chiantifix` path works out of the box because the
required Python-readable correction export is shipped under
`src/pyeuvtools/data/aia/chiantifix-exports/`.

Contributors can refresh that packaged asset from the SSW correction `.genx`
with:

```bash
printf '.compile /Users/gelu/code/SUNCAST-ORG/pyEUVTools/scripts/idl/ExportAIAChiantifix.pro\nExportAIAChiantifix\nexit\n' | sswidl
```

By default this writes:

- `~/.pyeuvtools/aia/chiantifix-exports/aia_V9/aia_chiantifix_export_v1.sav`
- `~/.pyeuvtools/aia/chiantifix-exports/aia_V9/aia_chiantifix_export_v1.metadata.txt`

To refresh the packaged runtime asset in the repository, pass an explicit
repo-local `outdir`. Pass `chiantifix_export=...` to the Python
`aia_get_response(...)` wrapper when you want to pin a non-default export path
explicitly.
