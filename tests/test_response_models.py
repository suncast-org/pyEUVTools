from astropy.time import Time
import astropy.units as u

from pyeuvtools.response.models import AIAChannelWavelengthResponse, WavelengthResponseSet


def test_aia_channel_wavelength_response_table_export() -> None:
    response = AIAChannelWavelengthResponse(
        channel="171",
        obstime=Time("2020-11-26T19:58:31"),
        wavelength=u.Quantity([171.0], u.angstrom),
        response=u.Quantity([1.0], u.cm**2 * u.DN / u.ph),
        include_eve_correction=True,
    )
    table = response.to_table()
    assert table.colnames == ["wavelength", "response"]
    assert table.meta["instrument"] == "AIA"
    assert table.meta["channel"] == "171"
    assert table.meta["include_eve_correction"] is True


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


def test_wavelength_response_set_table_export() -> None:
    response = WavelengthResponseSet(
        instrument="AIA",
        obstime=Time("2020-11-26T19:58:31"),
        channels=("171", "193"),
        wavelength=u.Quantity([171.0, 193.0], u.angstrom),
        responses={
            "171": u.Quantity([1.0, 2.0], u.cm**2 * u.DN / u.ph),
            "193": u.Quantity([3.0, 4.0], u.cm**2 * u.DN / u.ph),
        },
    )
    table = response.to_table()
    assert table.colnames == ["wavelength", "response_171", "response_193"]
    assert table.meta["channels"] == ["171", "193"]

