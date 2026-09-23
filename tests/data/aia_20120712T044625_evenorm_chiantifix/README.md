# AIA GX IDL parity fixture

This fixture freezes the inputs used to compare the pyEUVTools GX response bridge with SolarSoft IDL for all seven AIA EUV channels.

- Epoch: `2012-07-12T04:46:25.800`
- Channels: 94, 131, 171, 193, 211, 304, and 335 Angstrom
- IDL call: `aia_get_response(/temperature, /dn, evenorm=1, chiantifix=1, timedepend_date=...)`
- IDL instrument/emissivity export: AIA V9
- IDL CHIANTI version reported during generation: 11.0.2
- Detector pixel area: 0.36 arcsec^2

`idl_aia_response.sav` is the compact IDL response structure. `aia_correction_table.ecsv` is the JSOC AIA response correction table fetched on 2026-09-17 and frozen so the test does not require network access or drift with future calibration-table updates.

The regression rebuilds the response from pyEUVTools' packaged V9 hybrid export and requires every significant temperature-response sample in every channel to agree with IDL within a relative error of `5e-4`.
