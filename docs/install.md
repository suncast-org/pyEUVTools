# Installation

## Stable release

```bash
pip install pyeuvtools
```

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
from pyeuvtools.response import ensure_fiasco_database, get_fiasco_backend_status

status = get_fiasco_backend_status()
if not status.database_available:
	status = ensure_fiasco_database(ask_before=False)
```

## Notes

- `aiapy` is used for AIA wavelength-response functionality.
- `fiasco` is the first Python-native CHIANTI backend being prototyped for temperature-response work.
- the package currently targets Python 3.12+

