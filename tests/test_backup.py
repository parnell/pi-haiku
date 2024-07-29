import os
import shutil
import tempfile
from pathlib import Path

import pytest

from pi_haiku import PackageMatch, PyPackage, PyProjectModifier


@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)


@pytest.fixture
def sample_pyproject_toml():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "test-project"
version = "0.1.0"
description = "A test project"

[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.25.1"
local-package = {path = "../local-package", develop = true}
"""


@pytest.fixture
def pyproject_file(temp_project_dir, sample_pyproject_toml):
    pyproject_path = temp_project_dir / "pyproject.toml"
    with open(pyproject_path, "w") as f:
        f.write(sample_pyproject_toml)
    return pyproject_path


@pytest.fixture
def mock_packages(temp_project_dir):
    local_package_dir = temp_project_dir.parent / "local-package"
    local_package_dir.mkdir(exist_ok=True)
    local_package_pyproject = local_package_dir / "pyproject.toml"
    with open(local_package_pyproject, "w") as f:
        f.write(
            """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "local-package"
version = "0.1.0"
description = "A local package"

[tool.poetry.dependencies]
python = "^3.8"
"""
        )
    return {"local-package": PyPackage.from_path(local_package_pyproject)}


def test_convert_to_remote_with_backup_dir(temp_project_dir, pyproject_file, mock_packages):
    backup_dir = temp_project_dir / "backup"
    os.mkdir(backup_dir)

    ppm = PyProjectModifier(pyproject_file, packages=mock_packages)
    match_patterns = [
        PackageMatch(
            package_regex="^local-package$", version_regex=r"^.*$", version_to="{package.version}"
        )
    ]

    changes = ppm.convert_to_remote(match_patterns=match_patterns, backup_dir=backup_dir)

    # Check if the backup file was created
    backup_file = backup_dir / "test-project_pyproject.toml"
    assert backup_file.exists()

    # Check if the changes were applied
    assert len(changes) == 1
    assert "local-package" in changes[0][0]
    assert "0.1.0" in changes[0][1]

    # Verify the content of the backup file
    with open(backup_file, "r") as f:
        content = f.read()
        assert 'local-package = "0.1.0"' in content
        assert 'path = "../local-package"' not in content
        assert "develop = true" not in content


def test_convert_to_local_with_backup_dir(temp_project_dir, pyproject_file, mock_packages):
    backup_dir = temp_project_dir / "backup"
    os.mkdir(backup_dir)

    # Modify the original pyproject.toml to have a remote dependency
    with open(pyproject_file, "r") as f:
        content = f.read()
    content = content.replace(
        'local-package = {path = "../local-package", develop = true}', 'local-package = "0.1.0"'
    )
    with open(pyproject_file, "w") as f:
        f.write(content)

    ppm = PyProjectModifier(pyproject_file, packages=mock_packages)
    match_patterns = [
        PackageMatch(
            package_regex="^local-package$",
            version_regex=r"^.*$",
            version_to='{develop = true, path = "{package.path.relative}"}',
        )
    ]

    changes = ppm.convert_to_local(match_patterns=match_patterns, backup_dir=backup_dir)

    # Check if the backup file was created
    backup_file = backup_dir / "test-project_pyproject.toml"
    assert backup_file.exists()

    # Check if the changes were applied
    assert len(changes) == 1
    assert "local-package" in changes[0][0]
    assert "path" in changes[0][1] and "develop = true" in changes[0][1]

    # Verify the content of the backup file
    with open(backup_file, "r") as f:
        content = f.read()
        assert "local-package" in content
        assert 'path = "../local-package"' in content
        assert "develop = true" in content


def test_no_changes_with_backup_dir(temp_project_dir, pyproject_file, mock_packages):
    backup_dir = temp_project_dir / "backup"
    os.mkdir(backup_dir)

    ppm = PyProjectModifier(pyproject_file, packages=mock_packages)
    match_patterns = [
        PackageMatch(
            package_regex="^non-existent-package$",
            version_regex=r"^.*$",
            version_to="{package.version}",
        )
    ]

    changes = ppm.convert_to_remote(match_patterns=match_patterns, backup_dir=backup_dir)

    # Check that no changes were made
    assert len(changes) == 0

    # Check that no backup file was created
    backup_file = backup_dir / "test-project_pyproject.toml"
    assert not backup_file.exists()


if __name__ == "__main__":
    pytest.main([__file__])
