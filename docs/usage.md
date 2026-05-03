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

The package currently exposes the AIA wavelength-response layer through `aiapy`.
This implementation validates supported EUV channels and provides structured export,
but GX-compatible temperature-response tables are planned and not yet implemented.

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
