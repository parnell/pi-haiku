import pytest
from pathlib import Path
from unittest.mock import mock_open, patch
from pi_haiku.models import PyPackage, BuildSystem


@pytest.fixture
def sample_poetry_toml():
    return b"""
[build-system]
build-backend = "poetry.core.masonry.api"
requires = ["poetry-core"]

[tool.poetry]
name = "test-package"
version = "1.0.0"

[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.25.1"
local-package = {path = "../local-package"}

[tool.poetry.group.dev.dependencies]
pytest = "^6.2.5"
"""


def test_get_dependencies_poetry(sample_poetry_toml):
    with patch("builtins.open", mock_open(read_data=sample_poetry_toml)):
        dependencies = PyPackage.get_dependencies("dummy_path")

    assert dependencies == {
        "python": "^3.9",
        "requests": "^2.25.1",
        "local-package": {"path": "../local-package"},
        "pytest": "^6.2.5",
    }


def test_from_path_poetry(sample_poetry_toml):
    with patch("builtins.open", mock_open(read_data=sample_poetry_toml)):
        package = PyPackage.from_path("dummy_path/pyproject.toml")

    assert package.name == "test-package"
    assert package.version == "1.0.0"
    assert package.dependencies == {
        "python": "^3.9",
        "requests": "^2.25.1",
        "local-package": {"path": "../local-package"},
        "pytest": "^6.2.5",
    }


def test_get_local_dependencies():
    package = PyPackage(
        name="test-package",
        version="1.0.0",
        path=Path("dummy_path"),
        dependencies={
            "requests": "^2.25.1",
            "local-package": {"path": "../local-package"},
            "another-local": {"path": "../another-local", "develop": True},
        },
    )

    local_deps = package.get_local_dependencies()
    assert local_deps == {"local-package": "../local-package", "another-local": "../another-local"}


def test_from_path_directory(sample_poetry_toml):
    with patch("pathlib.Path.is_dir", return_value=True), patch(
        "pathlib.Path.expanduser", return_value=Path("/home/user/project")
    ), patch("pathlib.Path.resolve", return_value=Path("/home/user/project")), patch(
        "builtins.open", mock_open(read_data=sample_poetry_toml)
    ):
        package = PyPackage.from_path("/home/user/project")

    assert package.name == "test-package"
    assert package.version == "1.0.0"
    assert package.path == Path("/home/user/project/pyproject.toml")


def test_from_path_file(sample_poetry_toml):
    with patch("pathlib.Path.is_dir", return_value=False), patch(
        "pathlib.Path.expanduser", return_value=Path("/home/user/project/pyproject.toml")
    ), patch("pathlib.Path.resolve", return_value=Path("/home/user/project/pyproject.toml")), patch(
        "builtins.open", mock_open(read_data=sample_poetry_toml)
    ):
        package = PyPackage.from_path("/home/user/project/pyproject.toml")

    assert package.name == "test-package"
    assert package.version == "1.0.0"
    assert package.path == Path("/home/user/project/pyproject.toml")


if __name__ == "__main__":
    pytest.main([__file__])
