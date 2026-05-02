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

## Notes

- `aiapy` is used for AIA wavelength-response functionality.
- `fiasco` is the first Python-native CHIANTI backend being prototyped for temperature-response work.
- the package currently targets Python 3.12+

