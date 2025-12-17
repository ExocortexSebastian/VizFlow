"""Test that vizflow can be imported."""


def test_import():
    """Test basic import works."""
    import vizflow as vf

    assert vf is not None


def test_version():
    """Test version is set correctly."""
    import vizflow as vf

    assert vf.__version__ == "0.4.4"
    assert isinstance(vf.__version__, str)
