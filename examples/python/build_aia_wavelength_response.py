from astropy.time import Time

from pyeuvtools.response.aia import build_aia_wavelength_response, build_aia_wavelength_response_set


def main() -> None:
    response = build_aia_wavelength_response(171, Time("2020-11-26T19:58:31"))
    responses = build_aia_wavelength_response_set(Time("2020-11-26T19:58:31"))
    print("single channel:", response.channel)
    print("single table columns:", response.to_table().colnames)
    print("instrument:", responses.instrument)
    print("channels:", responses.channels)
    print("wavelength samples:", responses.wavelength.shape)
    print("set table columns:", responses.to_table().colnames[:3])


if __name__ == "__main__":
    main()
