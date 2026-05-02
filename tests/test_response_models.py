from astropy.time import Time
import astropy.units as u

from pyeuvtools.response.models import WavelengthResponseSet


def test_wavelength_response_set_fields() -> None:
    response = WavelengthResponseSet(
        instrument="AIA",
        obstime=Time("2020-11-26T19:58:31"),
        channels=("171",),
        wavelength=u.Quantity([171.0], u.angstrom),
        responses={"171": u.Quantity([1.0], u.cm**2 * u.DN / u.ph)},
    )
    assert response.instrument == "AIA"
    assert response.channels == ("171",)
