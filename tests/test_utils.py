from utils.paths import unc_join_path


def test_unc_path_join():
    a = "C:/Builds"
    b = "//depot/release"
    assert unc_join_path(a, b) == "C:/Builds/depot/release"