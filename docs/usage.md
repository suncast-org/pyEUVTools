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
