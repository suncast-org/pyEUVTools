# Installation

## Stable release

There is no public PyPI release yet. The first intended release is `0.1.0`, so
current use should go through a development install from source.

## Development install

```bash
git clone https://github.com/suncast-org/pyEUVTools.git
cd pyEUVTools
python -m pip install -e .[dev]
```

## Optional CHIANTI backend prototype

```bash
git clone https://github.com/suncast-org/pyEUVTools.git
cd pyEUVTools
python -m pip install -e .[chianti]
```

After installing the optional backend, the current prototype API can check or
provision the configured `fiasco` database paths:

```python
from pyeuvtools.response import ensure_fiasco_database, get_fiasco_backend_status, rebuild_fiasco_database

status = get_fiasco_backend_status()
if not status.database_available:
	status = ensure_fiasco_database(ask_before=False)
elif not status.line_data_available:
	status = rebuild_fiasco_database(ask_before=False, show_progress=False)
```

The readiness check now probes a representative ion for line datasets as well,
so a partial or corrupt HDF5 database will not be reported as temperature-response
ready just because `fiasco.list_ions()` succeeds. When that probe fails, the
rebuild helper provides the supported recovery path for the configured local cache.

For a backend-local status note describing what this prototype already covers,
what was validated, and why active development was paused in favor of the hybrid
genx-derived approach, see `src/pyeuvtools/response/README.md`.

## Notes

- `aiapy` is used for AIA wavelength-response functionality.
- `fiasco` is the first Python-native CHIANTI backend being prototyped for temperature-response work.
- the package currently targets Python 3.12+

