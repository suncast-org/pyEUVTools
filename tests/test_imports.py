from pyeuvtools import __version__


def test_version_string_present() -> None:
    assert isinstance(__version__, str)
    assert __version__
