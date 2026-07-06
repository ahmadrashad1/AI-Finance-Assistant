import ai_platform


def test_ai_platform_package_is_importable() -> None:
    assert ai_platform.__version__ == "0.1.0"
