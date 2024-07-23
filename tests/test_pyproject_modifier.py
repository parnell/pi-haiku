import tempfile
from pathlib import Path

import pytest

from pi_haiku import PyPackage, PyProjectModifier, ToLocalMatch, ToRemoteMatch


@pytest.fixture
def package1_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package1"
version = "0.1.0"
description = ""
authors = ["Author One <author1@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
package2 = { path = "../package2" }
numpy = "^1.21.0"
"""


@pytest.fixture
def package2_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package2"
version = "0.2.0"
description = ""
authors = ["Author Two <author2@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
"""


@pytest.fixture
def package3_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package3"
version = "0.3.0"
description = ""
authors = ["Author Three <author3@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
"""


@pytest.fixture
def package1_pyproject_toml(tmp_path, package1_toml_content):
    file_path = tmp_path / "package1" / "pyproject.toml"
    file_path.parent.mkdir(parents=True)
    with open(file_path, "w") as f:
        f.write(package1_toml_content)
    return file_path


@pytest.fixture
def package2_pyproject_toml(tmp_path, package2_toml_content):
    file_path = tmp_path / "package2" / "pyproject.toml"
    file_path.parent.mkdir(parents=True)
    with open(file_path, "w") as f:
        f.write(package2_toml_content)
    return file_path


@pytest.fixture
def package3_pyproject_toml(tmp_path, package3_toml_content):
    file_path = tmp_path / "package3" / "pyproject.toml"
    file_path.parent.mkdir(parents=True)
    with open(file_path, "w") as f:
        f.write(package3_toml_content)
    return file_path


@pytest.fixture
def haiku(package1_pyproject_toml, package2_pyproject_toml):
    return PyProjectModifier(
        src=package1_pyproject_toml, package_dir=package1_pyproject_toml.parent.parent
    )


def test_pypackage_from_path(package1_pyproject_toml):
    pkg = PyPackage.from_path(package1_pyproject_toml)
    assert pkg.name == "package1"
    assert pkg.version == "0.1.0"
    assert "numpy" in pkg.dependencies
    assert pkg.dependencies["numpy"] == "^1.21.0"


def test_haiku_init(package1_pyproject_toml):
    haiku = PyProjectModifier(src=package1_pyproject_toml)
    assert haiku.pyproj.name == "package1"
    assert haiku.pyproj.version == "0.1.0"


def test_find_pyproject_tomls(package1_pyproject_toml, tmp_path):
    haiku = PyProjectModifier(src=package1_pyproject_toml)
    pyproject_files = haiku.find_pyproject_tomls(tmp_path)
    assert len(pyproject_files) == 1
    assert pyproject_files[0] == package1_pyproject_toml


def test_convert_to_local(haiku: PyProjectModifier, package1_pyproject_toml):
    match_pattern = ToLocalMatch(package_regex="package2")
    changes = haiku.convert_to_local([match_pattern], in_place=True)
    assert len(changes) == 1
    with open(package1_pyproject_toml) as f:
        content = f.read()
    assert '{develop = true, path = "../package2"}' in content


def test_convert_to_remote(haiku: PyProjectModifier, package1_pyproject_toml):
    match_pattern = ToRemoteMatch(package_regex="package2")
    changes = haiku.convert_to_remote([match_pattern], in_place=True)
    assert len(changes) == 1
    with open(package1_pyproject_toml) as f:
        content = f.read()
    assert 'package2 = "0.2.0"' in content


def test_convert_back_and_forth(haiku: PyProjectModifier, package1_pyproject_toml):
    match_pattern = ToRemoteMatch(package_regex="package2")
    changes = haiku.convert_to_remote([match_pattern], in_place=True)
    assert len(changes) == 1
    with open(package1_pyproject_toml) as f:
        content = f.read()
    assert 'package2 = "0.2.0"' in content

    match_pattern = ToLocalMatch(package_regex="package2")  # type: ignore
    changes = haiku.convert_to_local([match_pattern], in_place=True)
    assert len(changes) == 1
    with open(package1_pyproject_toml) as f:
        content = f.read()
    assert '{develop = true, path = "../package2"}' in content


def test_haiku_with_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        PyProjectModifier(src=Path("/nonexistent/path/pyproject.toml"))


def test_haiku_with_invalid_toml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as tmp:
        tmp.write("This is not a valid TOML file")
        tmp.flush()
        with pytest.raises(ValueError):
            PyProjectModifier(src=Path(tmp.name))


def test_convert_with_dest_file(haiku: PyProjectModifier, tmp_path):
    dest_file = tmp_path / "new_pyproject.toml"
    match_pattern = ToRemoteMatch(package_regex="package2")
    changes = haiku.convert_to_remote([match_pattern], dest_file=str(dest_file))
    assert len(changes) == 1
    assert dest_file.exists()
    with open(dest_file) as f:
        content = f.read()
    assert 'package2 = "0.2.0"' in content


def test_convert_without_changes(haiku: PyProjectModifier):
    match_pattern = ToRemoteMatch(package_regex="nonexistent-package")
    changes = haiku.convert_to_remote([match_pattern], in_place=True)
    assert len(changes) == 0


def test_convert_to_local_with_packages(
    haiku: PyProjectModifier,
    package1_pyproject_toml,
    package2_pyproject_toml,
    package3_pyproject_toml,
):
    package2 = PyPackage.from_path(package2_pyproject_toml)
    package3 = PyPackage.from_path(package3_pyproject_toml)

    changes = haiku.convert_to_local(packages=[package2, package3], in_place=True)

    assert len(changes) == 1  # Only package2 should change, as package3 wasn't in the original

    with open(package1_pyproject_toml) as f:
        content = f.read()
    assert '{develop = true, path = "../package2"}' in content
    assert "package3" not in content  # Ensure package3 wasn't added


def test_convert_to_remote_with_packages(
    haiku: PyProjectModifier,
    package1_pyproject_toml,
    package2_pyproject_toml,
    package3_pyproject_toml,
):
    package2 = PyPackage.from_path(package2_pyproject_toml)
    package3 = PyPackage.from_path(package3_pyproject_toml)

    # First, ensure package2 is local
    haiku.convert_to_local([ToLocalMatch(package_regex="package2")], in_place=True)

    changes = haiku.convert_to_remote(packages=[package2, package3], in_place=True)

    assert len(changes) == 1  # Only package2 should change

    with open(package1_pyproject_toml) as f:
        content = f.read()

    assert 'package2 = "0.2.0"' in content
    assert "package3" not in content  # Ensure package3 wasn't added


def test_convert_with_no_patterns_or_packages(haiku: PyProjectModifier):
    with pytest.raises(ValueError, match="Either match_patterns or packages must be provided"):
        haiku.convert_to_local(in_place=True)

    with pytest.raises(ValueError, match="Either match_patterns or packages must be provided"):
        haiku.convert_to_remote(in_place=True)


def test_convert_with_both_patterns_and_packages(haiku: PyProjectModifier, package2_pyproject_toml):
    package2 = PyPackage.from_path(package2_pyproject_toml)
    match_pattern = ToLocalMatch(package_regex="package2")

    changes = haiku.convert_to_local(
        match_patterns=[match_pattern], packages=[package2], in_place=True
    )

    assert len(changes) == 1  # The conversion should happen based on match_patterns


if __name__ == "__main__":
    pytest.main()
