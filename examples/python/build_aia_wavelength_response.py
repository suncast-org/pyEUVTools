from astropy.time import Time

from pyeuvtools.response.aia import build_aia_wavelength_response_set


def main() -> None:
    responses = build_aia_wavelength_response_set(Time("2020-11-26T19:58:31"))
    print("instrument:", responses.instrument)
    print("channels:", responses.channels)
    print("wavelength samples:", responses.wavelength.shape)


if __name__ == "__main__":
    main()
