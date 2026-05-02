# Usage

## AIA wavelength response set

```python
from astropy.time import Time
from pyeuvtools.response.aia import build_aia_wavelength_response_set

responses = build_aia_wavelength_response_set(Time("2020-11-26T19:58:31"))

print(responses.instrument)
print(responses.channels)
print(responses.wavelength.shape)
print(responses.responses["171"].shape)
```

## Current limitation

The package currently exposes the AIA wavelength-response layer through `aiapy`.
GX-compatible temperature-response tables are planned but not yet implemented.
