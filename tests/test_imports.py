"""Smoke test for the M0.4 scaffold: the layer packages import cleanly."""


def test_layer_packages_importable() -> None:
    import ingest
    import query

    assert ingest.__doc__
    assert query.__doc__
