# pyEUVTools

`pyEUVTools` is a SunCAST package for EUV instrument response products.

The package is intended to provide reusable response-building utilities for the
broader SunCAST Python ecosystem while remaining usable as a standalone library.

## Initial Mission

- expose a Pythonic interface to time-dependent AIA wavelength response functions
- provide reusable response-table data models
- build toward GX-compatible temperature response tables

## Longer-Term Direction

The long-term design is intentionally broader than AIA. The package structure is
meant to accommodate additional instruments and response builders in future work.
