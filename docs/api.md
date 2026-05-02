# API Notes

## Data model

`pyeuvtools.response.models.WavelengthResponseSet` stores:

- instrument name
- observation time
- ordered channel labels
- common wavelength grid
- per-channel response arrays

## AIA module

`pyeuvtools.response.aia` currently provides:

- `build_aia_wavelength_response`
- `build_aia_wavelength_response_set`
- `build_aia_temperature_response` (planned; currently raises `NotImplementedError`)
