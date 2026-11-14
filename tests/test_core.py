import pytest

from my_package import greet


def test_greet() -> None:
    assert greet("World") == "Hello, World!"


def test_greet_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        greet("")
