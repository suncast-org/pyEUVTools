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
from pyeuvtools.response import compare_aia_response_to_idl

comparison = compare_aia_response_to_idl(
	"../pyGXrender-test-data/raw/responses/20251126T153431/resp_aia_20251126T153431.sav",
	"2025-11-26T15:34:31",
)

print(comparison.channel_match)
print(comparison.idl_temperature_shape)
print(comparison.python_wavelength_samples)
print(comparison.blocking_gaps)
```

This helper is intended to make the current scientific gap explicit. Today the
IDL fixture is a GX-style temperature-response structure, while the shipped Python
API still exposes wavelength responses.
