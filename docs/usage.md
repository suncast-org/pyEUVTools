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
