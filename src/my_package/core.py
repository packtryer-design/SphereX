"""Core functionality. Replace this example with your own code."""


def greet(name: str) -> str:
    """Return a greeting for ``name``."""
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"
